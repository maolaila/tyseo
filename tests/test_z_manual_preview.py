import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from z_manual_preview import existing_pages

class ManualScope(unittest.TestCase):
    def test_only_own_existing_pages_without_excluding_missing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'templates/z1').mkdir(parents=True)
            (root/'templates/z1/index.html').write_text('existing')
            (root/'templates/shared.html').write_text('shared')
            pages=[{'entry_template':v} for v in ('z1/index.html','z1/missing.html','shared.html','z2/index.html')]
            self.assertEqual(existing_pages(root,'z1',{'pages':pages}),[pages[0]])
