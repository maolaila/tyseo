"""Empty backend data must not become fictional matches or statistics."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import ROOT, read_json


class ZEmptyStates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        task = ROOT / "tasks/local.json"
        repo = Path(read_json(task if task.exists() else ROOT / "tasks/bootstrap.json")["repo_root"])
        cls.env = Environment(loader=FileSystemLoader(str(repo / "templates")))

    def test_football_widgets_have_honest_empty_states(self):
        for number in range(14, 22):
            for name, expected in (("news", "暂无最新资讯"), ("hosts", "暂无主播信息"),
                                   ("live_matches", "暂无足球赛事"), ("focus_matches", "暂无焦点赛事")):
                with self.subTest(template=number, widget=name):
                    html = self.env.get_template(f"z{number}/widgets/football/{name}.html").render(
                        list_news=[], list_result=[], list_match_data=[], fb_sched_url="/allmatch")
                    self.assertIn(expected, html)
                    self.assertNotIn("/10001.html", html)
                    self.assertNotIn("解说老王", html)
                    self.assertNotIn("12.6万", html)

    def test_portal_widgets_have_no_fake_match_links(self):
        for number in range(16, 21):
            for name, expected in (("hot_live", "暂无热门赛事"), ("today_schedule", "暂无赛程数据")):
                with self.subTest(template=number, widget=name):
                    html = self.env.get_template(f"z{number}/widgets/football-portal/{name}.html").render(
                        fp_pool=SimpleNamespace(items=[]), fp_is_bb=False, recap_skip_ended=False)
                    self.assertIn(expected, html)
                    self.assertNotIn("/10001.html", html)

    def test_z15_live_empty_rows_are_not_invented(self):
        context = {"fl_stand_leagues": SimpleNamespace(items=[]), "fl_pool": SimpleNamespace(items=[]),
                   "sl_py": "lanqiu", "sl_stand_league": "NBA", "sl_stand_url": "/nba/paihangbang"}
        standings = self.env.get_template("z15/widgets/football-live/standings.html").render(**context)
        ticker = self.env.get_template("z15/widgets/football-live/live_ticker.html").render(**context)
        self.assertIn("暂无积分榜数据", standings)
        self.assertIn("暂无实时赛况", ticker)
        self.assertNotIn("凯尔特人", standings)
        self.assertNotIn("98 - 92", ticker)

    def test_z14_focal_empty_state_has_no_fictional_fixture(self):
        html = self.env.get_template("z14/macros/dash_hero.html").module.hero_placeholder()
        self.assertIn("暂无可显示的焦点赛事", html)
        self.assertIn('href="/allmatch"', html)
        self.assertNotIn("利物浦", html)
        self.assertNotIn("5月11日", html)


if __name__ == "__main__":
    unittest.main()
