#!/usr/bin/python3
"""Runs INSIDE the tvheadend container (as uid 1000): writes Jellyfin .nfo files next to
finished recordings so a Jellyfin 'Shows' library shows programme -> recordings with metadata.
Env: TVH_USER, TVH_PASS. Exit non-zero on any failure (wrapper logs it)."""
import os, sys, json, time, urllib.request
from xml.sax.saxutils import escape as x
B = "http://127.0.0.1:9981"
pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
pm.add_password(None, B, os.environ["TVH_USER"], os.environ["TVH_PASS"])
op = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(pm))
ents = json.load(op.open(B + "/api/dvr/entry/grid_finished?limit=5000", timeout=30))["entries"]

def write(path, text):
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return 0
    tmp = path + ".tmp"
    open(tmp, "w", encoding="utf-8").write(text)
    os.replace(tmp, path)
    return 1

JF = "/recordings/_jellyfin"
def mp4_for(ts):
    return os.path.join(JF, os.path.relpath(os.path.splitext(ts)[0], "/recordings") + ".mp4")
wrote = 0; wanted = set(); missing = 0
shows = {}
for e in ents:
    f = e.get("filename") or ""
    if not f.endswith((".ts", ".mkv")) or not os.path.exists(f) or os.path.getsize(f) == 0:
        continue
    mp4 = mp4_for(f)
    if not os.path.exists(mp4):
        missing += 1; print("MISSING MP4 for", f); continue
    e["_mp4"] = mp4
    shows.setdefault(os.path.dirname(mp4), []).append(e)
for d, es in shows.items():
    title = es[0].get("disp_title") or os.path.basename(d)
    plot = next((e.get("disp_description") or e.get("disp_subtitle") for e in es if e.get("disp_description") or e.get("disp_subtitle")), "")
    p = os.path.join(d, "tvshow.nfo"); wanted.add(p)
    wrote += write(p, '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<tvshow>\n  <title>%s</title>\n  <plot>%s</plot>\n</tvshow>\n' % (x(title), x(plot)))
    es.sort(key=lambda e: e["start"]); cnt = {}
    for e in es:
        t = time.localtime(e["start"]); y = t.tm_year; cnt[y] = cnt.get(y, 0) + 1
        sub = e.get("disp_subtitle") or ""; desc = e.get("disp_description") or ""
        plot = (sub + ("\n\n" if sub and desc else "") + desc).strip()
        et = time.strftime("%a %d %b %Y %H:%M", t) + " · " + (e.get("channelname") or "")
        runtime = max(1, (e["stop"] - e["start"]) // 60)
        genre = "".join("  <genre>%s</genre>\n" % x(str(g)) for g in (e.get("genre") or []) if isinstance(g, str))
        n = os.path.splitext(e["_mp4"])[0] + ".nfo"; wanted.add(n)
        wrote += write(n, '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<episodedetails>\n  <title>%s</title>\n  <showtitle>%s</showtitle>\n  <season>%d</season>\n  <episode>%d</episode>\n  <aired>%s</aired>\n  <runtime>%d</runtime>\n  <studio>%s</studio>\n  <plot>%s</plot>\n%s</episodedetails>\n'
            % (x(et), x(title), y, cnt[y], time.strftime("%Y-%m-%d", t), runtime, x(e.get("channelname") or ""), x(plot), genre))
# remove orphaned nfo anywhere under /recordings (incl. old ones beside the .ts), and orphaned
# MP4 copies whose master .ts no longer exists (Tvheadend retention deleted it). Only .nfo/.mp4, only under /recordings/_jellyfin for mp4.
removed = 0; mp4_removed = 0
for root, _, files in os.walk(JF):
    for fn in files:
        if fn.endswith(".mp4"):
            p = os.path.join(root, fn)
            src = "/recordings/" + os.path.relpath(os.path.splitext(p)[0], JF) + ".ts"
            if not os.path.exists(src) and not os.path.exists(os.path.splitext(p)[0] + ".mp4.part"):
                os.remove(p); mp4_removed += 1
# orphaned thumbnails: "<name>-thumb.jpg" whose MP4 is gone, and folder.jpg in a folder with no MP4 left
for root, _, files in os.walk(JF):
    for fn in files:
        p = os.path.join(root, fn)
        if fn.endswith("-thumb.jpg") and not os.path.exists(p[:-len("-thumb.jpg")] + ".mp4"):
            os.remove(p); removed += 1
        elif fn == "folder.jpg" and not any(f.endswith(".mp4") for f in files):
            os.remove(p); removed += 1
for root, dirs, files in os.walk(JF, topdown=False):
    if root != JF and not os.listdir(root):
        os.rmdir(root)
for root, _, files in os.walk("/recordings"):
    for fn in files:
        p = os.path.join(root, fn)
        if fn.endswith(".nfo") and p not in wanted:
            os.remove(p); removed += 1
print("recordings=%d shows=%d nfo_written=%d orphans_removed=%d mp4_removed=%d missing_mp4=%d" % (sum(len(v) for v in shows.values()), len(shows), wrote, removed, mp4_removed, missing))
sys.exit(0)
