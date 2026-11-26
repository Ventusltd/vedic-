import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from shutil import which
from types import SimpleNamespace
from unittest.mock import patch

from family_pulse import write
from source_admissions import (
    BASE, POLICY, SCHEMA, make_policy_receipt, prepare, replay, stage_proposal,
    verify_policy_candidate, verify_policy_receipt,
)
from source_evidence import source_link, verify_exact_span, verify_lightning_initializer

MANIFEST = "a" * 40
TIME = "2026-11-26T00:00:00Z"
PYTHON = b"@dec\ndef firstCommand(x):\n    if x:\n        return 10\n    return 0\n"
JAVASCRIPT = b"export function firstCommand(x) {\n  if (x) {\n    return '}';\n  }\n  return 0;\n}\n"


def source(raw, path="engine/test.py", first=1, last=5):
    blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    return {"repo": "Ventusltd/test", "commit": "b" * 40, "blob": blob,
            "path": path, "first": first, "last": last}


def candidate(word="FIRST COMMAND", symbol="firstCommand", first=10):
    src = source(PYTHON, first=first, last=first + 2)
    row = {
        "word": word, "symbol": symbol, "purpose": "Purpose of " + word,
        "limits": "Source contract only", "inputs": ["x"], "output": "result",
        "estate_group": "Test", "discipline": "Test", "periodic_category": "Test",
        "vedic_class_candidate": "Computation", "aliases": [],
        "source": src, "receipt": source_link(src),
    }
    row["policy_receipt"] = make_policy_receipt(row, PYTHON)
    return row


def dictionary():
    return {"entries": [], "next_number": 1}


def archive():
    return {"schema": SCHEMA, "baseline_commit": BASE, "records": []}


def queue(*records):
    return {"schema": "vedic.source-candidates.v1", "records": list(records)}


def policy_modules(canonical):
    module = SimpleNamespace(POLICY=POLICY, reproduce_candidate=lambda source, raw: canonical)
    return patch.dict(sys.modules, {"daily_source_policy": module})


class AdmissionTests(unittest.TestCase):
    def test_bad_record_does_not_consume_id(self):
        d, a = dictionary(), archive()
        good = candidate()
        bad = candidate("lowercase", "bad", 20)
        added, held = prepare(d, a, queue(bad, good), MANIFEST, TIME, lambda candidate: None)
        self.assertEqual((added, len(held), d["next_number"]), (["GG2050-VEDIC-000001"], 1, 2))

    def test_bounded_drain_and_exact_replay(self):
        d, a = dictionary(), archive()
        q = queue(*(candidate(f"COMMAND {i}", f"cmd{i}", 10 + i * 4) for i in range(21)))
        self.assertEqual(len(prepare(d, a, q, MANIFEST, TIME, lambda candidate: None)[0]), 20)
        self.assertEqual(len(prepare(d, a, q, MANIFEST, TIME, lambda candidate: None)[0]), 1)
        self.assertEqual(prepare(d, a, q, MANIFEST, TIME, lambda candidate: None)[0], [])
        expected = replay(dictionary(), a, lambda manifest, path: q, lambda manifest: TIME)
        self.assertEqual(expected, d)
        self.assertEqual([e["number"] for e in d["entries"]], list(range(1, 22)))

    def test_duplicate_symbol_and_source(self):
        d, a = dictionary(), archive()
        q = queue(candidate(), candidate("SECOND", "firstCommand", 20), candidate("THIRD", "third", 11))
        added, held = prepare(d, a, q, MANIFEST, TIME, lambda candidate: None)
        self.assertEqual((len(added), len(held)), (1, 2))

    def test_check_failure_rolls_back(self):
        d, a = dictionary(), archive()
        q = queue(candidate(), candidate("SECOND", "second", 20))

        def check(candidate):
            if candidate["word"] == "FIRST COMMAND":
                raise ValueError("source mismatch")

        added, held = prepare(d, a, q, MANIFEST, TIME, check)
        self.assertEqual((len(added), len(held), d["entries"][0]["number"]), (1, 1, 1))

    def test_archive_tamper(self):
        d, a = dictionary(), archive()
        q = queue(candidate())
        prepare(d, a, q, MANIFEST, TIME, lambda candidate: None)
        a["records"][0]["candidate"] = copy.deepcopy(a["records"][0]["candidate"])
        a["records"][0]["candidate"]["purpose"] = "tampered"
        with self.assertRaisesRegex(ValueError, "archive evidence mismatch"):
            replay(dictionary(), a, lambda manifest, path: q, lambda manifest: TIME)

    def test_legacy_prefix_is_immutable(self):
        legacy = [{"candidate_id": "historic"}]
        with self.assertRaisesRegex(ValueError, "legacy source-admission archive prefix"):
            replay(dictionary(), archive(), legacy_records=legacy)

    def test_new_candidates_refuse_dangling_human_review(self):
        proposed = candidate()
        proposed["receipt"] = "https://github.com/Ventusltd/neural-link-between-agents/issues/87#issuecomment-"
        proposed["policy_receipt"] = make_policy_receipt(proposed, PYTHON)
        with self.assertRaisesRegex(ValueError, "exact pinned source"):
            verify_policy_receipt(proposed)
        proposed.pop("policy_receipt")
        _, held = prepare(dictionary(), archive(), queue(proposed), MANIFEST, TIME,
                          lambda candidate: self.fail("unreviewed candidate must not reach the checker"))
        self.assertIn("strict policy receipt", held[0]["reason"])

    def test_policy_reproduction_rejects_changed_contract_even_with_recomputed_receipt(self):
        accepted = candidate(first=1)
        accepted["source"]["last"] = 5
        accepted["receipt"] = source_link(accepted["source"])
        accepted["policy_receipt"] = make_policy_receipt(accepted, PYTHON)
        canonical = {key: value for key, value in accepted.items() if key != "policy_receipt"}
        with policy_modules(canonical):
            verify_policy_candidate(accepted, PYTHON)
            for field in ("purpose", "output"):
                changed = dict(accepted, **{field: "Different value"})
                with self.assertRaisesRegex(ValueError, "does not bind candidate contract"):
                    verify_policy_candidate(changed, PYTHON)
                changed["policy_receipt"] = make_policy_receipt(changed, PYTHON)
                with self.assertRaisesRegex(ValueError, "differs from exact policy reproduction"):
                    verify_policy_candidate(changed, PYTHON)

    def test_stage_proposal_does_not_expose_incomplete_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            dest = parent / "proposal"

            def write_one(path, value):
                if path.name == "admitted-queue-archive.json":
                    raise OSError("simulated failed second write")
                write(path, value)

            with patch("source_admissions.write", side_effect=write_one):
                with self.assertRaisesRegex(OSError, "second write"):
                    stage_proposal(dest, dictionary(), archive())
            self.assertFalse(dest.exists())
            self.assertFalse(list(parent.iterdir()))
            stage_proposal(dest, dictionary(), archive())
            self.assertEqual(sorted(p.name for p in (dest / "data").iterdir()),
                             ["admitted-queue-archive.json", "dictionary.json"])
            with self.assertRaisesRegex(ValueError, "destination already exists"):
                stage_proposal(dest, dictionary(), archive())


