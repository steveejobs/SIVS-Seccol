import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server import ROLE_MODULES, ROLE_READ_MODULES, SIVSHandler, VALUE_SENSITIVE_MODULES


class LeastPrivilegePresetTests(unittest.TestCase):
    def test_generic_operator_is_not_a_cross_company_job_function(self):
        self.assertEqual(
            ROLE_MODULES["operator"],
            {"arquivos", "contatos", "ramais", "produtividade"},
        )
        self.assertTrue(ROLE_MODULES["operator"].isdisjoint(VALUE_SENSITIVE_MODULES))
        self.assertEqual(ROLE_READ_MODULES["operator"], ROLE_MODULES["operator"])

    def test_generic_viewer_does_not_receive_sensitive_areas_or_values(self):
        self.assertEqual(ROLE_MODULES["viewer"], set())
        self.assertEqual(ROLE_READ_MODULES["viewer"], {"arquivos", "produtividade"})
        self.assertTrue(ROLE_READ_MODULES["viewer"].isdisjoint(VALUE_SENSITIVE_MODULES))
        for module in ROLE_READ_MODULES["viewer"]:
            operations = SIVSHandler.operation_defaults(
                module, ROLE_READ_MODULES["viewer"], set(), "viewer",
            )
            self.assertNotIn("view_values", operations)
            self.assertNotIn("view_sensitive", operations)


if __name__ == "__main__":
    unittest.main()
