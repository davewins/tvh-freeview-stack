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

    def finished(self, include_damaged: bool = True):
        """Finished recordings (newest data first as Tvheadend returns it). With include_damaged, also the recordings
        Tvheadend moved to "failed" only because of "Too many data errors" (poor reception): they have a file with
        most of the programme in it, which is worth converting. Recordings with no file ("Time missed") are not."""
        entries = self.get("/api/dvr/entry/grid_finished?limit=5000").get("entries", [])
        if not include_damaged:
            return entries
        seen = {e.get("uuid") for e in entries}
        try:
            failed = self.get("/api/dvr/entry/grid_failed?limit=5000").get("entries", [])
        except Exception:
            return entries  # a failed lookup must not stop the normal recordings
        for e in failed:
            if e.get("uuid") not in seen and (e.get("filesize") or 0) > 0 and "data errors" in (e.get("status") or "").lower():
                entries.append(e)
        return entries


DAMAGED_ERRORS = 1000  # a few hundred damaged packets is normal and invisible; thousands show as glitches


def is_damaged(entry: dict) -> bool:
    """True for a recording Tvheadend flagged for data errors, or that has many of them (one moved to Finished by hand
    reads "Forced OK" but still carries its count)."""
    return "data errors" in (entry.get("status") or "").lower() or (entry.get("data_errors") or 0) >= DAMAGED_ERRORS
