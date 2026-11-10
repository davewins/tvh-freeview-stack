"""Turn a Comskip EDL into an ffmpeg chapter file: "Commercial" for each advert break, "Part N" for the programme.

Exit-style result: ("ok", ffmetadata, summary) | ("none", "", summary) | ("suspicious", "", summary)"""

MIN_BREAK = 1.0         # shorter than this is noise
MERGE_GAP = 5.0         # two breaks closer than this are one break
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


def clean(breaks, duration):
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


def build(edl_path, duration):
    breaks = clean(read_edl(edl_path), duration)
    if not breaks:
        return "none", "", "breaks=0 seconds=0"
    total = sum(b - a for a, b in breaks)
    summary = "breaks=%d seconds=%d" % (len(breaks), round(total))
    if total > MAX_BREAK_SHARE * duration:
        return "suspicious", "", summary
    lines = [";FFMETADATA1"]
    for a, b, title in chapters(breaks, duration):
        lines.append("[CHAPTER]\nTIMEBASE=1/1000\nSTART=%d\nEND=%d\ntitle=%s" % (round(a * 1000), round(b * 1000), title))
    return "ok", "\n".join(lines) + "\n", summary
