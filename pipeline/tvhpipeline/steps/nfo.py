"""Jellyfin .nfo files: a tvshow.nfo per programme folder and an episode .nfo per recording, so a Jellyfin "Shows"
library lists programme -> recordings with their metadata. Output format matches the legacy tvh-nfo-sync."""
import os
import time
from xml.sax.saxutils import escape as x

from .. import paths


def _write(path: str, text: str) -> int:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return 0
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return 1


def episode_nfo(title, year, number, entry, start_struct):
    sub = entry.get("disp_subtitle") or ""
    desc = entry.get("disp_description") or ""
    plot = (sub + ("\n\n" if sub and desc else "") + desc).strip()
    et = time.strftime("%a %d %b %Y %H:%M", start_struct) + " · " + (entry.get("channelname") or "")
    runtime = max(1, (entry["stop"] - entry["start"]) // 60)
    genre = "".join("  <genre>%s</genre>\n" % x(str(g)) for g in (entry.get("genre") or []) if isinstance(g, str))
    return (
        '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<episodedetails>\n  <title>%s</title>\n  <showtitle>%s</showtitle>\n'
        "  <season>%d</season>\n  <episode>%d</episode>\n  <aired>%s</aired>\n  <runtime>%d</runtime>\n  <studio>%s</studio>\n"
        "  <plot>%s</plot>\n%s</episodedetails>\n"
        % (x(et), x(title), year, number, time.strftime("%Y-%m-%d", start_struct), runtime, x(entry.get("channelname") or ""), x(plot), genre)
    )


def show_nfo(title, plot):
    return ('<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<tvshow>\n  <title>%s</title>\n  <plot>%s</plot>\n</tvshow>\n'
            % (x(title), x(plot)))


def sync(cfg, entries):
    """Write the NFO files for finished recordings that have an MP4. Returns (written, missing_mp4)."""
    shows, missing = {}, 0
    for e in entries:
        f = paths.to_local(cfg, e.get("filename") or "")
        if not f.endswith((".ts", ".mkv")) or not os.path.exists(f) or os.path.getsize(f) == 0:
            continue
        mp4 = paths.mp4_for(cfg, f)
        if not os.path.exists(mp4):
            missing += 1
            continue
        shows.setdefault(os.path.dirname(mp4), []).append(dict(e, _mp4=mp4))
    written = 0
    for folder, es in shows.items():
        title = es[0].get("disp_title") or os.path.basename(folder)
        plot = next((e.get("disp_description") or e.get("disp_subtitle") for e in es
                     if e.get("disp_description") or e.get("disp_subtitle")), "")
        written += _write(os.path.join(folder, "tvshow.nfo"), show_nfo(title, plot))
        es.sort(key=lambda e: e["start"])
        counts = {}
        for e in es:
            st = time.localtime(e["start"])
            counts[st.tm_year] = counts.get(st.tm_year, 0) + 1
            written += _write(os.path.splitext(e["_mp4"])[0] + ".nfo", episode_nfo(title, st.tm_year, counts[st.tm_year], e, st))
    return written, missing
