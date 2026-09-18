import tempfile,unittest,json,sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workbench import Monitor
from unittest.mock import patch
import time

class InlineThread:
    def __init__(self,target,**kwargs):self.target=target
    def start(self):self.target()

class WorkbenchTests(unittest.TestCase):
    def test_connect_immediately_reads_and_clears_stale_error(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','keyword':'词','status':'waiting_purchase'}]}))
            m=Monitor(path);m.state['monitor'].update(status='blocked',last_error='stale error')
            class FakeConnector:
                def connect(self):pass
                def read(self):return {'pending':[{'domain':'example.com','owner':'Pony'}],'launch':[]}
            m.connector=FakeConnector()
            with patch('workbench.threading.Thread',InlineThread):m.control('connect')
            self.assertEqual(m.state['monitor']['connection_state'],'connected');self.assertIsNone(m.state['monitor']['last_error'])
            self.assertEqual(m.state['monitor']['status'],'waiting')
    def test_login_pending_gets_short_bounded_retry(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'state.json';path.write_text(json.dumps({'batch_id':'test','business_date':datetime.now().date().isoformat(),'expected_count':1,'domains':[{'domain':'example.com','status':'waiting_purchase'}]}))
            m=Monitor(path)
            class FakeConnector:
                def connect(self):pass
                def read(self):raise RuntimeError('请先在程序专用浏览器完成 Google 登录')
            m.connector=FakeConnector()
            with patch('workbench.threading.Thread',InlineThread):m.control('connect')
            self.assertEqual(m.state['monitor']['connection_state'],'login_required')
            self.assertLess(m.state['monitor']['next_check_at']-time.time(),16)
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
            self.assertEqual(monitor.state['monitor']['status'],'awaiting_leo_review');self.assertFalse(monitor.status()['completion']['completed'])

if __name__=='__main__':unittest.main()
