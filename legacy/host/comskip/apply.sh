#!/bin/sh
# tvh-comskip-apply <mp4>: find the advert breaks with Comskip and write them into the MP4 as chapters.
# Never leaves a half-written file: the new MP4 is made beside the original, checked, and only then moved over it.
# Last line printed is always "RESULT <status> [detail]" for the caller.
F="$1"
T=$(mktemp -d /tmp/cs.XXXXXX) || exit 1
trap 'rm -rf "$T"' EXIT
emit() { echo "RESULT $*"; exit 0; }

[ -f "$F" ] || emit missing
VID=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$F" | head -1)
[ -n "$VID" ] || emit novideo
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$F")
[ -n "$DUR" ] || emit unreadable
python3 -c "import sys; sys.exit(0 if float('$DUR')>=300 else 1)" || emit tooshort
if ffprobe -v error -show_entries chapter_tags=title -of csv=p=0 "$F" | grep -qi '^commercial'; then emit already; fi

nice -n 15 comskip --ini=/etc/tvh-comskip.ini --output="$T" --threads=2 "$F" >"$T/comskip.log" 2>&1
EDL="$T/$(basename "${F%.*}").edl"
[ -f "$EDL" ] || emit nobreaks 0
python3 /usr/local/bin/tvh-comskip-chapters.py "$EDL" "$DUR" >"$T/meta.txt" 2>"$T/summary.txt"
RC=$?
SUM=$(cat "$T/summary.txt")
[ $RC -eq 3 ] && emit nobreaks 0
[ $RC -eq 4 ] && emit suspicious "$SUM"
[ $RC -eq 0 ] || emit error "chapter builder rc=$RC"
NCH=$(grep -c '^\[CHAPTER\]' "$T/meta.txt")

# The temp name must NOT end in .mp4: tvh-nfo-sync treats any .mp4 without a matching recording as an orphan and deletes it
NEW="$F.comskip.part"
rm -f "$NEW"
ffmpeg -v error -y -i "$F" -i "$T/meta.txt" -map 0 -map_metadata 0 -map_chapters 1 -c copy -movflags +faststart -f mp4 "$NEW" 2>"$T/ffmpeg.err" \
  || { rm -f "$NEW"; emit error "ffmpeg failed: $(head -c 200 "$T/ffmpeg.err")"; }

# check the new file before it replaces the original
D2=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$NEW")
V2=$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name -of csv=p=0 "$NEW" | head -1)
A1=$(ffprobe -v error -select_streams a -show_entries stream=codec_name -of csv=p=0 "$F" | wc -l)
A2=$(ffprobe -v error -select_streams a -show_entries stream=codec_name -of csv=p=0 "$NEW" | wc -l)
C2=$(ffprobe -v error -show_chapters -of csv=p=0 "$NEW" | wc -l)
S1=$(stat -c %s "$F"); S2=$(stat -c %s "$NEW")
OK=$(python3 -c "d1=float('$DUR');d2=float('${D2:-0}');s1=$S1;s2=$S2
print(1 if abs(d1-d2)<0.5 and abs(s1-s2)/s1<0.01 and '$V2'=='$VID' and $A1==$A2 and $C2==$NCH else 0)")
if [ "$OK" != 1 ]; then rm -f "$NEW"; emit error "verify failed dur $DUR/$D2 size $S1/$S2 chapters $NCH/$C2"; fi
mv "$NEW" "$F" || { rm -f "$NEW"; emit error "could not replace"; }
emit ok "$SUM chapters=$NCH"
