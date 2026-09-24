import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import resolve_repo_root


ROOT = Path(__file__).resolve().parents[1]


class BaselineAlignedCases(unittest.TestCase):
    """功能基线 2026-09-24 由 r62 改为 z18 / z22（用户明确）。"""

    def test_common_cases_match_the_new_baseline(self):
        cases = json.loads((ROOT / 'config/final-user-cases.json').read_text(encoding='utf-8'))
        self.assertEqual(cases['reference_template_id'], ['z18', 'z22'])
        self.assertIn('live-detail-playback-link-nofollow', cases['common'])
        self.assertIn('mobile-menu-open-close', cases['common'])
        self.assertTrue({'desktop-navigation', 'more-events-menu', 'home-match-tabs'} <= set(cases['common']))
        # z18 / z22 这三项都有，所以重新是必备
        self.assertTrue({'site-search', 'theme-toggle-and-persist', 'goto-top'} <= set(cases['common']))

    def test_runner_checks_the_features_the_baseline_has(self):
        runner = (ROOT / 'scripts/cli-final-user-journeys.js').read_text(encoding='utf-8')
        for rule in ('SITE-SEARCH', 'THEME-TOGGLE', 'GOTO-TOP',
                     'MOBILE-MENU', 'LIVE-DETAIL-PLAYBACK-NOFOLLOW', 'MORE-EVENTS-MENU'):
            self.assertIn(rule, runner)

    def test_runner_recognises_the_baseline_control_names(self):
        runner = (ROOT / 'scripts/cli-final-user-journeys.js').read_text(encoding='utf-8')
        # z22 的回顶叫 ar-totop / #ar-top，不是 scroll-to-top；选择器要认得出来
        self.assertIn('data-ar-totop', runner)
        self.assertIn('#ar-top', runner)

    def test_r62_and_pony_templates_mark_playback_links_nofollow(self):
        repo = resolve_repo_root()
        template_ids = ['r62', *[f'z{i}' for i in range(1, 19)]]
        for template_id in template_ids:
            path = repo / 'templates' / template_id / 'detail_zb.html'
            if not path.exists():
                continue
            source = path.read_text(encoding='utf-8')
            links = re.findall(r'<a\b(?:(?!</a>).)*?/play/(?:(?!</a>).)*?>', source, re.I | re.S)
            self.assertTrue(links, f'{template_id} has no playback link to verify')
            for link in links:
                rel = re.search(r'\brel\s*=\s*["\']([^"\']*)', link, re.I)
                self.assertIsNotNone(rel, f'{template_id} playback link is missing rel')
                self.assertIn('nofollow', rel.group(1).split(), f'{template_id} playback link is missing nofollow')


if __name__ == '__main__':
    unittest.main()
