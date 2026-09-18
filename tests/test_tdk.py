import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from tdk import generate_tdk,prepare_drafts,require_current_review,plan_sheet_write,ensure_unique_tdks,record_tdk_history,prior_tdks

def draft(keyword='球帝直播',batch='batch-one',group='2组'):
    date=datetime.now().date().isoformat()
    return generate_tdk(keyword,title=keyword+'赛事赛程与比分',
        description=keyword+'提供足球与篮球比赛赛程、比分及录像入口。',
        keywords=keyword+',足球直播,篮球直播',
        assignment={'owner':'Pony','group':group,'business_date':date,
                    'sheet':'bing体育品牌词','workbook_url':'https://docs.google.com/spreadsheets/d/1-3DvtAhJQu83G9fA1TWrEZIKiosOzvwDWYknEFXKGJ0/edit?gid=0'},
        competitors=[{'url':'https://example.org/rival','checked_on':date,'title':'另一体育站'}],
        batch_id=batch,business_date=date)

class TdkTests(unittest.TestCase):
    def test_no_fixed_copy_or_old_group_fallback(self):
        with self.assertRaises(ValueError):generate_tdk('球帝直播')
        item=draft();self.assertEqual(item['review_status'],'not_required')
        require_current_review({'tdk':item}) # Ordinary batches do not require Leo.
        args={k:item[k] for k in ('title','description','keywords','assignment','competitors','batch_id','business_date')}
        args['assignment']={**item['assignment'],'group':''}
        with self.assertRaisesRegex(ValueError,'Pony 关键词分组'):generate_tdk('球帝直播',**args)
        args['assignment']=item['assignment'];args['competitors']=[]
        with self.assertRaisesRegex(ValueError,'竞争网站'):generate_tdk('球帝直播',**args)
        args['competitors']=[{'url':'https://example.org','checked_on':item['business_date'],'title':item['title']}]
        with self.assertRaisesRegex(ValueError,'直接复制'):generate_tdk('球帝直播',**args)

    def test_each_field_rejects_previous_launch_copy(self):
        old={'domain':'old.example.com','tdk':draft(batch='old')}
        new={'domain':'new.example.com','tdk':draft(batch='new')}
        with self.assertRaisesRegex(ValueError,'title.*重复'):ensure_unique_tdks([new],[old])
        changed=copy.deepcopy(new)
        changed['tdk']['title']='球帝直播赛事赛程与比分！'
        with self.assertRaisesRegex(ValueError,'title.*重复'):ensure_unique_tdks([changed],[old])
        changed['tdk']['title']='球帝直播另一种赛事入口'
        with self.assertRaisesRegex(ValueError,'description.*重复'):ensure_unique_tdks([changed],[old])
        changed['tdk']['description']='球帝直播当天比赛列表'
        with self.assertRaisesRegex(ValueError,'keywords.*重复'):ensure_unique_tdks([changed],[old])
        hashes={field:hashlib.sha256(''.join(c.lower() for c in old['tdk'][field] if c.isalnum()).encode()).hexdigest()
                for field in ('title','description','keywords')}
        with self.assertRaisesRegex(ValueError,'title.*重复'):
            ensure_unique_tdks([new],[{'domain':'old.example.com','field_hashes':hashes}])

    def test_review_only_when_requested_and_revision_covers_assignment(self):
        item={'tdk':draft()}
        require_current_review(item)
        item['leo_review_required']=True
        with self.assertRaisesRegex(ValueError,'Leo review'):require_current_review(item)
        item['leo_review']={'status':'approved','reviewer':'Leo','revision':item['tdk']['revision'],'evidence':'message'}
        require_current_review(item)
        item['tdk']['assignment']['group']='3组'
        with self.assertRaisesRegex(ValueError,'版本已变化'):require_current_review(item)

    def test_new_domain_waits_for_ai_and_writer_scopes_existing_rows(self):
        row={'domain':'example.com','owner':'Pony','keyword':'球帝直播','row':3539,'cells':['']*17}
        item={'domain':'example.com','keyword':'球帝直播','status':'waiting_purchase'}
        snapshot={'pending':[],'launch':[row]}
        self.assertIsNone(prepare_drafts([item],snapshot)[0]['tdk'])
        item['tdk']=draft()
        planned=plan_sheet_write([item],snapshot)
        self.assertEqual(planned[0]['row'],3539)
        self.assertEqual(planned[0]['values'][0],'r62')
        row['cells'][5]='Another author'
        with self.assertRaisesRegex(ValueError,'已有不同'):plan_sheet_write([item],snapshot)
        row['cells'][4:8]=planned[0]['values']
        self.assertEqual(plan_sheet_write([item],snapshot),[])
        row['owner']='Other'
        with self.assertRaisesRegex(ValueError,'归属'):plan_sheet_write([item],snapshot)

    def test_history_fingerprints_survive_a_new_batch(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            states=root/'runs/site-launch'
            current=states/'next-batch/state.json'
            current.parent.mkdir(parents=True)
            current.write_text(json.dumps({'batch_id':'next-batch','domains':[]}),encoding='utf-8')
            previous={'domain':'old.example.com','tdk':draft(batch='past-batch')}
            next_draft=draft(batch='next-batch')
            with patch('tdk.ROOT',root):
                record_tdk_history([previous],'past-batch')
                record_tdk_history([previous],'past-batch')
                saved=json.loads((root/'data/tdk-fingerprints.json').read_text(encoding='utf-8'))
                self.assertEqual(len(saved['entries']),1)
                self.assertNotIn('球帝直播',json.dumps(saved,ensure_ascii=False))
                with self.assertRaisesRegex(ValueError,'重复'):
                    ensure_unique_tdks([{'domain':'next.example.com','tdk':next_draft}],
                                       prior_tdks(current))

if __name__=='__main__':unittest.main()
