"""Regression checks for exact command lookup and the package admission boundary."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from semantic_compiler import (BINDINGS, DICTIONARY, Refusal, execute, resolve,
                               strict_json)


class CommandCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dictionary = strict_json(DICTIONARY.read_bytes())
        cls.registry = strict_json(BINDINGS.read_bytes())

    def plan(self, phrase, sense_id=None):
        return resolve(phrase, self.dictionary, self.registry, sense_id)

    def test_every_dictionary_name_resolves_by_its_existing_id(self):
        for row in self.dictionary["entries"]:
            with self.subTest(command=row["gg_id"]):
                self.assertEqual(self.plan(row["word"], row["gg_id"])["command_id"], row["gg_id"])

    def test_alias_keeps_the_existing_composition_identity(self):
        canonical = self.plan("ORIENT")
        self.assertEqual(canonical, self.plan(" Measure distance and bearing "))
        self.assertEqual(canonical["components"], [row["vedic_id"] for row in canonical["operations"]])
        self.assertEqual(canonical["execution_readiness"], "PRIVATE_FACTORY_PACKAGE")
        self.assertFalse(canonical["independent_package_acceptance"])

    def test_homonym_requires_an_explicit_existing_sense(self):
        with self.assertRaisesRegex(Refusal, "AMBIGUOUS_COMMAND") as caught:
            self.plan("AREA")
        self.assertEqual(caught.exception.details["candidates"],
                         ["GG2050-VEDIC-000017", "GG2050-VEDIC-000019"])
        self.assertEqual(self.plan("AREA", "GG2050-VEDIC-000019")["command_id"], "GG2050-VEDIC-000019")

    def test_refuses_dictionary_binding_drift_and_alias_collision(self):
        changed = deepcopy(self.dictionary)
        next(row for row in changed["entries"] if row["word"] == "ORIENT")["components"].reverse()
        with self.assertRaisesRegex(Refusal, "DICTIONARY_BINDING_DRIFT"):
            resolve("ORIENT", changed, self.registry)
        other = deepcopy(self.dictionary)
        other["entries"][0]["aliases"] = ["Measure Distance and Bearing"]
        with self.assertRaisesRegex(Refusal, "AMBIGUOUS_COMMAND"):
            resolve("measure distance and bearing", other, self.registry)

    def test_discards_unrecognised_free_text_and_nonfinite_input(self):
        for text in ("guess the voltage", "measure voltage; orient", "Orıent", "please could you measure the distance"):
            with self.subTest(text=text), self.assertRaises(Refusal):
                self.plan(text)
        for raw, expected in ((b'{"a":1,"a":2}', "DUPLICATE_JSON_KEY"),
                              (b'{"a":1e400}', "NONFINITE_INPUT"),
                              (b'{"a":NaN}', "NONFINITE_INPUT")):
            with self.subTest(raw=raw), self.assertRaisesRegex(Refusal, expected):
                strict_json(raw)

    def test_unadmitted_meaning_refuses_before_reading_artifacts(self):
        with self.assertRaisesRegex(Refusal, "PACKAGE_NOT_ADMITTED"):
            execute(self.plan("CHECK POWER CAP"), {}, None, None, None)

    def test_tampered_archive_refuses_before_staging_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tampered"
            path.write_bytes(b"tampered evidence")
            with self.assertRaisesRegex(Refusal, "PACKAGE_EVIDENCE_MISMATCH"):
                execute(self.plan("ORIENT"), {}, None, path, path)


if __name__ == "__main__":
    unittest.main()
