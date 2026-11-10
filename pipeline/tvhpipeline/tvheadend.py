"""A small Tvheadend API client (HTTP digest or basic authentication, whichever the server asks for)."""
import json
import urllib.request


class Tvheadend:
    def __init__(self, url: str, user: str, password: str):
        self.url = url
        mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        mgr.add_password(None, url, user, password)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPDigestAuthHandler(mgr), urllib.request.HTTPBasicAuthHandler(mgr)
        )

    def get(self, path: str):
        with self.opener.open(self.url + path, timeout=30) as r:
            return json.load(r)

    def finished(self):
        """Finished recordings (newest data first as Tvheadend returns it)."""
        return self.get("/api/dvr/entry/grid_finished?limit=5000").get("entries", [])
