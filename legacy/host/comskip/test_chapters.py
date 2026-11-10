import os, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chapters as c  # noqa: E402


class Chapters(unittest.TestCase):
    def test_emmerdale(self):
        b = c.build([(0, 36.4), (663.36, 917.6), (1608.56, 1856.76)], 1856.96)
        self.assertEqual(len(b), 3)
        ch = c.chapters(b, 1856.96)
        self.assertEqual([t for _, _, t in ch], ["Commercial", "Part 1", "Commercial", "Part 2", "Commercial"])  # 0.2 s left over: no Part 3
        self.assertEqual(ch[0][:2], (0.0, 36.4))     # the start is marked
        self.assertEqual(ch[-1][:2], (1608.56, 1856.76))

    def test_start_break_of_a_few_seconds_is_kept(self):
        self.assertEqual(c.build([(0, 4.0), (900, 1150)], 5417), [(0, 4.0), (900, 1150)])

    def test_noise_dropped_and_close_breaks_merged(self):
        self.assertEqual(c.build([(100, 100.4), (200, 260), (262, 330)], 1800), [(200, 330)])

    def test_clamped_to_the_recording(self):
        self.assertEqual(c.build([(1700, 2500)], 1800), [(1700, 1800)])

    def test_chapters_cover_the_recording_without_gaps(self):
        ch = c.chapters([(0, 30), (600, 900)], 1800)
        for (a1, b1, _), (a2, _, _) in zip(ch, ch[1:]):
            self.assertEqual(b1, a2)
        self.assertEqual(ch[0][0], 0)
        self.assertEqual(ch[-1][1], 1800)

    def run_cli(self, edl_text, dur):
        with tempfile.NamedTemporaryFile("w", suffix=".edl", delete=False) as f:
            f.write(edl_text)
        try:
            return subprocess.run([sys.executable, os.path.join(HERE, "chapters.py"), f.name, str(dur)], capture_output=True, text=True)
        finally:
            os.unlink(f.name)

    def test_no_breaks_exits_3(self):
        self.assertEqual(self.run_cli("", 1800).returncode, 3)

    def test_implausible_result_is_refused(self):
        r = self.run_cli("0\t1000\t0\n", 1800)   # more than half the recording "adverts"
        self.assertEqual(r.returncode, 4)
        self.assertNotIn("CHAPTER", r.stdout)

    def test_good_result_writes_ffmetadata(self):
        r = self.run_cli("651.00\t917.32\t0\n", 1856.96)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith(";FFMETADATA1"))
        self.assertIn("title=Commercial", r.stdout)


if __name__ == "__main__":
    unittest.main()
