#!/bin/sh
# Convert a Tvheadend .ts recording to a Jellyfin-friendly MP4 (H.264 + AAC, faststart, square pixels).
# Usage: tvh-to-mp4.sh in.ts out.mp4   (writes out.mp4.part then renames; exits non-zero on failure)
IN="$1"; OUT="$2"; PART="$OUT.part"
[ -f "$IN" ] && [ -n "$OUT" ] || { echo "usage: $0 in.ts out.mp4" >&2; exit 2; }
VC=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$IN" | head -1)
# Always re-encode with a keyframe every ~2s and closed GOPs: a straight copy of broadcast H.264 contains
# keyframes browsers cannot start from, so seeking in Chrome/Jellyfin web failed on HD recordings.
GOP="-g 50 -keyint_min 50 -sc_threshold 0 -x264-params open-gop=0 -pix_fmt yuv420p"
if [ "$VC" = "h264" ]; then
  # HD: deinterlace only frames flagged interlaced, keep resolution
  VOPT="-vf yadif=0:-1:1 -c:v libx264 -preset veryfast -crf 22 $GOP"
else
  # SD MPEG-2: deinterlace, convert anamorphic 544x576 to square-pixel 1024x576
  VOPT="-vf yadif=0:-1:0,scale=1024:576:flags=lanczos,setsar=1 -c:v libx264 -preset medium -crf 20 $GOP"
fi
rm -f "$PART"
nice -n 10 ffmpeg -nostdin -v error -y -fflags +genpts -i "$IN" -map 0:v:0 -map 0:a:0 $VOPT \
  -c:a aac -b:a 192k -ac 2 -sn -dn -movflags +faststart -f mp4 "$PART" || { rm -f "$PART"; echo "ffmpeg failed" >&2; exit 1; }
# verify: has video+audio, duration within 2% of the source
D1=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
D2=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$PART")
NV=$(ffprobe -v error -select_streams v -show_entries stream=index -of csv=p=0 "$PART" | wc -l)
NA=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$PART" | wc -l)
OKD=$(awk -v a="$D1" -v b="$D2" 'BEGIN{d=a-b; if(d<0)d=-d; print (a>0 && d/a<0.02)?1:0}')
if [ "$NV" -ge 1 ] && [ "$NA" -ge 1 ] && [ "$OKD" = 1 ]; then mv "$PART" "$OUT"; /bin/sh /config/tvh-thumb.sh "$OUT"; echo "ok $OUT dur $D1 -> $D2 ($VC)"; else rm -f "$PART"; echo "verify failed v=$NV a=$NA dur $D1 -> $D2" >&2; exit 1; fi
