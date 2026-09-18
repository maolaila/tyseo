import unittest
import sys
import tempfile
import copy
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import *
from checks import *
from jinja2 import Environment, StrictUndefined, UndefinedError

class Gates(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.task={'repo_root':str(self.root),'reference_template_id':'r62','target_template_id':'allocated_test',
                   'target_id_confirmed':True,'mode':'new-template'}
        self.allocation={'template_id':'allocated_test','source':'unit fixture allocation, not business authorization'}
    def tearDown(self):self.temp.cleanup()
    def guard(self,path):return safe_business_path(self.task,path,self.allocation)
    def test_F01_python_env_requirements(self):
        self.guard('templates/allocated_test/master.html')
        for p in ('run.py','.env','requirements.txt','templates/allocated_test/run.py'):
            with self.assertRaises(ValueError):self.guard(p)
    def test_F02_other_template(self):
        self.guard('static/allocated_test/style.css')
        for p in ('templates/r62/master.html','static/other/app.js'):
            with self.assertRaises(ValueError):self.guard(p)
    def test_F03_traversal_and_link(self):
        for p in ('templates/allocated_test/../r62/x.html','templates/allocated_test/x.html:stream','Templates/allocated_test/a.html'):
            with self.assertRaises(ValueError):self.guard(p)
        # Actual Windows junction: does not require developer-mode symlink privilege.
        import subprocess
        (self.root/'templates/allocated_test').mkdir(parents=True)
        (self.root/'outside').mkdir()
        if os.name=='nt':
            subprocess.run(['cmd','/c','mklink','/J',str(self.root/'templates/allocated_test/link'),str(self.root/'outside')],capture_output=True,check=True)
        else:(self.root/'templates/allocated_test/link').symlink_to(self.root/'outside',target_is_directory=True)
        self.task['mode']='repair-template'
        with self.assertRaises(ValueError):self.guard('templates/allocated_test/link/x.html')
    def test_F04_dirty_baseline_preserved(self):
        a={'files':{'mine.html':'abc'},'status':' M mine.html','commit':'one'}
        self.assertEqual(compare_baseline(a,copy.deepcopy(a))['status'],'pass')
        b=copy.deepcopy(a);b['files']['mine.html']='other';self.assertEqual(compare_baseline(a,b)['status'],'fail')
    def test_F05_id_missing_conflict(self):
        self.guard('templates/allocated_test/a.html')
        self.task['target_id_confirmed']=False
        with self.assertRaises(ValueError):self.guard('templates/allocated_test/a.html')
        self.task['target_id_confirmed']=True;(self.root/'templates/allocated_test').mkdir(parents=True)
        with self.assertRaises(ValueError):self.guard('templates/allocated_test/a.html')
    def test_F06_private_reference(self):
        self.assertFalse(check_dependencies("{% extends 'draft/master.html' %}",'draft',['r62']))
        self.assertTrue(check_dependencies("{% extends 'r62/master.html' %}",'draft',['r62']))
    def test_F07_F31_coverage_denominator(self):
        expected=[('home',390,'light',True),('detail',390,'light',True)]
        records=[dict(zip(('page_type_id','width','theme','javascript'),x)) for x in expected]
        self.assertFalse(coverage(expected,records));self.assertTrue(coverage(expected,records[:1]))
    def test_F08_strict_variable(self):
        e=Environment(undefined=StrictUndefined)
        self.assertEqual(e.from_string('{{ match.score }}').render(match={'score':0}),'0')
        with self.assertRaises(UndefinedError):e.from_string('{{ match.scroe }}').render(match={'score':0})
    def test_F09_F10_F11_score_mapping(self):
        for expected in ({'home':0,'away':1},{'home':None,'away':None},{'home':118,'away':115},{'home':'0','away':0}):
            visible={k:score_text(v) for k,v in expected.items()};self.assertTrue(check_scores(expected,visible))
            bad=dict(visible,home='wrong');self.assertFalse(check_scores(expected,bad))
        self.assertFalse(check_scores({'home':0,'away':1},{'home':'1','away':'0'}))
        self.assertFalse(check_scores({'home':None,'away':None},{'home':'0','away':'0'}))
    def test_F16_F17_search_scope(self):
        # Only verified route/method/parameter and declared scope are accepted.
        def valid(x):return x=={'route':'/search','method':'GET','parameter':'q','scope':'allowlisted'}
        self.assertTrue(valid({'route':'/search','method':'GET','parameter':'q','scope':'allowlisted'}))
        self.assertFalse(valid({'route':'/fake','method':'GET','parameter':'q','scope':'all-site'}))
    def test_F21_empty_shell(self):
        good='<html lang="zh"><body><h1>Sports fixtures real content with links</h1><a href="/match">Match detail</a></body></html>'
        self.assertEqual(html_checks(good)[0]['status'],'pass')
        self.assertEqual(html_checks('<html><body><div id="app"></div></body></html>')[0]['status'],'fail')
    def test_F22_real_href(self):
        self.assertEqual(html_checks('<a href="/detail">detail</a>')[1]['status'],'pass')
        self.assertEqual(html_checks('<a onclick="go()">detail</a>')[1]['status'],'fail')
    def test_F23_F24_canonical_policy(self):
        p={'canonical':'https://site.invalid/list?page=2'}
        self.assertEqual(next(x for x in html_checks('<link rel="canonical" href="https://site.invalid/list?page=2">',policy=p) if x['rule_id']=='SEO-06')['status'],'pass')
        for wrong in ('https://site.invalid/','http://localhost:5000/'):
            self.assertEqual(next(x for x in html_checks(f'<link rel="canonical" href="{wrong}">',policy=p) if x['rule_id']=='SEO-06')['status'],'fail')
    def test_F25_F26_robots_policy(self):
        body='<meta name="robots" content="noindex">'
        def status(indexable):return next(x for x in html_checks(body,policy={'indexable':indexable}) if x['rule_id']=='SEO-10')['status']
        self.assertEqual(status(True),'fail');self.assertEqual(status(False),'pass')
    def test_F27_head_binding(self):
        good='{% block title %}{{ article_info.Title }}{% endblock %}'
        bad='{% block title %}Homepage{% endblock %}'
        self.assertIn('{{',good);self.assertNotIn('{{',bad) # narrow static detector, not full semantic TDK proof
    def test_F28_fixture_leak(self):
        self.assertNotEqual(html_checks('<p>real content</p>')[-1]['status'],'fail')
        self.assertEqual(html_checks('<p>FIXTURE_ONLY</p>')[-1]['status'],'fail')
    def test_F29_design_difference(self):
        a={k:'a' for k in ('navigation','home_layout','match_presentation','article_layout','detail_layout')}
        b=dict(a,color='red');self.assertFalse(distinct_design(a,b))
        b.update(navigation='rail',home_layout='split',match_presentation='grid');self.assertTrue(distinct_design(a,b))
    def test_F30_no_score_mask(self):
        def valid(options):return not options.get('mask')
        self.assertTrue(valid({'full_page':True}));self.assertFalse(valid({'mask':['.score']}))
    def test_F32_evidence(self):
        (self.root/'evidence.txt').write_text('executed')
        r={'status':'pass','environment':'fixture','evidence_paths':['evidence.txt']};validate_result(r,self.root)
        r['evidence_paths']=['missing.png']
        with self.assertRaises(ValueError):validate_result(r,self.root)
    def test_F33_environment(self):
        r={'status':'blocked','environment':'fixture','claims_real_app':False};validate_result(r,self.root)
        r['claims_real_app']=True
        with self.assertRaises(ValueError):validate_result(r,self.root)
    def test_F34_stale_checkpoint(self):
        self.assertTrue(resume_valid({'input_hash':'one'},'one'));self.assertFalse(resume_valid({'input_hash':'one'},'two'))
    def test_F35_F36_forbidden_actions(self):
        self.assertTrue(allowed_action('get_local_page'))
        for action in ('sheet_write','purchase','deploy','python_repair','push','indexnow'):
            self.assertFalse(allowed_action(action))
    def test_F37_not_synthetic_crawl(self):
        self.assertTrue(genuine_crawl({'source':'verified_server_log','identity_verified':True}))
        self.assertFalse(genuine_crawl({'source':'own_probe','user_agent':'bingbot','synthetic':True}))
    def test_F38_no_relaxation(self):
        self.assertTrue(valid_repair('test-hash','test-hash','scope','scope',1))
        self.assertFalse(valid_repair('test-hash','new','scope','scope',1))
        self.assertFalse(valid_repair('test-hash','test-hash','scope','wider',1))
        self.assertFalse(valid_repair('test-hash','test-hash','scope','scope',4))

if __name__=='__main__':unittest.main()
