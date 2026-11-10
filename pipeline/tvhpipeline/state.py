"""What has been done to each recording, so the pipeline resumes after a restart and never repeats finished work."""
import sqlite3
import time

TERMINAL = ("ok", "exists", "none", "skipped", "already", "nobreaks", "tooshort", "novideo", "suspicious", "gone")


class State:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS steps (rec TEXT, step TEXT, status TEXT, detail TEXT, ts INTEGER, attempts INTEGER,"
            " PRIMARY KEY (rec, step))"
        )
        self.db.commit()

    def get(self, rec: str, step: str):
        r = self.db.execute("SELECT status, detail, ts, attempts FROM steps WHERE rec=? AND step=?", (rec, step)).fetchone()
        return None if r is None else {"status": r[0], "detail": r[1], "ts": r[2], "attempts": r[3]}

    def put(self, rec: str, step: str, status: str, detail: str = "", attempts: int = 0):
        self.db.execute(
            "INSERT INTO steps VALUES (?,?,?,?,?,?) ON CONFLICT(rec, step) DO UPDATE SET status=excluded.status,"
            " detail=excluded.detail, ts=excluded.ts, attempts=excluded.attempts",
            (rec, step, status, detail, int(time.time()), attempts),
        )
        self.db.commit()

    def due(self, rec: str, step: str, max_attempts: int, now: float | None = None) -> bool:
        """Should this step be attempted now? Finished steps no; failed ones back off (5 min, 10, 20, ... up to 6 h)."""
        now = now or time.time()
        s = self.get(rec, step)
        if s is None:
            return True
        if s["status"] in TERMINAL:
            return False
        if s["status"] == "failed" and s["attempts"] >= max_attempts:
            return False
        wait = min(300 * 2 ** max(s["attempts"] - 1, 0), 6 * 3600)
        return now - s["ts"] >= wait

    def retry_at(self, rec: str, step: str, max_attempts: int):
        """When a failed step will be tried again (epoch seconds), or None once it has been given up on."""
        s = self.get(rec, step)
        if s is None or s["status"] != "failed" or s["attempts"] >= max_attempts:
            return None
        return s["ts"] + min(300 * 2 ** max(s["attempts"] - 1, 0), 6 * 3600)

    def summary(self):
        return self.db.execute("SELECT step, status, COUNT(*) FROM steps GROUP BY step, status ORDER BY step, status").fetchall()

    def failures(self, limit: int = 10):
        return self.db.execute(
            "SELECT rec, step, detail, attempts FROM steps WHERE status='failed' ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()

    def close(self):
        self.db.close()
