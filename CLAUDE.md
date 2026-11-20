# CLAUDE.md — tvh-freeview-stack

Notes for Claude (and other AI assistants or people) working in this repository. Keep it current. The user-facing
description is `README.md` and `docs/`; this file is the "how to work here" plus what has been learned the hard way.

## What this is

A self-hosted UK Freeview recorder: **Tvheadend** records, the **tvh-pipeline** container turns each recording into a
browser/Jellyfin-friendly MP4 (thumbnail, `.nfo`, advert chapters, audio description stripped), and **tvhgo** (fork:
[davewins/tvhgo-player](https://github.com/davewins/tvhgo-player), see its own `CLAUDE.md`) is the web UI. Jellyfin
(not in the compose file) reads `recordings/_jellyfin`.

```
Tvheadend ─► recordings/Show/Show - date.ts ─► tvh-pipeline ─► recordings/_jellyfin/Show/Show - date.mp4 (+thumb, .nfo)
     ▲ API                                          │ status.json
     └──────────── tvhgo (reads both, plays MP4, deletes/keeps/protects) ◄──┘
```

## Layout

| Path | What |
| --- | --- |
| `docker-compose.yml`, `.env.example` | The stack (Tvheadend, tvhgo, optional `pipeline` profile). Secrets only in `.env` (git-ignored) |
| `pipeline/tvhpipeline/` | The pipeline (Python stdlib only). `runner.py` = main loop, `steps/*.py` = one file per step, `state.py` = SQLite record of what is done, `paths.py` = TS↔MP4 path mapping, `status.py` = `status.json` for tvhgo |
| `pipeline/tests/` | unittest suite incl. an end-to-end run with real ffmpeg against a fake Tvheadend |
| `pipeline/config.example.toml` | Every setting with its default; real config is `pipeline/config.toml` (git-ignored) |
| `legacy/` | The old shell/cron scripts this replaced. Reference and fallback only: do not extend |
| `tvheadend/`, `ops/` | Config export script and snapshot, backup script, example cron |
| `docs/` | install, pipeline, tvhgo, tvheadend, jellyfin, recovery |

## Build and test the pipeline

```bash
docker build -t tvh-pipeline pipeline/
docker run --rm --entrypoint python3 tvh-pipeline -W ignore -m unittest discover -s /opt/tvh-pipeline/tests -t /opt/tvh-pipeline
```
All tests must pass before you ship a pipeline change. Bump the image tag when you deploy (`0.1.x`), keep the previous
compose file as a backup, and check `docker logs` and the `status` output afterwards.

## Pipeline principles (do not break these)

- **Never delete anything it cannot account for.** A step that fails is retried with growing pauses (5, 10, 20 min…)
  up to `max_attempts` and then left visible in `status`.
- **Master `.ts` files are only altered to drop audio-description tracks** (stream copy, verified). Everything else is
  derived (MP4 etc.) and can be rebuilt.
- Steps are idempotent and keyed per recording in the SQLite state; a restart resumes where it stopped.
- `cleanup` removes library files whose `.ts` master is gone, **except an MP4 that has a `<name>.keep` marker** (written
  by tvhgo's "Delete, keeping the MP4"). The marker is a JSON copy of the recording and is a contract with tvhgo.
- Comskip is not run on BBC channels (no adverts) and a result where almost half the recording is "adverts" is refused.
- Encoding is CPU x264; expect about one conversion at a time.

## Tvheadend facts learned in production

- API uses **digest** auth. Use separate limited users (one for tvhgo, one for the pipeline, one for Jellyfin) with
  restricted allowed networks. Clients that send basic auth in URLs (Jellyfin's plugin) need the `digest` config set to
  allow plain+digest.
- **Autorec (series rule) title is a PCRE2 regex** (lookaheads work), case-insensitive, matched against the EPG *title*
  only (not the subtitle). Rules live under `api/dvr/autorec/*`; edit one with `POST /api/idnode/save` and
  `node={"uuid":"…","title":"…"}`. After a change, check `api/dvr/entry/grid_upcoming` to confirm the expected
  programmes are `scheduled`.
- **Broadcasters truncate long titles in the EPG and push the rest into the subtitle.** Seen: ITV sends
  `New: The Martin Lewis Money Show..` (32 chars, two dots) with the subtitle `...Live - Christmas Special`; Channel 4
  sends `F1 Las Vegas GP Qualifying...` with the subtitle `...Highlights: …`. So a rule anchored with `$` or requiring a
  trailing word (`…Show Live$`, `…Highlights`) silently misses those shows, and only on some weeks. Write rules to
  match the stable *beginning* of the title, drop end anchors, and prefer a word boundary. Check the next week's EPG
  after writing a rule, and check new rules against the truncated form.
- Rules are per channel; use the HD channel's id so SD and +1 duplicates are not recorded as well.
- Channel 4 F1 (2026): highlights and qualifying highlights every race weekend, only the British GP live. The live
  Silverstone sessions include practice; the rule excludes titles containing `Practice` or `Pit Lane`. Revisit each
  season: coverage deals change.
- DVR entry/rule `removal` and `retention`: days, or 2147483646 = maintained space, 2147483647 = forever ("protected").
- Pathname format needs strftime-style codes (`%Y-%m-%d %H.%M.$x`), not `$Y/$H`.
- One tuner serves a whole multiplex. Recordings on the same mux share it; a third mux needs a free tuner. tvhgo
  warns about this.
- A recording with a lot of damaged packets is moved to *Failed* with the status text "Too many data errors" (the
  `status` field of the entry; `sched_status` stays `completed`; `data_errors` is the count, normally under a few hundred).
  The file is still there. The pipeline converts these (`process_damaged`) and tvhgo warns on playback. "Time missed"
  entries have no file and are ignored.
- DVB-T2 (HD) reception can be marginal and appear as "locked but all packets uncorrectable": suspect RF/USB (a
  splitter, a powered hub and a longer extension fixed one install), not firmware.
- Some USB tuners need firmware that the distribution's `linux-firmware` does not ship (e.g. Si2168 `b40` for the
  Hauppauge dualHD): install it to `/usr/lib/firmware`, replug, then restart the Tvheadend container.
- Audio-description tracks can be picked by players by mistake, which is why the pipeline strips them.
- The Docker default address pool can be exhausted on a host with many stacks; use `network_mode: bridge` or set
  `default-address-pools` in `daemon.json` (needs a Docker restart: plan it).

## Working here

- Do not commit secrets, real hostnames, IP addresses or credentials. `.env` and `pipeline/config.toml` are git-ignored;
  keep it that way. This repository is public.
- Documentation changes with behaviour: update the relevant file in `docs/` in the same commit.
- Keep the stack and tvhgo repos consistent: the library mount, the `.keep` marker and the `status.json` format are
  shared contracts.
- Commit messages: short imperative summary, body explains why; end with the `Co-Authored-By` trailer.
