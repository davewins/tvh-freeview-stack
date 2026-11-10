#!/usr/bin/python3
"""Host script (cron, after tvh-nfo-sync): give any 'Freeview Recordings' programme that has NO Primary image
(TMDb found no match) one of its own episode thumbnails. Skips programmes younger than 1 hour so TMDb gets first go.
Never touches programmes that already have an image."""
import base64, glob, json, os, sys, urllib.request, datetime
B = os.environ["JELLYFIN_URL"]; LIB = os.environ["JELLYFIN_LIBRARY_ID"]; USER = os.environ["JELLYFIN_USER_ID"]  # see docs/jellyfin.md
H = {"Authorization": 'MediaBrowser Token="%s"' % os.environ["JELLYFIN_API_KEY"]}
def get(p): return json.load(urllib.request.urlopen(urllib.request.Request(B + p, headers=H), timeout=30))
items = get("/Items?parentId=%s&userId=%s&Recursive=true&IncludeItemTypes=Series&Fields=Path,DateCreated" % (LIB, USER))["Items"]
done = []
for s in items:
    if "Primary" in (s.get("ImageTags") or {}): continue
    age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(s["DateCreated"].replace("Z", "+00:00"))
    if age.total_seconds() < 3600: continue
    host = s["Path"].replace(os.environ.get("JELLYFIN_PATH_PREFIX", "/media8TB/"), os.environ.get("HOST_PATH_PREFIX", "/mnt/8TB/"), 1)
    thumbs = sorted(glob.glob(os.path.join(glob.escape(host), "*-thumb.jpg")))
    if not thumbs: continue
    req = urllib.request.Request(B + "/Items/%s/Images/Primary" % s["Id"], data=base64.b64encode(open(thumbs[0], "rb").read()),
                                 headers=dict(H, **{"Content-Type": "image/jpeg"}), method="POST")
    urllib.request.urlopen(req, timeout=30); done.append(s["Name"])
print("series=%d image_fallback=%s" % (len(items), done))
