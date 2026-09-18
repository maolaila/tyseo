"""Failed real-page matrix rows must carry a reviewable location and expectation."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from z_acceptance import decorate_failures


class FailureEvidence(unittest.TestCase):
    def test_overflow_and_theme_failure_have_required_context(self):
        contract = {"pages": [{"page_type_id": "index", "http_samples": [{"path": "/", "status": 200}]}]}
        row = {"page_type_id": "index", "status": "fail", "width": 390, "theme": "dark",
               "javascript": True, "engine": "chromium", "environment": "real_app",
               "metrics": {"scrollWidth": 430, "bodyText": 800},
               "theme_state": {"requested": "dark", "observed": "light", "state_matches": False},
               "evidence_paths": ["screenshots/index.png"]}
        findings = decorate_failures([row], contract)[0]["findings"]
        self.assertEqual({f["rule_id"] for f in findings}, {"LAYOUT-PAGE-OVERFLOW", "THEME-STATE-MISMATCH"})
        for finding in findings:
            for key in ("rule_id", "page", "viewport", "theme", "data_state", "selector",
                        "expected", "actual", "severity", "owner_layer", "evidence_paths"):
                self.assertIn(key, finding)
            self.assertEqual(finding["page"], "/")


if __name__ == "__main__":
    unittest.main()
