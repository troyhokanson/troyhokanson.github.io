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
        self.assertIn("evidence.html", portfolio_health.HTML_FILES)
        contract = json.loads((ROOT / "portfolio_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(
            contract["production_repository"],
            "troyhokanson/troyhokanson.github.io",
        )
        self.assertIn("practice.html", contract["pages"])
        self.assertIn("evidence.html", contract["pages"])

    def test_field_training_tenure_uses_date_range_until_duration_is_reconciled(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        practice = (ROOT / "practice.html").read_text(encoding="utf-8")
        self.assertIn("Field Training Officer, 2004–2023", index)
        self.assertIn("Field Training Officer from 2004–2023", practice)
        self.assertNotRegex(index, r"(?:18|19)[- ]year Field Training Officer")


    def test_homepage_uses_governing_career_headline(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        headline = (
            "Former Detective &amp; Digital Forensic Examiner | "
            "Public-Safety Software Training, Technical Support &amp; Evidence Workflows"
        )
        self.assertIn(headline, index)

    def test_current_public_chronology_is_visible(self):
        index = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Independent Professional | April 2026–Present", index)
        self.assertIn("eXp Realty and Keller Williams | June 2024–June 2026", index)

    def test_public_credentials_exclude_private_links_and_disputed_ftk_hours(self):
        credentials = (ROOT / "credentials.html").read_text(encoding="utf-8")
        self.assertNotIn("drive.google.com", credentials)
        self.assertNotIn("docs.google.com", credentials)
        self.assertIn("disputed FTK hour count is intentionally omitted", credentials)
        self.assertNotRegex(credentials, r"(?:21|25)\s+hours?.{0,100}(?:FTK|Forensic Toolkit)")

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


    def test_evidence_page_has_stable_public_anchors(self):
        source = (ROOT / "evidence.html").read_text(encoding="utf-8")
        required_ids = (
            "PR-2020-DIGITAL-FORENSICS-RESOURCE",
            "PR-2019-RESOURCE-BUILDER",
            "COM-2019-COMMERCIAL-BURGLARY",
            "COM-2013-PATROL-FOLLOW-UP",
            "COMMENDATIONS-20PLUS",
            "CASE-BEC-360K",
            "AWARD-PHOENIX500",
        )
        for evidence_id in required_ids:
            self.assertIn(f'id="{evidence_id}"', source)

    def test_evidence_page_uses_sanitized_public_sources(self):
        source = (ROOT / "evidence.html").read_text(encoding="utf-8")
        self.assertNotIn("drive.google.com", source)
        self.assertNotIn("notion.", source)
        self.assertNotIn("$295,704.11", source)
        self.assertNotIn("15-year federal sentence", source)
        self.assertNotIn("Supervisor:", source)
        self.assertIn("self-published provenance record", source)


if __name__ == "__main__":
    unittest.main()
