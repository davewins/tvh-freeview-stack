"""Episode thumbnail "<name>-thumb.jpg" next to the MP4, from a representative frame ~15% in."""
import os

from .. import media


def run(cfg, mp4: str):
    thumb = mp4[: -len(".mp4")] + "-thumb.jpg"
    if os.path.exists(thumb) and os.path.getsize(thumb) > 0:
        return "exists", ""
    dur = media.duration(mp4) or 600
    tmp = thumb + ".part"
    r = media.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", str(int(dur * 15 / 100)), "-i", mp4,
                   "-vf", "thumbnail=150,scale=1280:-2", "-frames:v", "1", "-q:v", "3", "-f", "image2", tmp])
    if r.returncode != 0 or not os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
        return "failed", "ffmpeg: " + r.stderr.strip()[-150:]
    os.replace(tmp, thumb)
    return "ok", ""
