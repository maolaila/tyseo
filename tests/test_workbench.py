import tempfile,unittest,json,sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench import Monitor

class WorkbenchTests(unittest.TestCase):
    def test_program_tick_and_pause_persistence(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','keyword':'词','status':'waiting_purchase'}]}))
            monitor=Monitor(path,1800)
            class FakeConnector:
                def read(self):return {'pending':[{'domain':'example.com','owner':'Pony'}],'launch':[]}
            monitor.connector=FakeConnector();monitor.scan()
            self.assertEqual(monitor.state['monitor']['status'],'waiting');self.assertEqual(monitor.state['domains'][0]['observed'],'waiting_purchase')
            self.assertTrue(monitor.state['monitor']['last_success_at']);monitor.control('pause')
            resumed=Monitor(path,1800);self.assertFalse(resumed.state['monitor']['enabled'])
    def test_purchase_is_not_completion(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','keyword':'词','status':'waiting_purchase'}]}))
            monitor=Monitor(path,1800)
            class FakeConnector:
                def read(self):return {'pending':[],'launch':[{'domain':'example.com','owner':'Pony','row':3,'keyword':'词','cells':['']*17}]}
            monitor.connector=FakeConnector();monitor.scan()
            self.assertEqual(monitor.state['monitor']['status'],'action_required');self.assertFalse(monitor.status()['completion']['completed'])

if __name__=='__main__':unittest.main()
