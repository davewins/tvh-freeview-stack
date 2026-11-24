"""ffmpeg / ffprobe helpers."""
import json
import subprocess

NICE = ["nice", "-n", "10"]


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class Result:
    def __init__(self, returncode, stderr):
        self.returncode, self.stderr = returncode, stderr


# per-macroblock decoder chatter: a damaged recording produces thousands of these and they bury the real error
NOISE = ("cabac", "decoding MB", "PPS", "decode_slice", "no frame", "Last message", "concealing", "block unavailable",
         "Reference", "reordering", "modification", "aac_latm", "mmco", "Missing reference", "out of range")


def run_progress(cmd, total_seconds, on_progress, timeout=None):
    """Run an ffmpeg command that was given `-progress pipe:1` and report how far it got (0-100) as it runs.
    Errors (ffmpeg is started with -v error) come back in `.stderr`."""
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    errors = []
    try:
        for line in p.stdout:
            line = line.strip()
            if line.startswith("out_time_us=") or line.startswith("out_time_ms="):  # both are in microseconds
                try:
                    us = int(line.split("=", 1)[1])
                except ValueError:
                    continue
                if total_seconds and us > 0:
                    on_progress(min(99.9, us / 1e6 / total_seconds * 100))
            elif "=" not in line.split(" ")[0] and line and not any(n in line for n in NOISE):
                errors.append(line)
        p.wait(timeout=timeout)
    except Exception:
        p.kill()
        raise
    return Result(p.returncode, "\n".join(errors[-20:]))


def duration(path: str):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    try:
        return float(r.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


def streams(path: str):
    r = run(["ffprobe", "-v", "error", "-of", "json", "-show_entries",
             "stream=index,codec_type,codec_name,channels,duration:stream_disposition=visual_impaired", path])
    try:
        return json.loads(r.stdout).get("streams", [])
    except ValueError:
        return []


def count(path: str, kind: str) -> int:
    return sum(1 for s in streams(path) if s.get("codec_type") == kind)


def first_codec(path: str, kind: str):
    for s in streams(path):
        if s.get("codec_type") == kind:
            return s.get("codec_name")
    return None


def leading_gap(path: str, window: int = 120, minimum: float = 5.0) -> float:
    """Seconds of nothing at the start of a recording: the tuner delivered a stray packet or two, then no data until
    later (seen when a recording starts as another one takes the tuner). The container duration counts that hole, the
    converted file correctly does not. Looks at the first `window` seconds only."""
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-read_intervals", "%%+%d" % window,
             "-show_entries", "packet=pts_time", "-of", "csv=p=0", path])
    times = sorted(float(x) for x in r.stdout.replace(",", " ").split() if _isnum(x))
    gap = 0.0
    for a, b in zip(times, times[1:]):
        if b - a >= minimum:
            gap = max(gap, b - a)
    return gap


def _isnum(x: str) -> bool:
    try:
        float(x)
        return True
    except ValueError:
        return False


def chapter_titles(path: str):
    r = run(["ffprobe", "-v", "error", "-of", "json", "-show_chapters", path])
    try:
        return [(c.get("tags") or {}).get("title", "") for c in json.loads(r.stdout).get("chapters", [])]
    except ValueError:
        return []


def start_lead(path: str) -> float:
    """Seconds by which the first video frame comes after the first audio sample (0 if video is not later). ffmpeg moves
    both streams to start at zero, which would show the video that much too early for the whole programme."""
    def start(kind):
        r = run(["ffprobe", "-v", "error", "-select_streams", kind + ":0", "-show_entries", "stream=start_time", "-of", "csv=p=0", path])
        try:
            return float(r.stdout.strip().splitlines()[0])
        except (ValueError, IndexError):
            return None
    v, a = start("v"), start("a")
    if v is None or a is None:
        return 0.0
    d = v - a
    return round(d, 3) if 0.04 < d < 10 else 0.0


def has_timestamp_jump(path: str, limit: float = 60.0) -> bool:
    """True if the video's timestamps jump by more than `limit` seconds anywhere (one corrupt packet is enough to make
    ffmpeg cut the programme short or run out of memory), even when Tvheadend did not call the recording damaged."""
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "packet=pts_time", "-of", "csv=p=0", path], timeout=1800)
    prev = None
    for x in r.stdout.split():
        try:
            t = float(x.strip(","))
        except ValueError:
            continue
        if prev is not None and abs(t - prev) > limit:
            return True
        prev = t
    return False
