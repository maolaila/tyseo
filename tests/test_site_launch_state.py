import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from site_launch_state import completion

class CompletionGate(unittest.TestCase):
    def test_no_receipt_cannot_finish(self):
        self.assertFalse(completion({'expected_count':1,'domains':[{'domain':'example.test','status':'verified'}]})['completed'])
    def test_inventory_mismatch(self):
        self.assertFalse(completion({'expected_count':20,'domains':[]})['completed'])
    def test_verified_with_evidence(self):
        item={'domain':'example.test','status':'verified','purchase_evidence':'sheet-observation',
              'submission':{'status':'confirmed','evidence':'receipt'},'verification':{'status':'passed','evidence':'site-check'}}
        self.assertTrue(completion({'expected_count':1,'domains':[item]})['completed'])
        item['submission']['status']='unknown'
        self.assertFalse(completion({'expected_count':1,'domains':[item]})['completed'])

if __name__=='__main__':unittest.main()
