"""Remove audio-description audio tracks from the recording itself (stream copy, in place, verified)."""
import os

from .. import media


def run(cfg, ts: str):
    """Returns (status, detail): none | ok | failed."""
    drop = []
    for s in media.streams(ts):
        if s.get("codec_type") != "audio":
            continue
        if (s.get("disposition") or {}).get("visual_impaired") == 1 or not s.get("channels"):
            drop += ["-map", "-0:%d" % s["index"]]
    if not drop:
        return "none", ""
    tmp = ts + ".stripad.part"
    r = media.run(["ffmpeg", "-v", "error", "-nostdin", "-y", "-i", ts, "-map", "0"] + drop + ["-c", "copy", "-f", "mpegts", tmp])
    if r.returncode != 0:
        _rm(tmp)
        return "failed", "ffmpeg: " + r.stderr.strip()[-200:]
    s1, s2 = os.path.getsize(ts), os.path.getsize(tmp)
    ok = media.count(tmp, "video") >= 1 and media.count(tmp, "audio") >= 1 and s1 > 0 and s2 >= 0.9 * s1
    if not ok:
        _rm(tmp)
        return "failed", "verification failed (size %d -> %d)" % (s1, s2)
    os.replace(tmp, ts)
    return "ok", "dropped %d track(s)" % (len(drop) // 2)


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass
