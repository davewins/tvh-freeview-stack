import os
import tempfile
import unittest

from tvhpipeline.steps import adbreaks as c


class AdBreaks(unittest.TestCase):
    def test_emmerdale(self):
        b = c.clean([(0, 36.4), (663.36, 917.6), (1608.56, 1856.76)], 1856.96)
        self.assertEqual(len(b), 3)
        ch = c.chapters(b, 1856.96)
        self.assertEqual([t for _, _, t in ch], ["Commercial", "Part 1", "Commercial", "Part 2", "Commercial"])  # 0.2 s left: no Part 3
        self.assertEqual(ch[0][:2], (0.0, 36.4))  # the start is marked

    def test_start_break_of_a_few_seconds_is_kept(self):
        self.assertEqual(c.clean([(0, 4.0), (900, 1150)], 5417), [(0, 4.0), (900, 1150)])

    def test_noise_dropped_and_close_breaks_merged(self):
        self.assertEqual(c.clean([(100, 100.4), (200, 260), (262, 330)], 1800), [(200, 330)])

    def test_clamped_to_the_recording(self):
        self.assertEqual(c.clean([(1700, 2500)], 1800), [(1700, 1800)])

    def test_chapters_cover_the_recording_without_gaps(self):
        ch = c.chapters([(0, 30), (600, 900)], 1800)
        for (a1, b1, _), (a2, _, _) in zip(ch, ch[1:]):
            self.assertEqual(b1, a2)
        self.assertEqual((ch[0][0], ch[-1][1]), (0, 1800))

    def build(self, text, dur):
        with tempfile.NamedTemporaryFile("w", suffix=".edl", delete=False) as f:
            f.write(text)
        try:
            return c.build(f.name, dur)
        finally:
            os.unlink(f.name)

    def test_no_breaks(self):
        self.assertEqual(self.build("", 1800)[0], "none")

    def test_implausible_result_is_refused(self):
        status, meta, _ = self.build("0\t1000\t0\n", 1800)  # over half the recording "adverts"
        self.assertEqual((status, meta), ("suspicious", ""))

    def test_good_result_writes_ffmetadata(self):
        status, meta, summary = self.build("651.00\t917.32\t0\n", 1856.96)
        self.assertEqual(status, "ok")
        self.assertTrue(meta.startswith(";FFMETADATA1"))
        self.assertIn("title=Commercial", meta)
        self.assertEqual(summary, "breaks=1 seconds=266")


if __name__ == "__main__":
    unittest.main()
