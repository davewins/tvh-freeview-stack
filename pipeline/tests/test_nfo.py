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


if __name__ == "__main__":
    unittest.main()
