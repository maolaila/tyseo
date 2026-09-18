import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('migration',Path(__file__).resolve().parents[1]/'scripts/migrate.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class MigrationTests(unittest.TestCase):
    def test_round_trip_and_wrong_key(self):
        old=m.ROOT
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);m.ROOT=base/'tools';m.ROOT.mkdir();(m.ROOT/'runs').mkdir()
            (m.ROOT/'runs/evidence.txt').write_text('test evidence')
            business=base/'business';business.mkdir();(business/'.env').write_text('EXAMPLE=fixture-only-secret')
            key=base/'private/key';result=m.pack(key,business)
            self.assertEqual(result['files'],2)
            wrong=base/'wrong';wrong.write_bytes(b'x'*32)
            with self.assertRaises(ValueError):m.restore(wrong,base/'bad')
            self.assertFalse(any((base/'bad').iterdir()))
            m.restore(key,base/'restored')
            self.assertEqual((base/'restored/private/business/.env').read_text(),'EXAMPLE=fixture-only-secret')
            with self.assertRaises(ValueError):m.restore(key,base/'restored')
        m.ROOT=old

if __name__=='__main__':unittest.main()
