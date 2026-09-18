import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tdk import generate_tdk
from workbench import Workbench

def draft(keyword):
    date=datetime.now().date().isoformat()
    return generate_tdk(keyword,title=keyword+'今日赛事赛程',
        description=keyword+'整理足球篮球赛事和比分入口。',
        keywords=keyword+',足球赛事,篮球赛事',
        assignment={'owner':'Pony','group':'2组','business_date':date,
                    'sheet':'bing体育品牌词','workbook_url':'https://docs.google.com/spreadsheets/d/1-3DvtAhJQu83G9fA1TWrEZIKiosOzvwDWYknEFXKGJ0/edit?gid=0'},
        competitors=[{'url':'https://example.org/sports','checked_on':date,'title':'另一赛事站'}],
        batch_id='fixture-batch',business_date=date)

class WorkbenchTests(unittest.TestCase):
    def state_path(self,root,with_draft):
        path=Path(root)/'state.json'
        item={'domain':'example.com','keyword':'球帝直播','status':'awaiting_ai_tdk'}
        if with_draft:item['tdk']=draft('球帝直播')
        path.write_text(json.dumps({'batch_id':'fixture-batch','business_date':datetime.now().date().isoformat(),
                                    'expected_count':1,'domains':[item]},ensure_ascii=False),encoding='utf-8')
        return path

    def test_no_polling_and_missing_draft_is_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            workbench=Workbench(self.state_path(folder,False))
            status=workbench.status()
            self.assertFalse(status['ready'])
            self.assertFalse(status['program']['background_monitor'])
            self.assertFalse(hasattr(workbench,'loop'))
            with self.assertRaises(ValueError):workbench.write_tdk(status['revision'])

    def test_manual_action_only_writes_target_tdk_and_confirms(self):
        with tempfile.TemporaryDirectory() as folder:
            workbench=Workbench(self.state_path(folder,True))
            cells=['']*17;cells[1]='Pony';cells[2]='example.com';cells[3]='球帝直播'
            before={'pending':[],'launch':[{'domain':'example.com','owner':'Pony',
                    'keyword':'球帝直播','row':3,'cells':cells}]}
            calls=[]
            class Connector:
                def ensure_browser(self):calls.append('browser')
                def read(self):calls.append('read');return copy.deepcopy(before)
                def write_tdk(self,updates,fresh=None):
                    calls.append('write');after=copy.deepcopy(fresh)
                    for update in updates:after['launch'][0]['cells'][4:8]=update['values']
                    return after
            workbench.connector=Connector()
            with patch('workbench.record_tdk_history') as history:
                result=workbench.write_tdk(workbench.revision())
            self.assertEqual(calls,['browser','read','write'])
            self.assertEqual(result['domains_verified'],1)
            self.assertEqual(result['rows_written'],[3])
            self.assertEqual(workbench.state['domains'][0]['status'],'sheet_filled')
            history.assert_called_once()
            self.assertTrue(workbench.status()['done'])
            self.assertFalse(workbench.status()['ready'])

if __name__=='__main__':unittest.main()