class SourceBoundaryTests(unittest.TestCase):
    def test_python_requires_exact_top_level_span_including_decorator(self):
        pin = source(PYTHON)
        verify_exact_span(pin, "firstCommand", PYTHON)
        for mismatched in (dict(pin, first=2), dict(pin, last=4)):
            with self.assertRaisesRegex(ValueError, "unique complete top-level function"):
                verify_exact_span(mismatched, "firstCommand", PYTHON)
        with self.assertRaisesRegex(ValueError, "pinned evidence"):
            verify_exact_span(pin, "firstCommand", PYTHON + b"\n")
        nested = b"def outer():\n    def firstCommand():\n        pass\n"
        with self.assertRaisesRegex(ValueError, "unique complete top-level function"):
            verify_exact_span(source(nested, first=2, last=3), "firstCommand", nested)

    @unittest.skipUnless(which("node"), "JavaScript syntax checking requires Node")
    def test_javascript_masks_strings_and_refuses_inner_brace_as_end(self):
        pin = source(JAVASCRIPT, "engine/test.js", last=6)
        verify_exact_span(pin, "firstCommand", JAVASCRIPT)
        with self.assertRaisesRegex(ValueError, "unique complete top-level function"):
            verify_exact_span(dict(pin, last=4), "firstCommand", JAVASCRIPT)

    @unittest.skipUnless(which("node"), "JavaScript syntax checking requires Node")
    def test_javascript_refuses_unbalanced_and_unsupported_source(self):
        for body, error in ((JAVASCRIPT[:-2], "invalid JavaScript source"),
                            (JAVASCRIPT.replace(b"'}'", b"/}/"), "lexical construct")):
            with self.assertRaisesRegex(ValueError, error):
                verify_exact_span(source(body, "engine/test.js", last=6), "firstCommand", body)

    @unittest.skipUnless(which("node"), "JavaScript syntax checking requires Node")
    def test_reviewed_initializer_requires_complete_unique_assignment(self):
        sample = (
            b"(() => {\n"
            b"  const label = `Lightning`;\n"
            b"  window.initVentusMap = function addPublicLightningLayer(options) {\n"
            b"    return originalInit.call(this, options);\n"
            b"  };\n"
            b"})();\n"
        )
        verify_lightning_initializer(sample, 3, 5)
        with self.assertRaisesRegex(ValueError, "unclosed"):
            verify_lightning_initializer(sample, 3, 4)
        with self.assertRaisesRegex(ValueError, "complete assignment"):
            verify_lightning_initializer(sample, 3, 6)
        with self.assertRaisesRegex(ValueError, "reviewed assignment"):
            verify_lightning_initializer(sample + sample, 3, 5)
