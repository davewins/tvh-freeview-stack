import os
import tempfile
import unittest

from tvhpipeline import paths
from tvhpipeline.config import Config
from tvhpipeline.state import State
from tvhpipeline.steps import cleanup


class StateTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.s = State(os.path.join(self.d, "s.db"))

    def test_new_step_is_due_finished_step_is_not(self):
        self.assertTrue(self.s.due("r", "convert_mp4", 5))
        self.s.put("r", "convert_mp4", "ok")
        self.assertFalse(self.s.due("r", "convert_mp4", 5))

    def test_failed_step_backs_off_then_gives_up(self):
        self.s.put("r", "x", "failed", "boom", attempts=1)
        ts = self.s.get("r", "x")["ts"]
        self.assertFalse(self.s.due("r", "x", 5, now=ts + 60))          # too soon (5 min)
        self.assertTrue(self.s.due("r", "x", 5, now=ts + 301))
        self.s.put("r", "x", "failed", "boom", attempts=2)
        ts = self.s.get("r", "x")["ts"]
        self.assertFalse(self.s.due("r", "x", 5, now=ts + 301))         # now 10 min
        self.assertTrue(self.s.due("r", "x", 5, now=ts + 601))
        self.s.put("r", "x", "failed", "boom", attempts=5)
        self.assertFalse(self.s.due("r", "x", 5, now=ts + 10 ** 6))     # gave up

    def test_summary_and_failures(self):
        self.s.put("a", "convert_mp4", "ok")
        self.s.put("b", "convert_mp4", "failed", "why", attempts=1)
        self.assertIn(("convert_mp4", "ok", 1), self.s.summary())
        self.assertEqual(self.s.failures()[0][:3], ("b", "convert_mp4", "why"))


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cfg = Config(recordings=self.root, library=os.path.join(self.root, "_jellyfin"), tvheadend_root=self.root)

    def touch(self, p, data=b"x"):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(data)
        return p

    def lib(self, show, name, ext):
        return os.path.join(self.cfg.library, show, name + ext)

    def test_keeps_files_of_existing_recordings(self):
        self.touch(os.path.join(self.root, "Show", "ep.ts"))
        for ext in (".mp4", "-thumb.jpg", ".nfo"):
            self.touch(self.lib("Show", "ep", ext))
        self.touch(self.lib("Show", "tvshow", ".nfo"))
        out = cleanup.run(self.cfg)
        self.assertEqual({k: v for k, v in out.items() if k != "skipped"}, {"mp4": 0, "thumb": 0, "nfo": 0, "folder_jpg": 0, "dirs": 0})
        self.assertTrue(os.path.exists(self.lib("Show", "ep", ".mp4")))

    def test_removes_files_of_deleted_recordings_and_empty_folders(self):
        self.touch(os.path.join(self.root, "Other", "keep.ts"))          # proves the recordings folder is mounted
        for ext in (".mp4", "-thumb.jpg", ".nfo"):
            self.touch(self.lib("Gone", "ep", ext))
        self.touch(self.lib("Gone", "tvshow", ".nfo"))
        self.touch(self.lib("Gone", "folder", ".jpg"))
        out = cleanup.run(self.cfg)
        self.assertEqual((out["mp4"], out["thumb"], out["nfo"], out["folder_jpg"]), (1, 1, 1, 1))
        self.assertFalse(os.path.exists(os.path.join(self.cfg.library, "Gone")) and os.listdir(os.path.join(self.cfg.library, "Gone")) != ["tvshow.nfo"])

    def test_keeps_an_mp4_marked_to_keep_after_its_recording_is_deleted(self):
        self.touch(os.path.join(self.root, "Other", "keep.ts"))          # proves the recordings folder is mounted
        for ext in (".mp4", "-thumb.jpg", ".nfo", ".keep"):
            self.touch(self.lib("Kept", "ep", ext))
        self.touch(self.lib("Kept", "folder", ".jpg"))
        for ext in (".mp4", "-thumb.jpg", ".nfo"):                       # a neighbour that is NOT marked
            self.touch(self.lib("Kept", "other", ext))
        out = cleanup.run(self.cfg)
        self.assertEqual((out["mp4"], out["thumb"], out["nfo"], out["folder_jpg"]), (1, 1, 1, 0))
        for ext in (".mp4", "-thumb.jpg", ".nfo", ".keep"):
            self.assertTrue(os.path.exists(self.lib("Kept", "ep", ext)), ext)
        self.assertFalse(os.path.exists(self.lib("Kept", "other", ".mp4")))

    def test_never_touches_work_in_progress_files(self):
        self.touch(os.path.join(self.root, "Other", "keep.ts"))
        part = self.touch(self.lib("Show", "ep", ".mp4.part"))
        cs = self.touch(self.lib("Show", "ep", ".mp4.comskip.part"))   # what the advert step writes: must not look like an orphan
        cleanup.run(self.cfg)
        self.assertTrue(os.path.exists(part) and os.path.exists(cs))

    def test_does_nothing_if_recordings_look_unmounted(self):
        mp4 = self.touch(self.lib("Show", "ep", ".mp4"))                # no .ts anywhere
        out = cleanup.run(self.cfg)
        self.assertTrue(out["skipped"])
        self.assertTrue(os.path.exists(mp4))

    def test_dry_run_removes_nothing(self):
        self.touch(os.path.join(self.root, "Other", "keep.ts"))
        mp4 = self.touch(self.lib("Gone", "ep", ".mp4"))
        out = cleanup.run(self.cfg, dry_run=True)
        self.assertEqual(out["mp4"], 1)
        self.assertTrue(os.path.exists(mp4))


class HeartbeatTests(unittest.TestCase):
    def test_heartbeat_ticks_without_the_main_loop(self):
        import time
        from tvhpipeline import runner
        d = tempfile.mkdtemp()
        p = os.path.join(d, "heartbeat")
        runner.start_heartbeat(p, interval=0.1)
        time.sleep(0.5)
        first = os.path.getmtime(p)
        time.sleep(0.5)
        self.assertGreater(os.path.getmtime(p), first)

    def test_activity_is_shown_while_a_step_runs_and_cleared_after(self):
        from tvhpipeline import runner
        from tvhpipeline.state import State as S
        d = tempfile.mkdtemp()
        runner.ACTIVITY["path"] = os.path.join(d, "activity")
        seen = []
        cfg = Config(max_attempts=5)
        st = S(os.path.join(d, "s.db"))
        runner._attempt(st, cfg, "r", "convert_mp4", lambda: (seen.append(open(runner.ACTIVITY["path"]).read()) or ("ok", "")), "x.ts")
        self.assertTrue(seen[0].startswith("convert_mp4 x.ts since"))
        self.assertFalse(os.path.exists(runner.ACTIVITY["path"]))


class PathTests(unittest.TestCase):
    def test_mapping(self):
        cfg = Config(tvheadend_root="/tvh", recordings="/data", library="/data/_jellyfin")
        self.assertEqual(paths.to_local(cfg, "/tvh/Show/ep.ts"), "/data/Show/ep.ts")
        self.assertEqual(paths.mp4_for(cfg, "/data/Show/ep.ts"), "/data/_jellyfin/Show/ep.mp4")
        self.assertEqual(paths.to_local(cfg, "/elsewhere/x.ts"), "/elsewhere/x.ts")


if __name__ == "__main__":
    unittest.main()
