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
                self.cmd = cmd
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

    def flags(self, damaged):
        self.run_with(1442.0, 1442.0, damaged=damaged)
        return self.cmd[self.cmd.index("-fflags") + 1], self.cmd

    def test_damaged_source_drops_corrupt_packets(self):
        # without this a damaged HD recording made ffmpeg's memory explode and the container OOM-kill it
        fflags, cmd = self.flags(True)
        self.assertIn("discardcorrupt", fflags)
        self.assertIn("-max_error_rate", cmd)

    def test_damaged_hd_keeps_real_timing_but_not_a_bogus_stamp(self):
        # a second recording (F1 highlights) still ran away in memory with only discardcorrupt: timestamps jumped by years
        fflags, cmd = self.flags(True)
        self.assertIn("PREV_INPTS", cmd[cmd.index("-vf") + 1])
        self.assertNotIn("N/FRAME_RATE", cmd[cmd.index("-vf") + 1])
        self.assertNotIn("-shortest", cmd)  # it queues audio while waiting for video: OOM again

    def test_late_video_is_held_not_shifted_early(self):
        # the video of one recording started 0.73 s after its audio; ffmpeg moved it to zero: lip-sync off for the whole show
        with mock.patch.object(to_mp4.media, "start_lead", return_value=0.728):
            self.run_with(1442.0, 1442.0, damaged=False)
        self.assertIn("tpad=start_duration=0.728:start_mode=clone", self.cmd[self.cmd.index("-vf") + 1])

    def test_a_timestamp_jump_switches_to_the_repair_path(self):
        with mock.patch.object(to_mp4.media, "has_timestamp_jump", return_value=True):
            fflags, cmd = self.flags(False)
        self.assertIn("discardcorrupt", fflags)
        self.assertIn("PREV_INPTS", cmd[cmd.index("-vf") + 1])
        self.assertNotIn("N/FRAME_RATE", cmd[cmd.index("-vf") + 1])

    def test_clean_source_is_not_changed(self):
        fflags, cmd = self.flags(False)
        self.assertEqual(fflags, "+genpts")
        self.assertNotIn("-max_error_rate", cmd)
        self.assertNotIn("setpts", cmd[cmd.index("-vf") + 1])


class TrimAudioOverhang(unittest.TestCase):
    def test_audio_longer_than_video_is_cut_at_the_video(self):
        import subprocess, tempfile
        from tvhpipeline import media
        from tvhpipeline.steps import to_mp4
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "x.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=10:d=4",
                            "-f", "lavfi", "-i", "sine=d=15", "-c:v", "libx264", "-c:a", "aac", f], check=True)
            self.assertGreater(media.duration(f), 14)
            self.assertIsNone(to_mp4._trim_audio(f))
            self.assertLess(media.duration(f), 5)

    def test_matching_lengths_are_left_alone(self):
        import subprocess, tempfile
        from tvhpipeline import media
        from tvhpipeline.steps import to_mp4
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "x.mp4")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=64x64:r=10:d=4",
                            "-f", "lavfi", "-i", "sine=d=4", "-c:v", "libx264", "-c:a", "aac", f], check=True)
            before = os.path.getsize(f)
            self.assertIsNone(to_mp4._trim_audio(f))
            self.assertEqual(os.path.getsize(f), before)


class StartLeadAndJumps(unittest.TestCase):
    def _ts(self, d, name, vdelay, extra=()):
        import subprocess
        f = os.path.join(d, name)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-itsoffset", str(vdelay), "-f", "lavfi", "-i", "testsrc=size=64x64:rate=25:d=6",
                        "-f", "lavfi", "-i", "sine=d=6", "-c:v", "libx264", "-c:a", "aac", "-f", "mpegts", f], check=True)
        return f

    def test_video_starting_after_audio_is_measured(self):
        from tvhpipeline import media
        with tempfile.TemporaryDirectory() as d:
            self.assertAlmostEqual(media.start_lead(self._ts(d, "late.ts", 0.7)), 0.7, delta=0.15)
            self.assertEqual(media.start_lead(self._ts(d, "same.ts", 0)), 0.0)

    def test_timestamp_jump_is_detected(self):
        from tvhpipeline import media
        with tempfile.TemporaryDirectory() as d:
            self.assertFalse(media.has_timestamp_jump(self._ts(d, "ok.ts", 0)))
        with mock.patch.object(media, "run") as r:
            r.return_value = types.SimpleNamespace(stdout="1.0\n1.04\n92461.2\n1.12\n")
            self.assertTrue(media.has_timestamp_jump("x"))


if __name__ == "__main__":
    unittest.main()
