"""Where a recording's files live."""
import os

TEMP_SUFFIXES = (".part", ".tmp")  # work-in-progress files: never ending in .mp4, never touched by cleanup


def to_local(cfg, tvh_path: str) -> str:
    """Tvheadend reports its own path; map it to where this container sees the same file."""
    if tvh_path.startswith(cfg.tvheadend_root + "/"):
        return cfg.recordings + tvh_path[len(cfg.tvheadend_root):]
    return tvh_path


def rel(cfg, local_ts: str) -> str:
    """Path of the recording below the recordings folder, without extension."""
    return os.path.splitext(os.path.relpath(local_ts, cfg.recordings))[0]


def mp4_for(cfg, local_ts: str) -> str:
    return os.path.join(cfg.library, rel(cfg, local_ts) + ".mp4")


def ts_for_mp4(cfg, mp4: str):
    """The master recording an MP4 in the library came from (the .ts, or .mkv if that is what exists)."""
    base = os.path.join(cfg.recordings, os.path.relpath(os.path.splitext(mp4)[0], cfg.library))
    for ext in (".ts", ".mkv"):
        if os.path.exists(base + ext):
            return base + ext
    return base + ".ts"
