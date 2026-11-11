"""Tidy the library: remove what belongs to recordings that no longer exist (Tvheadend's retention deleted the master).

Safety: it only ever deletes inside the library folder, only ever deletes known kinds of file, never touches work-in-
progress files (.part/.tmp), and does nothing at all if the recordings folder looks empty or unmounted.

An MP4 with a "<name>.keep" marker next to it is deliberately kept after its recording was deleted (tvhgo's "delete,
keep the MP4 copy"): it, and the thumbnail / NFO / folder image that go with it, are left alone."""
import os

from .. import paths

KEEP_SUFFIX = ".keep"


def recordings_look_mounted(cfg) -> bool:
    for _root, _dirs, files in os.walk(cfg.recordings):
        for f in files:
            if f.endswith((".ts", ".mkv")):
                return True
    return False


def run(cfg, dry_run: bool = False):
    """Returns a dict of what was (or would be) removed."""
    out = {"mp4": 0, "thumb": 0, "nfo": 0, "folder_jpg": 0, "dirs": 0, "skipped": ""}
    if not os.path.isdir(cfg.library):
        return out
    if not recordings_look_mounted(cfg):
        out["skipped"] = "no recordings found under %s: not cleaning" % cfg.recordings
        return out

    def remove(p, key):
        out[key] += 1
        if not dry_run:
            os.remove(p)

    # MP4 copies whose master no longer exists (and that are not being written)
    for root, _dirs, files in os.walk(cfg.library):
        for fn in files:
            if fn.endswith(paths.TEMP_SUFFIXES) or not fn.endswith(".mp4"):
                continue
            p = os.path.join(root, fn)
            if os.path.exists(p[: -len(".mp4")] + KEEP_SUFFIX):
                continue
            if not os.path.exists(paths.ts_for_mp4(cfg, p)) and not os.path.exists(p + ".part"):
                remove(p, "mp4")
    # thumbnails, episode NFOs whose MP4 is gone; folder.jpg in a folder with no MP4 left
    for root, _dirs, files in os.walk(cfg.library):
        has_mp4 = any(f.endswith(".mp4") for f in files)
        for fn in files:
            p = os.path.join(root, fn)
            if fn.endswith(paths.TEMP_SUFFIXES):
                continue
            if fn.endswith("-thumb.jpg") and not os.path.exists(p[: -len("-thumb.jpg")] + ".mp4"):
                remove(p, "thumb")
            elif fn.endswith(".nfo") and fn != "tvshow.nfo" and not os.path.exists(p[: -len(".nfo")] + ".mp4"):
                remove(p, "nfo")
            elif fn == "folder.jpg" and not has_mp4:
                remove(p, "folder_jpg")
    if not dry_run:
        for root, _dirs, _files in os.walk(cfg.library, topdown=False):
            if root != cfg.library and not os.listdir(root):
                os.rmdir(root)
                out["dirs"] += 1
    return out
