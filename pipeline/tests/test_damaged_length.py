import os
import shutil
import tempfile
import types
import unittest
from unittest import mock

from tvhpipeline.config import Config
from tvhpipeline.steps import to_mp4


class DamagedLength(unittest.TestCase):
    """A conversion that comes out shorter than its source is refused, unless the source was damaged by poor reception."""

    def run_with(self, src_len, out_len, damaged):
        root = tempfile.mkdtemp()
        try:
            ts = os.path.join(root, "Show", "Show - 2026-11-13 13.00.ts")
            out = os.path.join(root, "_jellyfin", "Show", "Show - 2026-11-13 13.00.mp4")
            os.makedirs(os.path.dirname(ts))
            open(ts, "wb").write(b"x")

            def fake_run(cmd, total, cb):
                open(cmd[-1], "wb").write(b"mp4")
                return types.SimpleNamespace(returncode=0, stderr="")

            lens = {ts: src_len}
            with mock.patch.object(to_mp4.media, "first_codec", return_value="h264"), \
                 mock.patch.object(to_mp4.media, "run_progress", side_effect=fake_run), \
                 mock.patch.object(to_mp4.media, "duration", side_effect=lambda p: lens.get(p, out_len)), \
                 mock.patch.object(to_mp4.media, "count", return_value=1), \
                 mock.patch.object(to_mp4.media, "leading_gap", return_value=0.0):
                return to_mp4.run(Config(), ts, out, damaged=damaged), os.path.exists(out)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_normal_recording_must_match(self):
        (status, _), exists = self.run_with(1442.0, 1280.0, damaged=False)
        self.assertEqual(status, "failed")
        self.assertFalse(exists)

    def test_damaged_recording_may_be_shorter(self):
        (status, detail), exists = self.run_with(1442.0, 1280.0, damaged=True)
        self.assertEqual(status, "ok", detail)
        self.assertIn("damaged", detail)
        self.assertTrue(exists)

    def test_damaged_recording_still_needs_most_of_it(self):
        (status, _), exists = self.run_with(1442.0, 600.0, damaged=True)
        self.assertEqual(status, "failed")
        self.assertFalse(exists)


if __name__ == "__main__":
    unittest.main()
