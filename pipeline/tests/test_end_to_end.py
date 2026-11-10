"""Whole pipeline against a fake Tvheadend, with real ffmpeg/ffprobe on a synthetic recording (skipped without them)."""
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest

from tvhpipeline import media, paths, runner
from tvhpipeline.config import Config
from tvhpipeline.state import State
from tvhpipeline.tvheadend import Tvheadend

HAVE_FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")


class FakeTvheadend:
    def __init__(self):
        self.entries = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body = json.dumps({"entries": outer.entries}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = "http://127.0.0.1:%d" % self.srv.server_port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()


def make_recording(path):
    """25 s H.264 video with two audio tracks; the second is flagged as audio description."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-f", "lavfi", "-i", "sine=frequency=440",
         "-f", "lavfi", "-i", "sine=frequency=880", "-t", "25", "-map", "0", "-map", "1", "-map", "2",
         "-vf", "noise=alls=40:allf=t",  # real broadcasts are mostly video: keep the audio a small part of the file
         "-c:v", "libx264", "-b:v", "3M", "-c:a", "aac",
         "-metadata:s:a:0", "language=eng", "-metadata:s:a:1", "language=eng",  # TS carries the flag only with a language label, as broadcasts do
         "-disposition:a:1", "visual_impaired", "-f", "mpegts", path], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def make_recording_with_hole(path, hole=40):
    """A recording whose first second is followed by `hole` seconds of nothing, then 12 s of programme (a tuner that
    started delivering late: seen on a real recording)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    for name, secs, offset in (("a.ts", 1, 0), ("b.ts", 12, hole)):
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-f", "lavfi", "-i", "sine=frequency=440",
             "-t", str(secs), "-vf", "noise=alls=40:allf=t", "-c:v", "libx264", "-g", "25", "-b:v", "2M", "-c:a", "aac",
             "-output_ts_offset", str(offset), "-f", "mpegts", path + "." + name], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    with open(path, "wb") as out:
        for name in ("a.ts", "b.ts"):
            with open(path + "." + name, "rb") as part:
                out.write(part.read())
            os.remove(path + "." + name)


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
class LeadingHole(unittest.TestCase):
    def test_hole_is_measured_and_the_conversion_is_still_accepted(self):
        from tvhpipeline.steps import to_mp4
        root = tempfile.mkdtemp()
        try:
            ts = os.path.join(root, "Show", "Show - 2026-11-09 20.00.ts")
            make_recording_with_hole(ts)
            self.assertGreater(media.leading_gap(ts), 30)
            out = os.path.join(root, "_jellyfin", "Show", "Show - 2026-11-09 20.00.mp4")
            status, detail = to_mp4.run(Config(), ts, out)
            self.assertEqual(status, "ok", detail)
            self.assertTrue(os.path.getsize(out) > 0)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_a_normal_recording_has_no_leading_gap(self):
        root = tempfile.mkdtemp()
        try:
            ts = os.path.join(root, "Show", "Show - 2026-11-09 20.00.ts")
            make_recording(ts)
            self.assertEqual(media.leading_gap(ts), 0.0)
        finally:
            shutil.rmtree(root, ignore_errors=True)


@unittest.skipUnless(HAVE_FFMPEG, "needs ffmpeg")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.tvh = FakeTvheadend()
        self.cfg = Config(tvh_url=self.tvh.url, tvheadend_root=self.root, recordings=self.root, library=os.path.join(self.root, "_jellyfin"),
                          state_dir=os.path.join(self.root, "state"), settle_seconds=0, comskip=False)
        os.makedirs(self.cfg.state_dir)
        self.state = State(os.path.join(self.cfg.state_dir, "state.db"))
        self.client = Tvheadend(self.tvh.url, "u", "p")
        self.ts = os.path.join(self.root, "Show", "Show - 2026-11-09 20.00.ts")
        make_recording(self.ts)
        self.tvh.entries = [{"uuid": "abc", "filename": self.ts, "disp_title": "Show", "disp_subtitle": "Ep", "disp_description": "",
                             "channelname": "ITV1 HD", "start": 1762718400, "stop": 1762720200}]

    def tearDown(self):
        self.tvh.close()
        shutil.rmtree(self.root, ignore_errors=True)

    def test_full_pass(self):
        self.assertEqual(media.count(self.ts, "audio"), 2)
        info = runner.cycle(self.cfg, self.state, self.client)
        self.assertEqual(info["worked"], 1)
        # the audio-description track is gone from the recording itself
        self.assertEqual(media.count(self.ts, "audio"), 1)
        mp4 = paths.mp4_for(self.cfg, self.ts)
        self.assertTrue(os.path.getsize(mp4) > 0)
        self.assertEqual((media.first_codec(mp4, "video"), media.first_codec(mp4, "audio")), ("h264", "aac"))
        self.assertAlmostEqual(media.duration(mp4), 25, delta=1.5)
        self.assertTrue(os.path.getsize(mp4[:-4] + "-thumb.jpg") > 0)
        self.assertIn("<showtitle>Show</showtitle>", open(mp4[:-4] + ".nfo").read())
        self.assertTrue(os.path.exists(os.path.join(os.path.dirname(mp4), "tvshow.nfo")))
        for step in ("strip_ad", "convert_mp4", "thumbnail"):
            self.assertIn(self.state.get("abc", step)["status"], ("ok",))
        # nothing left half-written
        leftovers = [f for r, _d, fs in os.walk(self.root) for f in fs if f.endswith((".part", ".tmp"))]
        self.assertEqual(leftovers, [])

    def test_second_pass_does_nothing_and_a_restart_does_not_redo_work(self):
        runner.cycle(self.cfg, self.state, self.client)
        mtime = os.path.getmtime(paths.mp4_for(self.cfg, self.ts))
        info = runner.cycle(self.cfg, self.state, self.client)
        self.assertEqual((info["worked"], info.get("nfo_written")), (0, 0))
        self.state.close()
        state2 = State(os.path.join(self.cfg.state_dir, "state.db"))  # as after a container restart
        runner.cycle(self.cfg, state2, self.client)
        self.assertEqual(os.path.getmtime(paths.mp4_for(self.cfg, self.ts)), mtime)

    def test_existing_mp4_from_the_old_pipeline_is_adopted_not_reencoded(self):
        mp4 = paths.mp4_for(self.cfg, self.ts)
        os.makedirs(os.path.dirname(mp4))
        open(mp4, "wb").write(b"made by the legacy scripts")
        runner.cycle(self.cfg, self.state, self.client)
        self.assertEqual(open(mp4, "rb").read(), b"made by the legacy scripts")
        self.assertEqual(self.state.get("abc", "convert_mp4")["status"], "exists")

    def test_a_recording_still_being_written_is_left_alone(self):
        self.cfg.settle_seconds = 3600
        info = runner.cycle(self.cfg, self.state, self.client)
        self.assertEqual(info["worked"], 0)
        self.assertFalse(os.path.exists(paths.mp4_for(self.cfg, self.ts)))

    def test_deleted_recording_is_tidied_from_the_library(self):
        runner.cycle(self.cfg, self.state, self.client)
        mp4 = paths.mp4_for(self.cfg, self.ts)
        make_recording(os.path.join(self.root, "Other", "other.ts"))   # keeps the "recordings are mounted" guard satisfied
        os.remove(self.ts)
        self.tvh.entries = []
        runner.cycle(self.cfg, self.state, self.client)
        self.assertFalse(os.path.exists(mp4))
        self.assertFalse(os.path.exists(mp4[:-4] + "-thumb.jpg"))
        self.assertFalse(os.path.exists(mp4[:-4] + ".nfo"))

    def test_a_broken_recording_fails_cleanly_and_does_not_block_others(self):
        bad = os.path.join(self.root, "Bad", "bad.ts")
        os.makedirs(os.path.dirname(bad))
        open(bad, "wb").write(b"not a video at all")
        self.tvh.entries.insert(0, {"uuid": "bad", "filename": bad, "disp_title": "Bad", "channelname": "X", "start": 1, "stop": 2})
        runner.cycle(self.cfg, self.state, self.client, max_recordings=2)
        self.assertIn(self.state.get("bad", "convert_mp4")["status"], ("failed", "novideo"))
        self.assertEqual(self.state.get("abc", "convert_mp4")["status"], "ok")

    def test_bbc_channels_are_not_sent_to_comskip(self):
        self.cfg.comskip = True
        self.tvh.entries[0]["channelname"] = "BBC ONE HD"
        runner.cycle(self.cfg, self.state, self.client)
        self.assertEqual(self.state.get("abc", "comskip")["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
