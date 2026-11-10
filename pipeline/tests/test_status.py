import json
import os
import tempfile
import unittest

from tvhpipeline import media, status
from tvhpipeline.state import State


class StatusFile(unittest.TestCase):
    def test_written_atomically_with_current_queue_and_failures(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "status.json")
        status.configure(p)
        status.set_lists([{"id": "b", "title": "B", "steps": ["convert_mp4"]}], [{"id": "c", "title": "C", "step": "convert_mp4", "detail": "x", "attempts": 2, "retry_at": 5}])
        status.begin("a", "A", "convert_mp4")
        status.progress(41.26)
        status.end()
        doc = json.load(open(p))
        self.assertIsNone(doc["current"])
        self.assertEqual(doc["queue"][0]["id"], "b")
        self.assertEqual(doc["failed"][0]["attempts"], 2)
        self.assertFalse(os.path.exists(p + ".tmp"))

    def test_progress_is_visible_while_a_step_runs(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "status.json")
        status.configure(p)
        status.begin("a", "A", "convert_mp4")
        status.progress(41.26)
        status.refresh()
        cur = json.load(open(p))["current"]
        self.assertEqual((cur["id"], cur["step"], cur["percent"]), ("a", "convert_mp4", 41.3))
        status.end()


class RunProgress(unittest.TestCase):
    def test_reports_percent_and_keeps_errors(self):
        seen = []
        script = "print('out_time_us=2500000'); print('progress=continue'); print('out_time_us=10000000'); print('Some error text')"
        r = media.run_progress(["python3", "-c", script], 10, seen.append)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(seen[0], 25.0)
        self.assertLess(seen[-1], 100)
        self.assertIn("Some error text", r.stderr)
        self.assertNotIn("out_time_us", r.stderr)


class RetryAt(unittest.TestCase):
    def test_backoff_and_giving_up(self):
        s = State(os.path.join(tempfile.mkdtemp(), "s.db"))
        s.put("r", "convert_mp4", "failed", "boom", 1)
        ts = s.get("r", "convert_mp4")["ts"]
        self.assertEqual(s.retry_at("r", "convert_mp4", 5), ts + 300)
        s.put("r", "convert_mp4", "failed", "boom", 5)
        self.assertIsNone(s.retry_at("r", "convert_mp4", 5))
        self.assertIsNone(s.retry_at("r", "nothing", 5))


if __name__ == "__main__":
    unittest.main()
