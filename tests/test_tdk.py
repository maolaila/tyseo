import unittest,sys,copy,json,tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tdk import generate_tdk,prepare_updates,require_leo_approval,backend_script
from workbench import Monitor

class TdkTests(unittest.TestCase):
    def test_brand_and_supported_claims(self):
        for name in ('球帝直播','纬来体育直播','360直播'):
            d=generate_tdk(name)
            for k in ('title','description','keywords'):self.assertIn(name,d[k]);self.assertNotIn('官网',d[k])
            self.assertEqual(d['review_status'],'pending')
        with self.assertRaises(ValueError):generate_tdk('=INJECTION')
    def test_preserve_existing_content(self):
        row={'domain':'example.com','owner':'Pony','keyword':'球帝直播','row':3,'cells':['']*17}
        domains=[{'domain':'example.com','keyword':'球帝直播','status':'awaiting_tdk_worker'}]
        updates,_=prepare_updates(domains,{'pending':[],'launch':[row]});self.assertEqual(len(updates),1)
        row['cells'][5]='Human edit'
        with self.assertRaises(ValueError):prepare_updates(domains,{'pending':[],'launch':[row]})
    def test_leo_gate_binds_revision(self):
        item={'tdk':generate_tdk('球帝直播')}
        with self.assertRaises(ValueError):require_leo_approval(item)
        item['leo_review']={'reviewer':'Leo','status':'approved','evidence':'message','revision':item['tdk']['revision']}
        require_leo_approval(item);item['tdk']['revision']='changed'
        with self.assertRaises(ValueError):require_leo_approval(item)
    def test_backend_server_mismatch_blocks_prefill(self):
        draft=generate_tdk('球帝直播');item={'domain':'example.com','keyword':'球帝直播','tdk':draft}
        cells=['']*17;cells[4:8]=[draft[k] for k in ('template','title','description','keywords')];cells[12]='s213017'
        cells[16]='$'.join(['example.com','球帝直播',draft['title'],draft['description'],draft['keywords'],'r62',*(['']*8)])
        row={'domain':'example.com','owner':'Pony','cells':cells}
        with self.assertRaisesRegex(ValueError,'服务器'):backend_script([item],{'launch':[row]})
    def test_scan_prepares_but_never_writes(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','keyword':'球帝直播','status':'waiting_purchase'}]}))
            class Connector:
                def read(self):return {'pending':[],'launch':[{'domain':'example.com','owner':'Pony','keyword':'球帝直播','row':3,'cells':['']*17}]}
                def write_tdk(self,updates):raise AssertionError('Scheduled scans must not write')
            m=Monitor(path);m.connector=Connector();m.scan()
            self.assertEqual(m.state['domains'][0]['status'],'awaiting_user_confirmation')
            self.assertEqual(m.state['monitor']['status'],'review_required')
    def test_manual_write_waits_for_leo(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','keyword':'球帝直播','status':'waiting_purchase'}]}))
            class Connector:
                writes=0
                row={'domain':'example.com','owner':'Pony','keyword':'球帝直播','row':3,'cells':['']*17}
                def read(self):return {'pending':[],'launch':[copy.deepcopy(self.row)]}
                def write_tdk(self,updates):
                    self.writes+=1;self.row['cells'][4:8]=updates[0]['values'];return self.read()
            m=Monitor(path);m.connector=Connector();m.scan();m.fill_sheet(m.draft_revision())
            self.assertEqual(m.connector.writes,1);self.assertEqual(m.state['domains'][0]['status'],'awaiting_leo_review')
            self.assertEqual(m.state['domains'][0]['leo_review']['status'],'pending')
