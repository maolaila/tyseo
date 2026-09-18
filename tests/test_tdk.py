import unittest,sys,copy,json,tempfile
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tdk import generate_tdk,prepare_drafts,require_leo_approval,backend_script
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
        entries=prepare_drafts(domains,{'pending':[],'launch':[row]});self.assertEqual(len(entries),1)
        row['cells'][5]='Human edit'
        before=copy.deepcopy(row)
        self.assertEqual(prepare_drafts(domains,{'pending':[],'launch':[row]})[0]['tdk'],entries[0]['tdk'])
        self.assertEqual(row,before)
    def test_leo_gate_binds_revision(self):
        item={'tdk':generate_tdk('球帝直播')}
        with self.assertRaises(ValueError):require_leo_approval(item)
        item['leo_review']={'reviewer':'Leo','status':'approved','evidence':'message','revision':item['tdk']['revision']}
        require_leo_approval(item);item['tdk']['revision']='changed'
        with self.assertRaises(ValueError):require_leo_approval(item)
    def test_admin_entry_is_independent_of_assigned_server(self):
        draft=generate_tdk('球帝直播');item={'domain':'example.com','keyword':'球帝直播','tdk':draft,'leo_review':{'reviewer':'Leo','status':'approved','revision':draft['revision'],'evidence':'user_report'}}
        cells=['']*17;cells[4:8]=[draft[k] for k in ('template','title','description','keywords')];cells[12]='s213017'
        cells[16]='$'.join(['example.com','球帝直播',draft['title'],draft['description'],draft['keywords'],'r62',*(['']*8)])
        row={'domain':'example.com','owner':'Pony','cells':cells}
        self.assertEqual(backend_script([item],{'launch':[row]}),cells[16])
        cells[12]=''
        with self.assertRaisesRegex(ValueError,'服务器缺失'):backend_script([item],{'launch':[row]})
    def test_scan_prepares_but_never_writes(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','keyword':'球帝直播','status':'waiting_purchase'}]}))
            class Connector:
                def read(self):return {'pending':[],'launch':[{'domain':'example.com','owner':'Pony','keyword':'球帝直播','row':3,'cells':['']*17}]}
                def write_tdk(self,updates):raise AssertionError('Scheduled scans must not write')
            m=Monitor(path);m.connector=Connector();m.scan()
            self.assertEqual(m.state['domains'][0]['status'],'awaiting_leo_review')
            self.assertEqual(m.state['monitor']['status'],'awaiting_leo_review')
    def test_removed_write_action_and_approval_survive_scan(self):
        with tempfile.TemporaryDirectory() as d:
            draft=generate_tdk('球帝直播')
            item={'domain':'example.com','keyword':'球帝直播','status':'approved_for_prefill','tdk':draft,'leo_review':{'status':'approved','reviewer':'Leo','revision':draft['revision'],'evidence':'user_report'}}
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[item]}))
            class Connector:
                def read(self):return {'pending':[],'launch':[{'domain':'example.com','owner':'Pony','keyword':'球帝直播','row':3,'cells':['']*17}]}
            m=Monitor(path);m.connector=Connector();m.scan()
            self.assertEqual(m.state['domains'][0]['status'],'approved_for_prefill')
            self.assertFalse(m.state['tdk_review_required'])
            with self.assertRaises(ValueError):m.control('fill_sheet',m.draft_revision())
            from launch_connector import SheetConnector
            self.assertFalse(hasattr(SheetConnector,'write_tdk'))
    def test_local_script_does_not_require_writing_reference_tdk(self):
        draft=generate_tdk('球帝直播');item={'domain':'example.com','keyword':'球帝直播','tdk':draft,'leo_review':{'status':'approved','reviewer':'Leo','revision':draft['revision'],'evidence':'user_report'}}
        cells=['']*17;cells[12]='s213017';cells[16]='$'.join(['example.com','球帝直播','old title','old desc','old keywords','old template',*(['config']*8)])
        snapshot={'pending':[],'launch':[{'domain':'example.com','owner':'Pony','cells':cells}]};before=copy.deepcopy(snapshot)
        result=backend_script([item],snapshot).split('$')
        self.assertEqual(result[2:6],[draft[k] for k in ('title','description','keywords','template')]);self.assertEqual(snapshot,before)
        self.assertEqual(result[6:],['config']*8)
        item['tdk']['title']='changed without revision update'
        with self.assertRaisesRegex(ValueError,'changed'):backend_script([item],snapshot)
