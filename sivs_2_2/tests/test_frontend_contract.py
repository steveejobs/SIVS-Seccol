import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "static" / "index.html").read_text(encoding="utf-8")


class FrontendContractTests(unittest.TestCase):
    def test_every_schema_has_a_specialized_registration_profile(self):
        schema_block = APP.split("const schemas = {", 1)[1].split("\n};\n\nconst formDomains", 1)[0]
        profile_block = APP.split("const registrationProfiles = {", 1)[1].split(
            "\n};\n\nfunction getRecordProfile", 1
        )[0]
        schemas = set(re.findall(r"^  ([a-z_]+): \[", schema_block, re.MULTILINE))
        profiles = set(re.findall(r"^  ([a-z_]+): P\(", profile_block, re.MULTILINE))
        self.assertEqual(46, len(schemas))
        self.assertEqual(schemas, profiles)

    def test_specialized_form_keeps_subject_and_governance_contract(self):
        required_ids = {
            "recordProfileHero", "recordProgressValue", "recordIdentification",
            "recordSpecifics", "recordRelationships", "recordGovernance",
            "dynamicFields", "relationshipList", "recordResources",
        }
        ids = set(re.findall(r'id="([A-Za-z][A-Za-z0-9_-]+)"', INDEX))
        self.assertTrue(required_ids.issubset(ids))
        self.assertIn('name="assunto" required', INDEX)
        self.assertIn("function validateSpecializedRecord", APP)
        self.assertIn("function updateRecordCompleteness", APP)

    def test_static_html_has_no_duplicate_ids(self):
        ids = re.findall(r'id="([A-Za-z][A-Za-z0-9_-]+)"', INDEX)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
