"""Convert a .ts recording to a Jellyfin- and browser-friendly MP4 (H.264 + AAC, faststart, square pixels).

Always re-encoded with a keyframe every ~2 s and closed GOPs: a straight copy of broadcast H.264 has keyframes browsers
cannot start from, which broke seeking in Chrome and Jellyfin's web client on HD recordings."""
import os

from .. import media, status

GOP = ["-g", "50", "-keyint_min", "50", "-sc_threshold", "0", "-x264-params", "open-gop=0", "-pix_fmt", "yuv420p"]


# A recording damaged by poor reception loses stretches of data, so its MP4 is legitimately shorter than the file's
# container says. Accept it if at least this much of the source survived.
DAMAGED_MIN_KEPT = 0.8


def run(cfg, ts: str, out: str, damaged: bool = False):
    """Returns (status, detail): exists | ok | novideo | failed. `damaged` relaxes the length check (see above)."""
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return "exists", ""
    codec = media.first_codec(ts, "video")
    if codec is None:
        return "novideo", "audio-only recording"
    if codec == "h264":  # HD: deinterlace only frames flagged interlaced, keep the resolution
        vopt = ["-vf", "yadif=0:-1:1", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22"] + GOP
    else:  # SD MPEG-2: deinterlace, turn anamorphic 544x576 into square-pixel 1024x576
        vopt = ["-vf", "yadif=0:-1:0,scale=1024:576:flags=lanczos,setsar=1", "-c:v", "libx264", "-preset", "medium", "-crf", "20"] + GOP
    if damaged:
        # broken timestamps in a damaged tail can make ffmpeg pad the gap with duplicate frames for far longer than the
        # programme (observed: a 24 minute recording still encoding after 40 minutes, output growing): cap the output
        src = media.duration(ts)
        if src:
            vopt += ["-t", "%d" % (src + 5)]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    part = out + ".part"  # never ends in .mp4
    _rm(part)
    cmd = media.NICE + ["ffmpeg", "-nostdin", "-v", "error", "-y", "-progress", "pipe:1", "-nostats", "-fflags", "+genpts", "-i", ts, "-map", "0:v:0", "-map", "0:a:0"] + vopt + [
        "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-sn", "-dn", "-movflags", "+faststart", "-f", "mp4", part]
    r = media.run_progress(cmd, media.duration(ts), status.progress)
    if r.returncode != 0:
        _rm(part)
        return "failed", "ffmpeg: " + r.stderr.strip()[-200:]
    d1, d2 = media.duration(ts), media.duration(part)
    if d1 and d2 and abs(d1 - d2) / d1 >= 0.02:
        # a hole at the start of the source (no data for a while) is not lost video: allow for exactly that much
        d1 -= media.leading_gap(ts)
    if damaged and d1 and d2 and d1 > 0:
        length_ok = DAMAGED_MIN_KEPT <= d2 / d1 < 1.02
    else:
        length_ok = bool(d1 and d2 and d1 > 0 and abs(d1 - d2) / d1 < 0.02)
    ok = media.count(part, "video") >= 1 and media.count(part, "audio") >= 1 and length_ok
    if not ok:
        _rm(part)
        return "failed", "verification failed (duration %s -> %s)" % (d1, d2)
    os.replace(part, out)
    note = " (damaged source, shorter)" if damaged and d1 and abs(d1 - d2) / d1 >= 0.02 else ""
    return "ok", "%s %.0fs -> %.0fs%s" % (codec, d1, d2, note)


def _rm(p):
    try:
        os.remove(p)
    except OSError:
        pass
