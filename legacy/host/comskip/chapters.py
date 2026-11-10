#!/usr/bin/env python3
"""Turn a Comskip EDL into an ffmpeg chapter file: "Commercial" for each advert break, "Part N" for the programme.

usage: chapters.py file.edl duration_seconds   (ffmetadata on stdout, a one-line summary on stderr)
exit 0 = chapters written, 3 = no usable breaks, 4 = result looks wrong (not applied)
"""
import sys

MIN_BREAK = 1.0       # shorter than this is noise (the lead-in before the programme can be a few seconds)
MERGE_GAP = 5.0       # two breaks closer than this are one break
MAX_BREAK_SHARE = 0.45  # more than this of the recording being "adverts" means Comskip got it wrong


def read_edl(path):
    out = []
    for line in open(path):
        p = line.split()
        if len(p) >= 2:
            try:
                out.append((float(p[0]), float(p[1])))
            except ValueError:
                pass
    return sorted(out)


def build(breaks, duration):
    cleaned = []
    for a, b in breaks:
        a, b = max(0.0, a), min(duration, b)
        if b - a >= MIN_BREAK:
            if cleaned and a - cleaned[-1][1] < MERGE_GAP:
                cleaned[-1] = (cleaned[-1][0], max(cleaned[-1][1], b))
            else:
                cleaned.append((a, b))
    return cleaned


def chapters(breaks, duration):
    ch, pos, n = [], 0.0, 1
    for a, b in breaks:
        if a - pos >= 1.0:
            ch.append((pos, a, "Part %d" % n))
            n += 1
        ch.append((a, b, "Commercial"))
        pos = b
    if duration - pos >= 1.0:
        ch.append((pos, duration, "Part %d" % n))
    return ch


def main():
    edl, duration = sys.argv[1], float(sys.argv[2])
    breaks = build(read_edl(edl), duration)
    if not breaks:
        print("breaks=0 seconds=0", file=sys.stderr)
        return 3
    total = sum(b - a for a, b in breaks)
    print("breaks=%d seconds=%d" % (len(breaks), round(total)), file=sys.stderr)
    if total > MAX_BREAK_SHARE * duration:
        return 4
    print(";FFMETADATA1")
    for a, b, title in chapters(breaks, duration):
        print("[CHAPTER]\nTIMEBASE=1/1000\nSTART=%d\nEND=%d\ntitle=%s" % (round(a * 1000), round(b * 1000), title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
