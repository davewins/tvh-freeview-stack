"""A small JSON status file (what is being converted now, how far, what is waiting, what failed) for tvhgo or anything
else that wants to show progress. Written atomically; harmless if nothing reads it."""
import json
import os
import threading
import time

_LOCK = threading.Lock()
_S = {"path": None, "current": None, "queue": [], "failed": [], "last_write": 0.0}


def configure(path: str):
    _S["path"] = path
    _write(force=True)


def _write(force: bool = False):
    p = _S["path"]
    now = time.time()
    if not p or (not force and now - _S["last_write"] < 2.0):
        return
    doc = {"updated": int(now), "current": _S["current"], "queue": _S["queue"], "failed": _S["failed"]}
    try:
        tmp = p + ".tmp"
        with open(tmp, "w") as f:
            json.dump(doc, f)
        os.replace(tmp, p)
        _S["last_write"] = now
    except OSError:
        pass


def begin(rec: str, title: str, step: str):
    with _LOCK:
        _S["current"] = {"id": rec, "title": title, "step": step, "percent": None, "since": int(time.time())}
        _write(force=True)


def progress(percent: float):
    with _LOCK:
        if _S["current"] is not None:
            _S["current"]["percent"] = max(0, min(100, round(percent, 1)))
            _write()


def end():
    with _LOCK:
        _S["current"] = None
        _write(force=True)


def set_lists(queue: list, failed: list):
    with _LOCK:
        _S["queue"], _S["failed"] = queue, failed
        _write(force=True)


def refresh():
    """Called by the heartbeat so `updated` keeps moving while a long step runs."""
    with _LOCK:
        _write(force=True)


def snapshot() -> dict:
    with _LOCK:
        return {"current": _S["current"], "queue": list(_S["queue"]), "failed": list(_S["failed"])}
