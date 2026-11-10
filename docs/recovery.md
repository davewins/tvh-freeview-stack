# If the machine is lost

Everything that is not a recording can be rebuilt from this repository plus **one backup: Tvheadend's `/config`
folder**. The recordings themselves live on their own disk; if that survived, plug it into the new machine.

## What to back up (and where each thing lives)
| What | Where | Why it matters |
| --- | --- | --- |
| **Tvheadend config folder** (`TVH_CONFIG_DIR`) | on the host | Channels, tuner scan, EPG settings, DVR profile, series rules, users. Without it you re-scan and re-create everything. Back it up with `ops/backup-tvheadend-config.sh` (or point your backup tool at it) |
| Recordings (`RECORDINGS_DIR`) | on the host | The `.ts` masters. The MP4/NFO/thumbnails under `_jellyfin/` can be rebuilt by the pipeline, so they are lower priority |
| tvhgo data (`TVHGO_DATA_DIR`) | on the host | tvhgo's users and sessions (small). The cache inside it can be dropped |
| `.env` and `pipeline/config.toml` | **not in git** | Passwords and your settings. Keep a copy in a password manager |
| Jellyfin config | Jellyfin's own folder | Library settings, users, Intro Skipper plugin and its settings |
| This repository | GitHub | Compose file, pipeline, scripts, docs, a readable snapshot of the Tvheadend settings |

## Rebuild, in order
1. Install Docker. Clone this repository. Plug in the tuner and recordings disk.
2. Create the folders from `.env.example`, restore the **Tvheadend config backup** into `TVH_CONFIG_DIR` and `chown -R 1000:1000` it.
   (No backup? Do the first-run wizard again and use `tvheadend/config-snapshot/` and [tvheadend.md](tvheadend.md) as the guide.)
3. `cp .env.example .env`, fill it in. Build the `tvhgo-player` image ([install.md](install.md)).
4. `docker compose up -d`. Check Tvheadend shows your channels and the tuner, and that the DVR profile's post-processor
   command matches how you run the pipeline ([pipeline.md](pipeline.md)).
5. Start the pipeline (`--profile pipeline`). It rebuilds anything missing under `_jellyfin/` from the masters. This can
   take a long time for a big library; it works through them one at a time.
6. Reinstall Jellyfin, re-add the library, reinstall the Intro Skipper plugin and apply the settings in [jellyfin.md](jellyfin.md).
7. Recreate tvhgo's users in its Settings.

## Test it
A backup you have never restored is a hope, not a backup. Once, on another machine or in a scratch folder, restore the
Tvheadend config, start only the `tvheadend` container, and confirm the channels and series rules appear.
