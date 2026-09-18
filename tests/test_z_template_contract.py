"""Company-wide z-template source contracts before browser acceptance."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import ROOT, read_json


class ZTemplateContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        task = ROOT / "tasks/local.json"
        cls.repo = Path(read_json(task if task.exists() else ROOT / "tasks/bootstrap.json")["repo_root"])

    def test_dynamic_injections_and_app_scripts(self):
        for number in range(1, 22):
            with self.subTest(template=number):
                source = (self.repo / "templates" / f"z{number}" / "master.html").read_text(encoding="utf-8-sig")
                for dynamic in ("website_config.HeaderJS", "website_config.FooterJS"):
                    self.assertIn(dynamic, source)
                self.assertLess(source.index('/static/js/jquery.min.js'), source.index('/static/js/ajs.js'))

    def test_team_pages_have_one_main_heading(self):
        for number in range(1, 22):
            for page in ("team_info", "team_match_list", "team_player"):
                with self.subTest(template=number, page=page):
                    source = (self.repo / "templates" / f"z{number}" / f"{page}.html").read_text(encoding="utf-8-sig")
                    self.assertEqual(len(re.findall(r"<h1(?:\s|>)", source)), 1)

    def test_no_pseudo_filter_links(self):
        for number in range(1, 22):
            for path in (self.repo / "templates" / f"z{number}").rglob("*.html"):
                with self.subTest(path=str(path)):
                    self.assertNotIn("javascript:void(0)", path.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
