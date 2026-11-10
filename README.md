# tvh-freeview-stack

A self-hosted **UK Freeview recorder** you can run from one `docker compose` file: [Tvheadend](https://tvheadend.org)
records, a **pipeline** turns every recording into something Jellyfin and browsers play well (MP4, thumbnail, metadata,
advert breaks marked, audio description removed), and **tvhgo** gives a modern web interface with live TV, playback,
series recording and a programme guide.

It grew out of one household's setup (a Hauppauge dualHD tuner, UK Freeview, Jellyfin for
playback) and is shared in case it saves someone else the same work. It is a personal project, in daily use, not a
product: expect to adapt it to your tuner, region and taste.

```
 DVB tuner ──► Tvheadend ──► recordings/Show/Show - 2026-11-09 20.00.ts   (the master, only altered to drop
                 │                         │                                audio-description tracks)
                 │ API                     ▼
                 ├──────────────► tvh-pipeline ──► recordings/_jellyfin/Show/…
                 │                  (container)       ├─ Show - 2026-11-09 20.00.mp4   H.264/AAC, seekable, with
                 │                                    │                                 "Commercial" chapters
                 │      progress                      ├─ …-thumb.jpg, .nfo, tvshow.nfo
                 ▼      (status.json)                 ▼
              tvhgo (web UI, live TV,            Jellyfin "Shows" library (+ Intro Skipper plugin)
              player, series rules, Skip ad break, tuner + progress display)
```

## Why you might want it
- **Recordings that just work everywhere.** Broadcast `.ts` files seek badly and play in few browsers. The pipeline makes
  a clean H.264/AAC MP4 with a keyframe every 2 seconds, so seeking works in browsers, Jellyfin and phones.
- **Skip the adverts.** [Comskip](https://github.com/erikkaashoek/Comskip) finds the breaks and the pipeline writes
  them into the MP4 as chapters. In Jellyfin (with the Intro Skipper plugin) they become Skip buttons; in tvhgo there is a
  "Skip ad break" button.
- **No audio description by accident.** Audio-description tracks are removed from the master so the wrong track never
  plays.
- **Looks after itself.** Resumes after a restart, retries failures with back-off, never deletes anything it cannot
  account for, and tidies the library when Tvheadend removes old recordings.
- **You can see what it is doing.** A status file and tvhgo's badge show what is converting and how far, what is waiting
  and what failed.
- **Honest about the tuners.** Tvheadend ties a tuner to a whole multiplex, so recordings on the same one share it.
  tvhgo shows how many tuners are in use and warns when a clash is coming.

## What's here
| Folder | What |
| --- | --- |
| `docker-compose.yml`, `.env.example` | The whole stack: `cp .env.example .env`, edit, `docker compose up -d` |
| `pipeline/` | **tvh-pipeline**, the container that does the work after a recording ([docs/pipeline.md](docs/pipeline.md)) |
| `legacy/` | The shell/cron scripts this grew out of, kept as reference and as a fallback |
| `tvheadend/` | `export-config.sh`, and the DVR profile as a worked example |
| `ops/` | Backup script and example cron lines |
| `docs/` | [install](docs/install.md), [pipeline](docs/pipeline.md), [tvhgo](docs/tvhgo.md), [tvheadend](docs/tvheadend.md), [jellyfin](docs/jellyfin.md), [recovery](docs/recovery.md) |

## Quick start
You need Linux with Docker and Compose, a DVB tuner visible as `/dev/dvb`, and disk space (roughly 1 GB per 30 minutes of
HD, plus about the same again for the MP4 copy).

```
git clone https://github.com/davewins/tvh-freeview-stack && cd tvh-freeview-stack
cp .env.example .env            # edit: folders, LAN address, passwords
docker build -f Dockerfile.player -t tvhgo-player:latest <path to a clone of davewins/tvhgo-player>
docker compose up -d tvheadend  # then do Tvheadend's first-run wizard (tuner scan, channels, EPG)
docker compose --profile pipeline up -d
```
Full steps, including the Tvheadend users and DVR profile to create, are in [docs/install.md](docs/install.md).

## The parts
- **Tvheadend** ([linuxserver image](https://docs.linuxserver.io/images/docker-tvheadend/)): tuners, EPG, recording.
- **tvhgo** ([davewins/tvhgo-player](https://github.com/davewins/tvhgo-player), a fork of
  [davidborzek/tvhgo](https://github.com/davidborzek/tvhgo)): the web interface ([docs/tvhgo.md](docs/tvhgo.md)).
- **tvh-pipeline** (this repo): per recording it (1) removes audio-description tracks from the master, (2) makes the MP4,
  (3) makes a thumbnail, (4) writes Jellyfin `.nfo` files, (5) finds adverts and writes chapters, and (6) tidies the
  library. Python standard library, ffmpeg and Comskip in one small container, with a SQLite record of what is done.
- **Jellyfin** (not in the compose file): point a "Shows" library at `recordings/_jellyfin`
  ([docs/jellyfin.md](docs/jellyfin.md)).

## Status and limits
- Used daily for UK Freeview recordings; the pipeline replaced the original scripts on 2026-11-10 after a shadow run
  that compared its output with theirs. It has an automated test suite (including a full pass with real ffmpeg against
  a fake Tvheadend) that runs in CI.
- **UK Freeview focus.** Channel groups, date formats, the BBC "no adverts" rule and the "New:" title handling assume UK
  broadcasts. Other regions should work for recording and conversion but will want tweaks.
- Comskip is heuristic. It is very good on commercial channels and is not run on BBC channels at all; a result where
  almost half a recording is "adverts" is refused. Expect the odd missed or extra break.
- Encoding is CPU-only (x264). Plan on roughly one conversion at a time; a 30-minute HD programme took about 4 minutes
  on a 16-core machine.

## Security
This stack has no secrets in the repository: passwords live in `.env` and `pipeline/config.toml`, both git-ignored.
Run it on a trusted network, restrict each Tvheadend user's allowed networks, and put a TLS reverse proxy in front before
exposing tvhgo to the internet ([docs/tvhgo.md](docs/tvhgo.md#security-notes)). Running a recorder is your responsibility:
recordings are for personal use and Freeview content remains the broadcasters' copyright.

## Contributing
Issues and pull requests are welcome, but this is maintained in spare time. Please run the tests first:
```
docker build -t tvh-pipeline pipeline/
docker run --rm --entrypoint python3 tvh-pipeline -W ignore -m unittest discover -s /opt/tvh-pipeline/tests -t /opt/tvh-pipeline
```

## Credits and licence
Built around [Tvheadend](https://tvheadend.org), [Jellyfin](https://jellyfin.org), [Comskip](https://github.com/erikkaashoek/Comskip),
[ffmpeg](https://ffmpeg.org) and [tvhgo](https://github.com/davidborzek/tvhgo) by David Borzek. Programme artwork in
tvhgo comes from [TMDb](https://www.themoviedb.org) (this product uses the TMDb API but is not endorsed or certified by
TMDb). Much of this was written with the help of Claude (Anthropic) and reviewed and run by the repository owner.

Released under the [MIT licence](LICENSE). Comskip (GPL) and the other tools are separate projects with their own licences;
this repository does not contain their code (the pipeline image installs Comskip and ffmpeg from the distribution's packages).
