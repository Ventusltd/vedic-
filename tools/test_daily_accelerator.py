import random
import sqlite3
import unittest

import numpy as np

import daily_accelerator
from estate_crib_search import GROUPS, scheduled_cribs, select_groups_numpy
from estate_domain_scan import scan


class DailyAcceleratorTests(unittest.TestCase):
    def progress(self, rounds, database="a", method="b", total=37):
        return daily_accelerator.validate({
            "schema": daily_accelerator.SCHEMA,
            "database_sha256": database * 64,
            "method_sha256": method * 64,
            "completed_rounds": rounds,
            "probe_coverage": {"MEASURE EXAMPLE": {"tested": min(total, rounds * 16), "total": total}},
        })

    def test_seeded_rotation_covers_every_crib_before_repeating(self):
        choices = list(range(37))
        unique = []
        for round_index in range(4):
            selected, covered = scheduled_cribs(choices, 16, random.Random(91 + round_index), 123, round_index)
            self.assertEqual(selected, scheduled_cribs(choices, 16, random.Random(91 + round_index), 123, round_index)[0])
            self.assertEqual(len(set(selected)), 16)
            fresh = covered - len(unique)
            self.assertFalse(set(selected[:fresh]).intersection(unique))
            self.assertTrue(set(selected[fresh:]).issubset(unique))
            unique.extend(selected[:fresh])
        self.assertEqual(set(unique), set(choices))

    def test_progress_rejects_skips_changed_universes_and_missing_state(self):
        old = self.progress(1)
        daily_accelerator.verify_advance(old, old)
        daily_accelerator.verify_advance(old, self.progress(2))
        daily_accelerator.verify_advance(old, self.progress(2, database="c"))
        daily_accelerator.verify_advance(old, self.progress(1, method="c"))
        with self.assertRaisesRegex(ValueError, "skipped a round"):
            daily_accelerator.verify_advance(old, self.progress(3))
        with self.assertRaisesRegex(ValueError, "changed its probe universe"):
            daily_accelerator.verify_advance(old, self.progress(2, total=38))
        with self.assertRaisesRegex(ValueError, "first round"):
            daily_accelerator.verify_advance(old, self.progress(2, method="c"))
        with self.assertRaisesRegex(ValueError, "Missing existing"):
            daily_accelerator.verify_advance(old, None)

    def test_cpu_element_scores_matching_tied_and_ungrounded_clues(self):
        rows = np.array([[6, 6, 0, 0], [6, 6, 6, 6], [6, 0, 0, 0]], dtype=np.float32)
        base = np.zeros((4, len(GROUPS) * 2), dtype=np.float32)
        base[:, :4] = np.eye(4, dtype=np.float32)
        scores = np.zeros((4, len(GROUPS)), dtype=np.float32)
        scores[:2, 0] = scores[2:, 1] = 1
        result, _ = select_groups_numpy(rows, base, scores, 1)
        self.assertEqual(result.tolist(), [[0, 18, 0], [-1, 18, 0], [-1, 0, 0]])

    def test_cpu_domain_scan_uses_existing_action_and_object_rule(self):
        columns = {"draw": 0, "cable": 1, "route": 2}
        cues = np.array([[1, 0], [0, 1], [0, 1]], dtype=np.float32)
        with sqlite3.connect(":memory:") as database:
            database.execute("CREATE TABLE line(n INTEGER, text BLOB)")
            database.executemany("INSERT INTO line VALUES(?, ?)", [(1, b"draw cable route"), (3, b"draw cable"), (9, b"cable route")])
            ids, masks, truncated, benchmark = scan(database, columns, cues, backend="numpy")
        self.assertEqual((ids.tolist(), masks.tolist(), truncated), ([1, 3, 9], [1, 0, 0], 0))
        self.assertIsNone(benchmark["cupy_seconds_including_transfers"])


if __name__ == "__main__":
    unittest.main()
