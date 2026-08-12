import importlib.util
import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_health.py"
WORKFLOW = ROOT / ".github" / "workflows" / "portfolio-health.yml"
SPEC = importlib.util.spec_from_file_location("portfolio_health", SCRIPT)
portfolio_health = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(portfolio_health)


class PortfolioHealthTests(unittest.TestCase):
    def test_repository_passes_four_local_audit_layers(self):
        result = portfolio_health.run(check_live=False, fix=False)
        self.assertEqual(result["status"], "passed", result["issues"])

    def test_auto_fixer_is_idempotent(self):
        self.assertEqual(portfolio_health.apply_safe_fixes(), [])

    def test_twice_daily_schedule_is_central_time_dst_safe(self):
        source = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "15 0,1,12,13 * * *"', source)
        self.assertIn("TZ=America/Chicago", source)
        self.assertIn('== "07"', source)
        self.assertIn('== "19"', source)
        self.assertIn("needs: schedule-gate", source)

    def test_privacy_contract_uses_generic_license_detection(self):
        contract_path = ROOT / "portfolio_contract.json"
        contract = json.loads(contract_path.read_text(encoding="utf-8"))

        for pattern in contract["forbidden_patterns"]:
            self.assertIsNone(re.search(r"\d{4,}", pattern))

        samples = (
            "Minnesota license #12345",
            "Minnesota License Number: 12345",
            "Minnesota License #: 12345",
        )
        for sample in samples:
            self.assertTrue(any(
                re.search(pattern, sample)
                for pattern in contract["forbidden_patterns"]
            ))


    def test_consolidated_public_pages_are_audited(self):
        self.assertIn("practice.html", portfolio_health.HTML_FILES)
        contract = json.loads((ROOT / "portfolio_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(
            contract["production_repository"],
            "troyhokanson/troyhokanson.github.io",
        )
        self.assertIn("practice.html", contract["pages"])

    def test_field_training_tenure_is_current(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        practice = (ROOT / "practice.html").read_text(encoding="utf-8")
        self.assertIn("19-year Field Training Officer", index)
        self.assertIn("Field Training Officer from 2004–2023", practice)
        self.assertNotIn("18-year Field Training Officer", index)


    def test_stale_commendation_total_is_blocked(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        credentials = (ROOT / "credentials.html").read_text(encoding="utf-8")
        contract = json.loads((ROOT / "portfolio_contract.json").read_text(encoding="utf-8"))
        combined = index + " " + credentials
        self.assertNotIn("20+ written professional commendations", combined)
        self.assertIn("Documented professional recognition", index)
        self.assertTrue(any(
            re.search(pattern, "20+ written professional commendations")
            for pattern in contract["forbidden_patterns"]
        ))


if __name__ == "__main__":
    unittest.main()
