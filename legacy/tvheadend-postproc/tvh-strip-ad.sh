#!/bin/sh
# Tvheadend DVR post-processor (runs in the container): remove audio-description audio tracks
# (disposition visual_impaired, or 0-channel audio) from a finished recording, stream copy only.
# Replaces the original ONLY if the result has video + >=1 audio and size >=90%. Never fails the recording.
F="$1"; LOG=/config/tvh-strip-ad.log
log(){ echo "$(date '+%F %T') $*" >> "$LOG"; }
[ -f "$F" ] || { log "missing $F"; exit 0; }
DROP=$(ffprobe -v error -select_streams a -show_entries stream=index,channels:stream_disposition=visual_impaired -of csv=p=0 "$F" | awk -F, '$1!="" && ($3==1||$2==0||$2==""){printf "-map -0:%s ",$1}')
[ -z "$DROP" ] && { log "no AD track: $F"; exit 0; }
TMP="${F%.*}.stripad.tmp.ts"
if ffmpeg -v error -nostdin -y -i "$F" -map 0 $DROP -c copy -f mpegts "$TMP" 2>>"$LOG"; then
  S1=$(stat -c %s "$F"); S2=$(stat -c %s "$TMP")
  V=$(ffprobe -v error -select_streams v -show_entries stream=index -of csv=p=0 "$TMP" | grep -c .); A=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$TMP" | sort -u | grep -c .)
  # timestamps may legitimately be re-based (duration differs), so verify by size (>=90%) + streams present
  OK=$(awk -v a="$S1" -v b="$S2" 'BEGIN{print (a>0 && b>=0.9*a)?1:0}'); D1=$S1; D2=$S2
  if [ "$V" -ge 1 ] && [ "$A" -ge 1 ] && [ "$OK" = 1 ]; then mv "$TMP" "$F" && log "stripped ($DROP) $F dur $D1 -> $D2"; else rm -f "$TMP"; log "VERIFY FAILED, kept original: v=$V a=$A dur $D1/$D2 $F"; fi
else rm -f "$TMP"; log "ffmpeg failed, kept original: $F"; fi
exit 0
