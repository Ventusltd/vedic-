import hashlib
import unittest
from unittest.mock import patch

from daily_source_policy import discover_candidates, pinned_functions, reproduce_candidate
from source_admissions import candidate_id, verify_policy_candidate


RAW = b"def validate_fixture(rows):\n    return len(rows)\n"
PIN = {
    "repo": "Ventusltd/fixture",
    "commit": "a" * 40,
    "path": "unit.py",
    "blob": hashlib.sha1(f"blob {len(RAW)}\0".encode() + RAW).hexdigest(),
}
CONTRACT = {
    "word": "COUNT FIXTURE ROWS",
    "purpose": "Count supplied fixture rows.",
    "inputs": ["fixture rows"],
    "output": "Number of supplied rows.",
    "limits": "Requires a sized collection.",
}


class SourcePolicyTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("daily_source_policy.PIN", PIN))
        self.enterContext(patch("daily_source_policy.CONTRACTS", {"validate_fixture": CONTRACT}))

    def test_candidate_is_reproducible_and_emitted_once_after_admission(self):
        draft = discover_candidates(RAW, {"records": []})
        candidate, = draft["records"]
        self.assertEqual(verify_policy_candidate(candidate, RAW),
                         verify_policy_candidate(candidate, RAW))
        self.assertEqual(reproduce_candidate(candidate["source"], RAW)["word"], CONTRACT["word"])
        archive = {"records": [{"candidate_id": candidate_id(candidate)}]}
        self.assertEqual(discover_candidates(RAW, archive)["records"], [])

    def test_pin_and_complete_span_are_required(self):
        anchor, _ = next(pinned_functions(RAW))
        with self.assertRaisesRegex(ValueError, "reviewed pin"):
            reproduce_candidate(anchor, RAW + b"\n")
        with self.assertRaisesRegex(ValueError, "Source span"):
            reproduce_candidate({**anchor, "last": anchor["last"] - 1}, RAW)
        with self.assertRaisesRegex(ValueError, "outside the reviewed"):
            reproduce_candidate({**anchor, "commit": "b" * 40}, RAW)

    def test_explicit_contract_requires_reviewed_blob_and_span(self):
        anchor = {**PIN, "repo": "Ventusltd/explicit-fixture", "first": 1, "last": 2}
        candidate = {**CONTRACT, "source": anchor, "symbol": "validate_fixture"}
        with patch("daily_source_policy.EXPLICIT_CONTRACTS", (candidate,)):
            self.assertEqual(reproduce_candidate(anchor, RAW), candidate)
            with self.assertRaisesRegex(ValueError, "blob differs"):
                reproduce_candidate(anchor, RAW + b"\n")
            with self.assertRaisesRegex(ValueError, "outside the reviewed"):
                reproduce_candidate({**anchor, "last": 1}, RAW)
