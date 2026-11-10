"""The main loop: ask Tvheadend for finished recordings, bring each through the steps, then the library-wide tidy-up."""
import logging
import os
import threading
import time

from . import paths, status as live_status
from .config import Config
from .state import State
from .steps import cleanup, comskip, nfo, series_images, strip_ad, thumb, to_mp4
from .tvheadend import Tvheadend

log = logging.getLogger("tvhpipeline")


def _settled(cfg, path: str, now: float) -> bool:
    try:
        return now - os.stat(path).st_mtime >= cfg.settle_seconds
    except OSError:
        return False


ACTIVITY = {"path": None}


def _set_activity(text: str):
    """What the pipeline is doing right now (shown by `status`; a long conversion can run for hours)."""
    p = ACTIVITY["path"]
    if not p:
        return
    try:
        if text:
            with open(p, "w") as f:
                f.write("%s since %s" % (text, time.strftime("%F %T")))
        elif os.path.exists(p):
            os.remove(p)
    except OSError:
        pass


def start_heartbeat(path: str, interval: float = 30.0) -> threading.Thread:
    """Touch `path` every `interval` seconds from a background thread, so the container reads as healthy even in the
    middle of a conversion that takes hours."""
    def beat():
        while True:
            try:
                with open(path, "w") as f:
                    f.write(str(int(time.time())))
            except OSError:
                pass
            live_status.refresh()
            time.sleep(interval)
    t = threading.Thread(target=beat, daemon=True, name="heartbeat")
    t.start()
    return t


def _attempt(state: State, cfg: Config, rec: str, step: str, fn, label: str, title: str = ""):
    """Run one step if it is due; remember the outcome. Returns the status (None if not attempted)."""
    if not state.due(rec, step, cfg.max_attempts):
        return None
    prev = state.get(rec, step)
    t0 = time.time()
    _set_activity("%s %s" % (step, label))
    live_status.begin(rec, title or label, step)
    try:
        status, detail = fn()
    except Exception as e:  # a bug or odd file must not stop the other recordings
        status, detail = "failed", "%s: %s" % (type(e).__name__, e)
    finally:
        _set_activity("")
        live_status.end()
    attempts = (prev["attempts"] if prev else 0) + (1 if status == "failed" else 0)
    state.put(rec, step, status, detail, attempts)
    log.info("%s %s -> %s %s (%.0fs)", step, label, status, detail, time.time() - t0)
    return status


def process_recording(cfg: Config, state: State, entry: dict, now: float) -> bool:
    """Bring one recording through the steps in order. Returns True if it did real work (so the caller can pace itself)."""
    ts = paths.to_local(cfg, entry.get("filename") or "")
    if not ts.endswith((".ts", ".mkv")) or not os.path.exists(ts) or os.path.getsize(ts) == 0 or not _settled(cfg, ts, now):
        return False
    rec = entry["uuid"]
    label = os.path.basename(ts)
    title = entry.get("disp_title") or label
    out = paths.mp4_for(cfg, ts)
    worked = False

    def did(s):
        return s not in (None, "exists", "none", "already")

    if cfg.strip_audio_description:
        worked |= did(_attempt(state, cfg, rec, "strip_ad", lambda: strip_ad.run(cfg, ts), label, title))
    if cfg.convert_mp4:
        worked |= did(_attempt(state, cfg, rec, "convert_mp4", lambda: to_mp4.run(cfg, ts, out), label, title))
    mp4_ready = os.path.exists(out) and os.path.getsize(out) > 0
    if cfg.thumbnail and mp4_ready:
        worked |= did(_attempt(state, cfg, rec, "thumbnail", lambda: thumb.run(cfg, out), label, title))
    if cfg.comskip and mp4_ready:
        if comskip.skip_channel(cfg, entry.get("channelname") or ""):
            if state.get(rec, "comskip") is None:
                state.put(rec, "comskip", "skipped", "no adverts on " + (entry.get("channelname") or ""))
        elif entry.get("stop", 0) >= cfg.comskip_since:
            worked |= did(_attempt(state, cfg, rec, "comskip", lambda: comskip.run(cfg, out), label, title))
    return worked


def _publish_lists(cfg: Config, state: State, entries: list, now: float):
    """What is waiting and what has failed, for the status file."""
    queue, failed = [], []
    for e in entries:
        ts = paths.to_local(cfg, e.get("filename") or "")
        if not ts.endswith((".ts", ".mkv")) or not os.path.exists(ts):
            continue
        rec, title = e["uuid"], e.get("disp_title") or os.path.basename(ts)
        wanted = [s for s, on in (("convert_mp4", cfg.convert_mp4), ("comskip", cfg.comskip and not comskip.skip_channel(cfg, e.get("channelname") or "")
                                                                          and e.get("stop", 0) >= cfg.comskip_since)) if on]
        waiting = []
        for step in wanted:
            st = state.get(rec, step)
            if st is None:
                waiting.append(step)
            elif st["status"] == "failed":
                retry = state.retry_at(rec, step, cfg.max_attempts)
                failed.append({"id": rec, "title": title, "step": step, "detail": st["detail"], "attempts": st["attempts"], "retry_at": retry})
                if retry is not None:
                    waiting.append(step)
        if waiting:
            queue.append({"id": rec, "title": title, "steps": waiting})
    live_status.set_lists(queue, failed)


def cycle(cfg: Config, state: State, tvh: Tvheadend, max_recordings: int = 1) -> dict:
    """One pass. At most `max_recordings` recordings get heavy work per pass, so the machine is never swamped."""
    now = time.time()
    entries = tvh.finished()
    entries.sort(key=lambda e: e.get("stop", 0))
    done = 0
    for e in entries:
        if done >= max_recordings:
            break
        if process_recording(cfg, state, e, now):
            done += 1
    _publish_lists(cfg, state, entries, now)
    info = {"recordings": len(entries), "worked": done}
    if cfg.nfo:
        written, missing = nfo.sync(cfg, entries)
        info.update(nfo_written=written, missing_mp4=missing)
    if cfg.cleanup:
        info["cleanup"] = cleanup.run(cfg)
    if cfg.series_images:
        try:
            info["series_images"] = series_images.run(cfg)
        except Exception as e:
            info["series_images"] = "error: %s" % e
    return info


def loop(cfg: Config):
    os.makedirs(cfg.state_dir, exist_ok=True)
    state = State(os.path.join(cfg.state_dir, "state.db"))
    tvh = Tvheadend(cfg.tvh_url, cfg.tvh_user, cfg.tvh_pass)
    heartbeat = os.path.join(cfg.state_dir, "heartbeat")
    ACTIVITY["path"] = os.path.join(cfg.state_dir, "activity")
    start_heartbeat(heartbeat)
    live_status.configure(os.path.join(cfg.state_dir, "status.json"))
    log.info("tvh-pipeline started: library=%s poll=%ss", cfg.library, cfg.poll_seconds)
    while True:
        try:
            info = cycle(cfg, state, tvh)
            if info.get("worked") or info.get("nfo_written") or any(info.get("cleanup", {}).get(k) for k in ("mp4", "thumb", "nfo", "dirs")):
                log.info("cycle %s", info)
        except Exception as e:
            log.error("cycle failed: %s: %s", type(e).__name__, e)
        time.sleep(cfg.poll_seconds)
