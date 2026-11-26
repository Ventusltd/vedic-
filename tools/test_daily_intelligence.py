import unittest
from daily_intelligence import inventory, next_gap

class DailyResearchTests(unittest.TestCase):
    def test_ranges(self):
        ref = "https://github.com/Ventusltd/gridatlas/blob/" + "a"*40 + "/atlas/index.html"
        self.assertEqual(list(inventory([{"provenance": ref+"#L2-L4 "+ref+"#L4-L6"}]).values()), [{2,3,4,5,6}])
    def test_bounded_gap(self):
        self.assertEqual(next_gap(1000, {1,2}, 0), (3,42))
    def test_no_gap(self):
        self.assertIsNone(next_gap(3, {1,2,3}, 0))
    def test_does_not_cross_covered_line(self):
        self.assertEqual(next_gap(10, {1,4,5,6,7,8,9,10}, 0), (2,3))

if __name__ == "__main__":
    unittest.main()
