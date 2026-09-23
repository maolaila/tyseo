import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from core import resolve_repo_root


ROOT = Path(__file__).resolve().parents[1]


class R62AlignedCases(unittest.TestCase):
    def test_common_cases_match_r62_baseline(self):
        cases = json.loads((ROOT / 'config/final-user-cases.json').read_text(encoding='utf-8'))
        self.assertEqual(cases['reference_template_id'], 'r62')
        self.assertIn('live-detail-playback-link-nofollow', cases['common'])
        self.assertIn('mobile-menu-open-close', cases['common'])
        self.assertTrue({'desktop-navigation', 'more-events-menu', 'home-match-tabs'} <= set(cases['common']))
        self.assertFalse({'search-button-and-enter', 'goto-top'} & set(cases['common']))

    def test_runner_does_not_require_features_absent_from_r62(self):
        runner = (ROOT / 'scripts/cli-final-user-journeys.js').read_text(encoding='utf-8')
        for removed_rule in ('SITE-SEARCH', 'THEME-TOGGLE', 'GOTO-TOP'):
            self.assertNotIn(removed_rule, runner)
        self.assertIn('MOBILE-MENU', runner)
        self.assertIn('LIVE-DETAIL-PLAYBACK-NOFOLLOW', runner)
        self.assertIn('MORE-EVENTS-MENU', runner)

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
