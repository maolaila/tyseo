"""Numeric zero must remain a score in every active z score component."""
import sys
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import ROOT, read_json


class ZScoreContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        task = ROOT / "tasks/local.json"
        repo = Path(read_json(task if task.exists() else ROOT / "tasks/bootstrap.json")["repo_root"])
        cls.repo = repo
        cls.env = Environment(loader=FileSystemLoader(str(repo / "templates")))

    def test_match_status_macros(self):
        cases = [(0, "0"), ("0", "0"), ("0-0", "0-0"), ("83-52", "83-52"), (None, "VS")]
        for number in range(7, 22):
            score = self.env.get_template(f"z{number}/macros/match_status.html").module.ms_score_view
            for value, expected in cases:
                with self.subTest(template=number, value=value):
                    self.assertEqual(score({"StatusUpName": "直播中", "StatusUp": 2,
                                            "MatchType": 1, "Score": value}).strip(), expected)
            self.assertEqual(score({"StatusUpName": "未开赛", "StatusUp": 1,
                                    "MatchType": 1, "Score": 0}).strip(), "VS")

    def test_legacy_hot_rows(self):
        item = {"MatchPinYin": "yingchao", "MatchID": 123, "IsHotMatch": True,
                "MatchTypePinYinFlag": "zuqiu", "MatchType": 1, "MatchTime": "2026-09-18 12:00:00",
                "MatchName": "英超", "HTeamName": "主队", "ATeamName": "客队",
                "HTeamLogo": "", "ATeamLogo": "", "StatusUpName": "直播中"}
        for number in (4, 5, 6):
            template = self.env.get_template(f"z{number}/widgets/match_row_hot.html")
            for value, expected in ((0, "0"), ("0", "0"), (None, "-")):
                with self.subTest(template=number, value=value):
                    html = BeautifulSoup(template.render(item={**item, "Score": value}), "html.parser")
                    self.assertEqual(html.select_one(f".z{number}-{'fix' if number == 4 else 'sch'}-score").get_text(strip=True), expected)

    def test_z14_live_hero_uses_real_score(self):
        hero = self.env.get_template("z14/macros/dash_hero.html").module.hero_slide
        item = {"MatchID": 1, "MatchPinYin": "yingchao", "MatchType": 1, "type": 1,
                "MatchName": "英超", "name": "英超", "HTeamName": "主队", "ATeamName": "客队",
                "StatusUpName": "直播中", "StatusUp": 2}
        for score, expected in ((0, "0"), ("83-52", "83-52"), (None, "VS")):
            with self.subTest(score=score):
                html = BeautifulSoup(hero({**item, "Score": score}, "站名"), "html.parser")
                self.assertEqual(html.select_one(".z14-dash-hero__matchline em").get_text(strip=True), expected)

    def test_z13_live_focus_does_not_invent_zero_zero(self):
        template = self.env.get_template("z13/widgets/sport_hub_focus.html")
        item = {"pinyin": "yingchao", "id": 123, "is_hot_match": True,
                "match_type_pinyin_flag": "zuqiu", "name": "英超",
                "hteam_name": "主队", "ateam_name": "客队", "hteam_logo": "", "ateam_logo": "",
                "StatusUpName": "直播中", "StatusUp": 2, "MatchType": 1}
        for score, expected in ((None, "VS"), (0, "0"), ("0-0", "0-0")):
            with self.subTest(score=score):
                html = BeautifulSoup(template.render(hub=SimpleNamespace(flat=[{**item, "score": score}])), "html.parser")
                self.assertEqual(html.select_one(".z13-fb-focus-vs strong").get_text(strip=True), expected)

    def test_detail_zb_preserves_zero_score(self):
        for number in range(1, 22):
            source = (self.repo / "templates" / f"z{number}" / "detail_zb.html").read_text(encoding="utf-8")
            statement = re.search(r"{% set has_match_score = .*? %}", source)
            self.assertIsNotNone(statement, f"z{number}")
            probe = self.env.from_string(statement.group(0) + "{% if has_match_score %}shown{% else %}hidden{% endif %}")
            for score, expected in ((0, "shown"), ("0", "shown"), (None, "hidden"), ("", "hidden")):
                with self.subTest(template=number, score=score):
                    self.assertEqual(probe.render(match_detail={"score": score}), expected)


if __name__ == "__main__":
    unittest.main()
