#!/usr/bin/env python3
"""Find the advert breaks in new Freeview recordings and write them into the MP4s as "Commercial" chapters.

Cron (every 10 min) runs this via tvh-comskip-sync.sh. For each finished MP4 in the Jellyfin library folder it runs the
tvh-comskip container (Comskip + ffmpeg) once, then remembers the outcome in comskip-state/state.json.

  - Only recordings that appeared after comskip-state/since (set when this was installed) are touched, so nothing old
    is changed unless asked: `tvh-comskip-sync.py --files PATH [PATH...]` processes exactly those files.
  - BBC channels have no adverts and are skipped (channel read from the NFO written by tvh-nfo-sync).
  - At most MAX_PER_RUN recordings per run, one run at a time (lock), low CPU priority.
"""
import fcntl, json, os, re, subprocess, sys, time, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = "/mnt/8TB/tvheadend-recordings/_jellyfin"
STATE_DIR = os.path.join(HERE, "comskip-state")
STATE = os.path.join(STATE_DIR, "state.json")
SINCE = os.path.join(STATE_DIR, "since")
IMAGE = "tvh-comskip:1"
MAX_PER_RUN = 2
SETTLE_SECONDS = 12 * 60       # the pipeline has finished with a file when it has not changed for this long
NFO_WAIT_SECONDS = 2 * 3600    # wait this long for the NFO (which names the channel) before processing without it
MAX_ATTEMPTS = 3
NO_ADS = re.compile(r"^\s*BBC\b", re.I)


def log(msg):
    print("%s %s" % (time.strftime("%F %T"), msg), flush=True)


def load_state():
    try:
        return json.load(open(STATE))
    except (OSError, ValueError):
        return {}


def save_state(st):
    tmp = STATE + ".tmp"
    json.dump(st, open(tmp, "w"), indent=1, sort_keys=True)
    os.replace(tmp, STATE)


def studio(mp4):
    nfo = os.path.splitext(mp4)[0] + ".nfo"
    try:
        m = re.search(r"<studio>(.*?)</studio>", open(nfo, encoding="utf-8", errors="replace").read(), re.S)
        return m.group(1).strip() if m else ""
    except OSError:
        return None


def candidates(st, since, now):
    out = []
    for root, _dirs, files in os.walk(LIB):
        for f in files:
            if not f.endswith(".mp4") or f.startswith("."):
                continue
            p = os.path.join(root, f)
            try:
                mt = os.stat(p).st_mtime
            except OSError:
                continue
            rec = st.get(p, {})
            if rec.get("status") in ("ok", "already", "nobreaks", "skipped", "suspicious", "tooshort", "novideo", "gone"):
                continue
            if rec.get("status") == "error" and rec.get("attempts", 0) >= MAX_ATTEMPTS:
                continue
            if mt < since or now - mt < SETTLE_SECONDS:
                continue
            out.append((mt, p))
    return [p for _mt, p in sorted(out)]


def run_one(path):
    rel = os.path.relpath(path, LIB)
    cmd = ["docker", "run", "--rm", "--user", "1000:1000", "--cpus=2", "--memory=2g",
           "-v", "%s:/rec" % LIB, IMAGE, "tvh-comskip-apply", "/rec/" + rel]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3 * 3600)
    last = [l for l in r.stdout.splitlines() if l.startswith("RESULT ")]
    if not last:
        return "error", "no result (rc=%s) %s" % (r.returncode, (r.stderr or "")[-200:].strip())
    parts = last[-1][7:].split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    lock = open(os.path.join(STATE_DIR, "lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # a previous run is still working
    st = load_state()
    now = time.time()
    forced = False
    if "--files" in sys.argv:
        forced = True
        todo = [os.path.abspath(a) for a in sys.argv[sys.argv.index("--files") + 1:]]
    else:
        try:
            since = float(open(SINCE).read().strip())
        except (OSError, ValueError):
            since = now
            open(SINCE, "w").write("%d" % now)  # first run: from now on only
        todo = candidates(st, since, now)[:MAX_PER_RUN]

    for path in todo:
        name = os.path.basename(path)
        if not forced:
            s = studio(path)
            age = now - os.stat(path).st_mtime
            if s is None and age < NFO_WAIT_SECONDS:
                continue  # the NFO (with the channel) is not there yet
            if s and NO_ADS.match(s):
                st[path] = {"status": "skipped", "detail": "no adverts on " + s, "ts": int(now)}
                log("skipped %s (%s)" % (name, s))
                save_state(st)
                continue
        t0 = time.time()
        status, detail = run_one(path)
        rec = st.get(path, {})
        attempts = rec.get("attempts", 0) + (1 if status == "error" else 0)
        st[path] = {"status": status, "detail": detail, "ts": int(time.time()), "attempts": attempts}
        log("%s %s -> %s %s (%ds)" % ("forced" if forced else "new", name, status, detail, time.time() - t0))
        save_state(st)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # never let cron mail noise
        log("error: %r" % (e,))
        sys.exit(0)
