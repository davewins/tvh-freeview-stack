# tvh-pipeline

A container that watches Tvheadend for finished recordings and prepares them for Jellyfin and for tvhgo. It replaces the
Tvheadend post-processor scripts and the host cron jobs in `legacy/` with one container, one config file and a small
database of what has been done.

## What it does, in order, for each finished recording
| Step | What | Result remembered as |
| --- | --- | --- |
| `strip_ad` | Remove audio-description tracks from the `.ts` master (stream copy, in place). Only replaced if the new file has video and audio and is at least 90% of the old size | `ok` / `none` |
| `convert_mp4` | Make `_jellyfin/<same path>.mp4`: H.264 + AAC, a keyframe every 2 s (closed GOPs) so seeking works in browsers, deinterlaced, SD turned into square pixels. Checked (video+audio present, duration within 2%) before it appears. An existing MP4 is adopted, never re-made | `ok` / `exists` / `novideo` |
| `thumbnail` | `<name>-thumb.jpg` from a frame 15% in | `ok` / `exists` |
| `comskip` | Find advert breaks, write them into the MP4 as chapters: **Commercial** for each break (including the lead-in at the start), **Part N** for the programme. Checked (same duration, streams, size within 1%, chapter count) before the file is replaced. BBC channels are skipped; a result where almost half the recording is "adverts" is refused | `ok` / `nobreaks` / `skipped` / `suspicious` |
| *(each pass)* `nfo` | Write `tvshow.nfo` per programme folder and an episode `.nfo` per recording | n/a |
| *(each pass)* `cleanup` | Remove library files whose master recording was deleted | n/a |
| *(each pass, optional)* `series_images` | Give a Jellyfin programme with no picture one of its own thumbnails | n/a |

A step that fails is retried after 5 minutes, then 10, 20, ... up to 6 hours, five times, then left. `docker exec
tvh-pipeline python3 -m tvhpipeline status` shows what has been done and any failures. Only one recording gets heavy
work per pass (every `poll_seconds`), and ffmpeg runs at low priority, so a long Comskip run never starves anything.

## Progress and status
While it works the pipeline keeps `status.json` (in its state folder) up to date every few seconds: the step running now
with a percentage (for conversions), what is waiting, and what has failed (with when it will be retried, or that it has
given up). tvhgo reads it (mount the state folder read-only, `TVHGO_PLAYBACK_PIPELINE_STATUS`) and shows a header badge
("Converting Emmerdale 41%"), a chip on each recording being processed, and reuses the progress in the player instead of
starting a second conversion. Anything else can read it too; a file not refreshed for more than about 90 seconds means
the pipeline is not running. `python3 -m tvhpipeline status` shows the same in a terminal.

```json
{"updated": 1794344525,
 "current": {"id": "<tvheadend dvr uuid>", "title": "Emmerdale", "step": "convert_mp4", "percent": 3.2, "since": 1794344517},
 "queue": [{"id": "...", "title": "...", "steps": ["convert_mp4", "comskip"]}],
 "failed": [{"id": "...", "title": "...", "step": "convert_mp4", "detail": "...", "attempts": 2, "retry_at": 1794345000}]}
```

## Odd recordings
- **A hole at the start.** Now and then a recording's first minute or two is empty (the tuner delivered nothing, for
  example when another recording started on the same tuner). The container's duration then includes the hole while the
  converted MP4 correctly does not. The pipeline measures a gap at the start of the source and allows for exactly that
  much when it checks the result; a genuinely truncated conversion still fails the check.
- **Audio description.** A track flagged as audio description is dropped from the master (`strip_ad`). Some broadcasts
  carry it as a stream ffmpeg cannot classify; it is then simply not copied into the MP4 (the MP4 gets the main audio).

## Speed
Encoding video scales with the number of CPU cores. On a 16-core machine with no cap a 30-minute HD programme converts
in about 4 minutes (roughly 7x real time); capped to 2 cores it took about 10x longer and a 90-minute programme needed
hours. The compose file therefore sets no CPU limit; ffmpeg runs at low priority (nice 10), so Tvheadend and anything
else on the machine come first. If you must cap it, expect a long programme to take roughly its own length or more.
A conversion can run for a long time, so the container's health signal ticks from a background thread and
`status` shows what it is working on right now (`NOW: convert_mp4 <file> since <time>`).

## Safety rules (each is tested)
- Work-in-progress files are named `*.part`, **never ending in `.mp4`**. (Learned the hard way: a temporary file ending
  in `.mp4` is indistinguishable from an orphaned MP4 and gets cleaned up in the middle of being written.)
- Cleanup only deletes inside the library folder, only known kinds of file, never work-in-progress, and does nothing at
  all if no `.ts`/`.mkv` recording can be found (an unmounted drive must not look like "all recordings deleted").
- A new file replaces the old only after it has been checked; otherwise the original is untouched.
- A recording is left alone until it has been unchanged for `settle_seconds`.
- One broken recording never blocks the others.

## Configuration
Copy `pipeline/config.example.toml` to `pipeline/config.toml`; every value shown is the default, so the file is optional.
Credentials and addresses come from the environment (`.env`): `TVH_URL`, `TVH_USER`, `TVH_PASS`, and for
`series_images` `JELLYFIN_URL` and `JELLYFIN_API_KEY`.

## Shadow mode and switching over
Don't replace a working pipeline blindly. Run the new one beside it, writing to a *different* library folder, and compare.

1. Set in `config.toml`:
   ```toml
   [paths]
   library = "/recordings/_jellyfin_shadow"
   [steps]
   strip_audio_description = false    # the legacy post-processor is still doing this
   cleanup = true                     # fine: it only touches the shadow folder
   ```
   Start it: `docker compose --profile pipeline up -d tvh-pipeline`. It will convert every existing finished recording
   into the shadow folder (slowly, one per pass), so give it a day or two. It never changes the masters or the real library.
2. Compare, for a few recordings: file lists, durations (`ffprobe`), the `.nfo` files (`diff`), chapters.
   `python3 -m tvhpipeline cleanup-dry-run` shows what cleanup would remove.
3. When satisfied, switch over in a quiet moment (no recording in progress):
   1. stop the legacy cron jobs (`legacy/host/` ones) and clear Tvheadend's **post-processor command**;
   2. in `config.toml` set `library = "/recordings/_jellyfin"` and `strip_audio_description = true`;
   3. `docker compose --profile pipeline up -d --force-recreate tvh-pipeline`. It adopts the existing MP4s (it sees they
      exist and does not re-encode), writes any missing NFO/thumbnail and runs Comskip on recordings newer than
      `since_epoch` if you set one.
4. Keep `legacy/` for a few weeks as the fallback (re-enable the post-processor command and cron lines).

## Building and testing
```
docker build -t tvh-pipeline pipeline/
docker run --rm --entrypoint python3 tvh-pipeline -W ignore -m unittest discover -s /opt/tvh-pipeline/tests -t /opt/tvh-pipeline
```
The tests include a full pass against a fake Tvheadend using real ffmpeg on a synthetic recording that has an
audio-description track.
