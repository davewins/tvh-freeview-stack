#!/bin/bash
# Export the Tvheadend settings that matter as readable JSON (so they can be reviewed, diffed and re-created).
# This is NOT a backup: the real backup is the Tvheadend /config folder (see ops/backup-tvheadend-config.sh).
# Usage: TVH_URL=http://host:9981 TVH_USER=admin TVH_PASS=... ./export-config.sh [output-dir]
set -eu
URL="${TVH_URL:?set TVH_URL, e.g. http://192.168.1.10:9981}"; OUT="${1:-$(dirname "$0")/config-snapshot}"
mkdir -p "$OUT"
get() { curl -fsS --digest -u "${TVH_USER:?}:${TVH_PASS:?}" "$URL$1"; }
pretty() { python3 -c 'import sys,json; print(json.dumps(json.load(sys.stdin), indent=1, sort_keys=True, ensure_ascii=False))'; }
# DVR profiles: storage path, file name format, padding, retention, post-processor command
get "/api/dvr/config/grid" | pretty > "$OUT/dvr-config.json"
# Series rules ("autorec")
get "/api/dvr/autorec/grid?limit=1000" | pretty > "$OUT/autorec.json"
# Channels: names, numbers, tags (EPG and picon settings come with them)
get "/api/channel/grid?limit=2000" | pretty > "$OUT/channels.json"
# Access entries (who may do what) WITHOUT passwords, so the users can be re-created with the right permissions
get "/api/access/entry/grid?limit=500" | python3 -c '
import sys,json
d=json.load(sys.stdin)
for e in d.get("entries",[]):
    for k in list(e):
        if "pass" in k.lower(): e[k]="<removed>"
print(json.dumps(d, indent=1, sort_keys=True, ensure_ascii=False))' > "$OUT/access-entries.json"
# Stream profiles used by the web player ("Auto" mode in tvhgo)
get "/api/profile/list" | pretty > "$OUT/stream-profiles.json" || true
# Server version
get "/api/serverinfo" | pretty > "$OUT/serverinfo.json"
echo "exported to $OUT"
