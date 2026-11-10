"""ffmpeg / ffprobe helpers."""
import json
import subprocess

NICE = ["nice", "-n", "10"]


def run(cmd, timeout=None):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


class Result:
    def __init__(self, returncode, stderr):
        self.returncode, self.stderr = returncode, stderr


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
            elif "=" not in line.split(" ")[0] and line:
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
             "stream=index,codec_type,codec_name,channels:stream_disposition=visual_impaired", path])
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
