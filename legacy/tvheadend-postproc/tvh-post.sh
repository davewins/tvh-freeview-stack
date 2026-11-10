#!/bin/sh
# Tvheadend DVR post-processor wrapper: (1) strip audio-description tracks from the .ts (in place),
# (2) make a Jellyfin-friendly MP4 copy under /recordings/_jellyfin/<same relative path>.mp4.
# The .ts stays the master (Tvheadend/TvhClient point at it). Never fails the recording (exit 0).
F="$1"; LOG=/config/tvh-strip-ad.log
/bin/sh /config/tvh-strip-ad.sh "$F"
case "$F" in /recordings/*) REL="${F#/recordings/}"; REL="${REL%.*}";; *) exit 0;; esac
OUT="/recordings/_jellyfin/$REL.mp4"
mkdir -p "$(dirname "$OUT")"
if R=$(/bin/sh /config/tvh-to-mp4.sh "$F" "$OUT" 2>&1); then echo "$(date '+%F %T') mp4 $R" >> "$LOG"
else echo "$(date '+%F %T') MP4 FAILED for $F: $R" >> "$LOG"; fi
exit 0
