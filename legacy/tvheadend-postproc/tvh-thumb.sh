#!/bin/sh
# Make a Jellyfin episode thumbnail "<name>-thumb.jpg" next to an MP4
# from a representative frame ~15% into the video. Idempotent; never fails the caller.
M="$1"; [ -f "$M" ] || exit 0
T="${M%.mp4}-thumb.jpg"; D=$(dirname "$M")
if [ ! -s "$T" ]; then
  DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$M" | cut -d. -f1); [ -n "$DUR" ] || DUR=600
  SS=$((DUR*15/100))
  ffmpeg -nostdin -v error -y -ss "$SS" -i "$M" -vf "thumbnail=150,scale=1280:-2" -frames:v 1 -q:v 3 "$T.tmp.jpg" && mv "$T.tmp.jpg" "$T" || rm -f "$T.tmp.jpg"
fi
exit 0
