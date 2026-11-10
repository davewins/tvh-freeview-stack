# Tvheadend settings this stack relies on

Tvheadend keeps its settings in its `/config` folder (`TVH_CONFIG_DIR`). **That folder is the real backup.**
`tvheadend/export-config.sh` also writes the important parts as readable JSON (`tvheadend/config-snapshot/`) so they can
be reviewed and re-created by hand.

## Users (Configuration → Users → Access Entries)
Create dedicated users so nothing runs as admin:

| User | Used by | Needs |
| --- | --- | --- |
| `tvhgo` | tvhgo's connection to Tvheadend | Web interface; Streaming: *Basic* + *Advanced*; Video recorder: *Basic*, *View all*, *Manage all*, *Failed* |
| `pipeline` | the pipeline container (reads the list of finished recordings) | Web interface (Tvheadend refuses every API call without it); Video recorder: *Basic*, *View all*. Not admin, no streaming, no *Manage all* |
| `tvhgo-status` (optional) | tvhgo's tuner display and clash warnings | **Admin** (Tvheadend only shows tuner status and the channel→multiplex map to admins) plus Video recorder: *Basic*, *View all* (read-only, to list scheduled recordings). tvhgo uses it for read-only calls and nothing else; keep its password separate from the main `tvhgo` user and restrict *Allowed networks*. Leave `TVHGO_STATUS_*` empty to switch the feature off |
| `jellyfin` (optional) | Jellyfin's Live TV plugin | Streaming Basic + Advanced + HTSP; Video recorder Basic, HTSP, View all, Manage all, Failed |

Restrict *Allowed networks* to your LAN (and the docker bridge range if containers connect from there).
tvhgo's own users (who log in to the web interface) are separate and live in tvhgo's database.

## DVR profile (Configuration → Recording → Digital Video Recorder Profiles)
| Setting | Value | Why |
| --- | --- | --- |
| Recording system path | `/recordings` | the folder mounted in the compose file |
| File name format / subdirectories | `$t/$t - %Y-%m-%d %H.%M.$x`, create a subdirectory per title | one folder per programme; the pipeline mirrors this under `_jellyfin/` |
| Pre / post recording padding | 2 / 5 minutes | start slightly early, finish slightly late |
| Post-processor command | **empty** once the pipeline container is in use. While using the legacy scripts: `/bin/sh /config/tvh-post.sh "%f"` | see [pipeline.md](pipeline.md) |
| Retention | e.g. 365 days | the pipeline removes the MP4/NFO/thumbnail when the master is deleted |

## Series rules
tvhgo creates and lists them (DVR → Series rules); they are Tvheadend "autorec" entries and can also be edited in
Tvheadend (Configuration → Recording → Automatic Recorder Rules). A rule made by tvhgo is for one title on one channel,
skips repeats, and also matches the broadcaster's "New:" / "Final:" tagged titles.

## Export and back up
```
TVH_URL=http://host:9981 TVH_USER=admin TVH_PASS=... tvheadend/export-config.sh    # readable snapshot
TVH_CONFIG_DIR=/srv/tvheadend/config DEST=/mnt/backup/tvheadend ops/backup-tvheadend-config.sh   # real backup
```
