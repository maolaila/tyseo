"""证据要盖对检出，页面内容规则要能自动判定。"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import core  # noqa: E402
import z_content_rules  # noqa: E402


def fake_checkout(root, name='fake'):
    path = Path(root) / name
    path.mkdir(parents=True, exist_ok=True)
    (path / 'run.py').write_text('# 占位，只为让 resolve_repo_root 认它是业务检出\n', encoding='utf-8')
    return path


class ResolveRepoRoot(unittest.TestCase):
    def setUp(self):
        self.previous = os.environ.pop('PONY_REPO_ROOT', None)

    def tearDown(self):
        if self.previous is None:
            os.environ.pop('PONY_REPO_ROOT', None)
        else:
            os.environ['PONY_REPO_ROOT'] = self.previous

    def test_explicit_argument_wins_over_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            explicit, env = fake_checkout(tmp, 'explicit'), fake_checkout(tmp, 'env')
            os.environ['PONY_REPO_ROOT'] = str(env)
            self.assertEqual(core.resolve_repo_root(str(explicit)), explicit.resolve())

    def test_environment_wins_over_bootstrap_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = fake_checkout(tmp, 'env')
            os.environ['PONY_REPO_ROOT'] = str(env)
            self.assertEqual(core.resolve_repo_root(), env.resolve())

    def test_default_still_points_at_the_configured_checkout(self):
        self.assertTrue((core.resolve_repo_root() / 'run.py').is_file())

    def test_directory_without_run_py_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                core.resolve_repo_root(tmp)

    def test_provenance_records_branch_and_dirty_state(self):
        provenance = core.repo_provenance(core.resolve_repo_root())
        self.assertEqual(set(provenance), {'repo_root', 'commit', 'branch', 'dirty'})
        self.assertRegex(provenance['commit'], r'^[0-9a-f]{40}$')
        self.assertIsInstance(provenance['dirty'], bool)


class ContentRules(unittest.TestCase):
    def test_none_in_page_text_is_reported(self):
        self.assertTrue(z_content_rules.NONE_TEXT.search('<td>None</td>'))
        self.assertTrue(z_content_rules.NONE_TEXT.search('<td> None </td>'))

    def test_legitimate_words_are_not_confused_with_none(self):
        self.assertIsNone(z_content_rules.NONE_TEXT.search('<td>Nonexistent</td>'))
        self.assertIsNone(z_content_rules.NONE_TEXT.search('<td>0</td>'))

    def test_markdown_left_in_page_is_reported(self):
        for raw in ('### 现任教练', '**队史得分王**', '| 球员 | 备注 |'):
            self.assertTrue(z_content_rules.MARKDOWN.search(raw), raw)

    def test_rendered_html_is_not_reported_as_markdown(self):
        self.assertIsNone(z_content_rules.MARKDOWN.search('<h3>现任教练</h3><strong>队史得分王</strong>'))


if __name__ == '__main__':
    unittest.main()
