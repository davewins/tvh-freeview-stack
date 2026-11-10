"""Find the advert breaks with Comskip and write them into the MP4 as chapters (verified before the file is replaced)."""
import os
import re
import tempfile

from .. import media
from . import adbreaks


def skip_channel(cfg, channel: str) -> bool:
    return bool(cfg.comskip_skip_channels and re.search(cfg.comskip_skip_channels, channel or "", re.I))


def run(cfg, mp4: str):
    """Returns (status, detail): ok | already | nobreaks | suspicious | tooshort | novideo | failed."""
    if not os.path.exists(mp4):
        return "failed", "mp4 missing"
    if media.first_codec(mp4, "video") is None:
        return "novideo", ""
    dur = media.duration(mp4)
    if not dur:
        return "failed", "unreadable"
    if dur < 300:
        return "tooshort", ""
    if any(t.lower().startswith("commercial") for t in media.chapter_titles(mp4)):
        return "already", ""
    with tempfile.TemporaryDirectory(prefix="comskip.") as tmp:
        r = media.run(media.NICE + ["comskip", "--ini=" + cfg.comskip_ini, "--output=" + tmp, "--threads=2", mp4], timeout=3 * 3600)
        edl = os.path.join(tmp, os.path.splitext(os.path.basename(mp4))[0] + ".edl")
        if not os.path.exists(edl):
            return "nobreaks", "comskip rc=%s" % r.returncode
        status, meta, summary = adbreaks.build(edl, dur)
        if status != "ok":
            return ("nobreaks" if status == "none" else status), summary
        meta_file = os.path.join(tmp, "meta.txt")
        open(meta_file, "w").write(meta)
        nchap = meta.count("[CHAPTER]")
        new = mp4 + ".comskip.part"  # must not end in .mp4: cleanup treats stray .mp4 files as orphans
        r = media.run(["ffmpeg", "-v", "error", "-y", "-i", mp4, "-i", meta_file, "-map", "0", "-map_metadata", "0",
                       "-map_chapters", "1", "-c", "copy", "-movflags", "+faststart", "-f", "mp4", new], timeout=3 * 3600)
        if r.returncode != 0:
            _rm(new)
            return "failed", "ffmpeg: " + r.stderr.strip()[-200:]
        d2, s1, s2 = media.duration(new), os.path.getsize(mp4), os.path.getsize(new)
        ok = (d2 and abs(dur - d2) < 0.5 and abs(s1 - s2) / s1 < 0.01
              and media.first_codec(new, "video") == media.first_codec(mp4, "video")
              and media.count(new, "audio") == media.count(mp4, "audio") and len(media.chapter_titles(new)) == nchap)
        if not ok:
            _rm(new)
            return "failed", "verification failed (duration %s/%s size %d/%d)" % (dur, d2, s1, s2)
        os.replace(new, mp4)
        return "ok", "%s chapters=%d" % (summary, nchap)


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass
