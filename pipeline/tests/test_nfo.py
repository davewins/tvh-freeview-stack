import os
import tempfile
import time
import unittest

from tvhpipeline.config import Config
from tvhpipeline.steps import nfo

os.environ["TZ"] = "UTC"
time.tzset()

E = {"uuid": "u1", "filename": "", "disp_title": "Emmerdale & Co", "disp_subtitle": "Bad news.", "disp_description": "Kev <moves>.",
     "channelname": "ITV1 HD", "start": 1762718400, "stop": 1762720200, "genre": ["Soap", 5]}  # 2025-11-09 20:00 UTC


class Nfo(unittest.TestCase):
    def test_episode_format_matches_the_legacy_writer(self):
        got = nfo.episode_nfo("Emmerdale & Co", 2025, 3, E, time.localtime(E["start"]))
        self.assertEqual(got, (
            '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<episodedetails>\n'
            "  <title>Sun 09 Nov 2025 20:00 · ITV1 HD</title>\n  <showtitle>Emmerdale &amp; Co</showtitle>\n"
            "  <season>2025</season>\n  <episode>3</episode>\n  <aired>2025-11-09</aired>\n  <runtime>30</runtime>\n"
            "  <studio>ITV1 HD</studio>\n  <plot>Bad news.\n\nKev &lt;moves&gt;.</plot>\n  <genre>Soap</genre>\n</episodedetails>\n"))

    def test_show_format(self):
        self.assertEqual(nfo.show_nfo("A & B", "x"), '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n<tvshow>\n  <title>A &amp; B</title>\n  <plot>x</plot>\n</tvshow>\n')

    def test_sync_numbers_episodes_per_year_and_skips_recordings_without_mp4(self):
        root = tempfile.mkdtemp()
        cfg = Config(recordings=root, tvheadend_root=root, library=os.path.join(root, "_jellyfin"))
        entries = []
        for i, day in enumerate((9, 10, 11)):
            ts = os.path.join(root, "Show", "ep%d.ts" % i)
            os.makedirs(os.path.dirname(ts), exist_ok=True)
            open(ts, "wb").write(b"x")
            if i < 2:  # the third has no MP4 yet
                mp4 = os.path.join(cfg.library, "Show", "ep%d.mp4" % i)
                os.makedirs(os.path.dirname(mp4), exist_ok=True)
                open(mp4, "wb").write(b"x")
            entries.append(dict(E, uuid="u%d" % i, filename=ts, start=E["start"] + i * 86400, stop=E["stop"] + i * 86400))
        written, missing = nfo.sync(cfg, entries)
        self.assertEqual((written, missing), (3, 1))   # tvshow.nfo + 2 episodes
        self.assertIn("<episode>2</episode>", open(os.path.join(cfg.library, "Show", "ep1.nfo")).read())
        self.assertEqual(nfo.sync(cfg, entries), (0, 1))  # nothing rewritten the second time


class NfoWrittenBeforeSlowSteps(unittest.TestCase):
    def test_nfo_exists_before_thumbnail_and_comskip_run(self):
        # Jellyfin files a new MP4 under "Season Unknown" if its .nfo is not there yet (seen 2026-11-24: comskip took
        # 100 s, other recordings 10 min). The runner must write the .nfo as soon as the MP4 is in place.
        import tempfile
        from unittest import mock
        from tvhpipeline import runner
        seen = {}
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "Show", "Show - 2026-11-24 13.30.mp4")
            os.makedirs(os.path.dirname(out))
            open(out, "wb").write(b"x")
            nfo_path = out[:-4] + ".nfo"

            def thumb_run(cfg, mp4):
                seen["nfo_before_thumb"] = os.path.exists(nfo_path)
                return "ok", ""

            cfg = mock.Mock(strip_audio_description=False, convert_mp4=False, thumbnail=True, comskip=False)
            state = mock.Mock()
            state.due.return_value = True
            state.get.return_value = None
            state.put = mock.Mock()
            ts = os.path.join(d, "Show", "Show - 2026-11-24 13.30.ts")
            open(ts, "wb").write(b"x")
            entry = {"uuid": "u", "filename": ts, "disp_title": "Show", "stop": 0}
            with mock.patch.object(runner.paths, "to_local", return_value=ts), \
                 mock.patch.object(runner.paths, "mp4_for", return_value=out), \
                 mock.patch.object(runner, "_settled", return_value=True), \
                 mock.patch.object(runner.thumb, "run", thumb_run), \
                 mock.patch.object(runner.live_status, "begin"), mock.patch.object(runner.live_status, "end"):
                runner.process_recording(cfg, state, entry, 0, lambda: open(nfo_path, "w").write("<nfo/>"))
        self.assertTrue(seen.get("nfo_before_thumb"))


if __name__ == "__main__":
    unittest.main()
