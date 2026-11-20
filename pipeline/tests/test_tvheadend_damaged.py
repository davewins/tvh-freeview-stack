import unittest

from tvhpipeline.tvheadend import Tvheadend


class Stub(Tvheadend):
    def __init__(self, finished, failed):
        self._d = {"grid_finished": finished, "grid_failed": failed}

    def get(self, path):
        for k, v in self._d.items():
            if k in path:
                return {"entries": v}
        raise AssertionError(path)


class DamagedRecordings(unittest.TestCase):
    def setUp(self):
        self.ok = {"uuid": "a", "status": "Completed OK", "filesize": 10}
        self.noisy = {"uuid": "b", "status": "Too many data errors", "filesize": 10}
        self.missed = {"uuid": "c", "status": "Time missed", "filesize": 0}
        self.empty = {"uuid": "d", "status": "Too many data errors", "filesize": 0}

    def test_includes_recordings_failed_only_for_data_errors(self):
        t = Stub([self.ok], [self.noisy, self.missed, self.empty])
        self.assertEqual([e["uuid"] for e in t.finished()], ["a", "b"])

    def test_can_be_switched_off(self):
        t = Stub([self.ok], [self.noisy])
        self.assertEqual([e["uuid"] for e in t.finished(include_damaged=False)], ["a"])

    def test_no_duplicates(self):
        t = Stub([self.ok, self.noisy], [self.noisy])
        self.assertEqual(len(t.finished()), 2)


if __name__ == "__main__":
    unittest.main()
