"""Optional: give a Jellyfin programme that has no picture (TMDb found no match) one of its own episode thumbnails.
Skips programmes younger than an hour so TMDb gets the first go. Never touches a programme that already has an image."""
import base64
import datetime
import glob
import json
import os
import urllib.request


def run(cfg):
    if not (cfg.jellyfin_url and cfg.jellyfin_library_id and cfg.jellyfin_user_id and cfg.jellyfin_api_key):
        return {"series": 0, "filled": [], "skipped": "jellyfin not configured"}
    base = cfg.jellyfin_url
    headers = {"Authorization": 'MediaBrowser Token="%s"' % cfg.jellyfin_api_key}

    def get(p):
        return json.load(urllib.request.urlopen(urllib.request.Request(base + p, headers=headers), timeout=30))

    items = get("/Items?parentId=%s&userId=%s&Recursive=true&IncludeItemTypes=Series&Fields=Path,DateCreated"
                % (cfg.jellyfin_library_id, cfg.jellyfin_user_id))["Items"]
    filled = []
    for s in items:
        if "Primary" in (s.get("ImageTags") or {}):
            continue
        age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(s["DateCreated"].replace("Z", "+00:00"))
        if age.total_seconds() < 3600:
            continue
        folder = s["Path"]
        if cfg.jellyfin_path_prefix:
            folder = folder.replace(cfg.jellyfin_path_prefix, cfg.host_path_prefix, 1)
        thumbs = sorted(glob.glob(os.path.join(glob.escape(folder), "*-thumb.jpg")))
        if not thumbs:
            continue
        with open(thumbs[0], "rb") as f:
            body = base64.b64encode(f.read())
        req = urllib.request.Request(base + "/Items/%s/Images/Primary" % s["Id"], data=body,
                                     headers=dict(headers, **{"Content-Type": "image/jpeg"}), method="POST")
        urllib.request.urlopen(req, timeout=30)
        filled.append(s["Name"])
    return {"series": len(items), "filled": filled, "skipped": ""}
