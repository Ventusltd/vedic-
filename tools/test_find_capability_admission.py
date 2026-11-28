import unittest

from semantic_compiler import BINDINGS, DICTIONARY, Refusal, execute, resolve, strict_json


class FindCapabilityAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.dictionary = strict_json(DICTIONARY.read_bytes())
        self.bindings = strict_json(BINDINGS.read_bytes())

    def test_reviewed_source_row_resolves_without_claiming_a_runtime_binding(self):
        plan = resolve("  find\tcapability  ", self.dictionary, self.bindings)
        self.assertEqual(plan["command_id"], "GG2050-VEDIC-000095")
        self.assertEqual(plan["canonical"], "FIND CAPABILITY")
        self.assertEqual(plan["dictionary_status"], "STATIC_POLICY_REPRODUCED")
        self.assertEqual(plan["execution_readiness"], "NO_REVIEWED_PACKAGE_BINDING")
        self.assertNotIn(plan["command_id"], self.bindings["bindings"])

    def test_executor_refuses_static_row_before_accessing_package_material(self):
        plan = resolve("FIND CAPABILITY", self.dictionary, self.bindings)
        with self.assertRaisesRegex(Refusal, "^PACKAGE_NOT_ADMITTED$"):
            execute(plan, {"objective": "audit a captured component"}, None, None, None)


if __name__ == "__main__":
    unittest.main()
