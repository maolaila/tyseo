import unittest
import tempfile
import sys
import copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import digest
from acceptance import make_plan,assess,html_summary,result_record
from checks import tdk_variation

class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.task={'reference_template_id':'z5','target_template_id':None,'browser_matrix':{'widths':[360,390,768,1280,1920],'themes':['light','dark'],'no_js_widths':[390,1280],'secondary_engines':['webkit','firefox']}}
        self.contract={'pages':[{'page_type_id':'index','sample_urls':['/']},{'page_type_id':'detail','sample_urls':[]}]}
        self.plan=make_plan(self.task,self.contract,'v1')
    def tearDown(self):self.tmp.cleanup()
    def record(self):
        case=self.plan['cases'][0];artifacts={}
        for kind in ('http','dom','screenshot'):
            p=self.root/(kind+'.txt');p.write_text(kind)
            artifacts[kind]={'path':p.name,'sha256':digest(p),'kind':'http_response' if kind=='http' else kind}
        return dict(case,status='pass',input_hash='v1',artifacts=artifacts,theme_verified=True)
    def test_full_matrix_and_nojs_not_dropped(self):
        for page in ('index','detail'):
            cases=[c for c in self.plan['cases'] if c['page_type_id']==page]
            self.assertEqual(sum(c['engine']=='chromium' and c['width'] in self.task['browser_matrix']['widths'] and c['text_scale']==1 for c in cases),12)
            self.assertEqual(sum(not c['javascript'] for c in cases),2)
            self.assertTrue(any(c['width']==320 for c in cases))
        self.assertEqual(len(self.plan['reviews']),8)
    def test_fixture_states_separate(self):
        c=copy.deepcopy(self.contract);c['pages'][0]['score_contract']={'selectors':['.score']}
        p=make_plan(self.task,c,'v1')
        fixture=[x for x in p['cases'] if x['environment']=='fixture']
        self.assertEqual(len(fixture),18*4)
        self.assertTrue(any(x['data_state']=='undefined' for x in fixture))
    def test_missing_cases_and_reviews_block_delivery(self):
        result=assess(self.plan,[self.record()],self.root,'v1')
        self.assertEqual(result['valid'],1);self.assertFalse(result['ready_for_human_review']);self.assertGreater(result['missing'],0)
    def test_changed_artifact_rejects_pass(self):
        r=self.record();(self.root/'dom.txt').write_text('changed')
        self.assertEqual(assess(self.plan,[r],self.root,'v1')['valid'],0)
    def test_wrong_provenance_rejected(self):
        r=self.record();r['artifacts']['http']['kind']='rendered_dom'
        self.assertIn('DOM',assess(self.plan,[r],self.root,'v1')['invalid'][0]['reason'])
    def test_stale_input_rejected(self):
        self.assertEqual(assess(self.plan,[self.record()],self.root,'v2')['valid'],0)
        self.assertTrue(assess(self.plan,[],self.root,'v2')['plan_stale'])
    def test_fixture_not_real(self):
        r=self.record();r['environment']='fixture';self.assertEqual(assess(self.plan,[r],self.root,'v1')['valid'],0)
    def test_theme_emulation_not_verification(self):
        r=self.record();r['theme_verified']=False;self.assertEqual(assess(self.plan,[r],self.root,'v1')['valid'],0)
    def test_meta_and_header_separate(self):
        h=html_summary('<html><head><meta name="robots" content="index"></head></html>',{'x-robots-tag':'noindex'})
        self.assertEqual(h['robots_meta'],'index');self.assertEqual(h['x_robots_tag'],'noindex')
    def test_failure_schema_has_context(self):
        f=result_record(self.plan['cases'][0],'UI-01','fail','fits','overflow',['a.png'],selector='.score')
        for key in ('rule_id','page_type_id','width','theme','data_state','expected','actual','severity','owner_layer','evidence_paths','selector'):self.assertIn(key,f)
    def test_tdk_multiple_configurations_and_homepage_leak(self):
        samples=[]
        for page in ('index','detail'):
            for site in ('fixture-a','fixture-b'):
                expected={k:page+site+k for k in ('title','description','keywords')}
                samples.append({'page_type_id':page,'site_config_id':site,'expected':expected,'actual':dict(expected),'source_evidence':'synthetic known-input fixture'})
        self.assertEqual(tdk_variation(samples)['status'],'pass')
        samples[-1]['actual']['title']=samples[0]['actual']['title']
        self.assertEqual(tdk_variation(samples)['status'],'fail')
        self.assertEqual(tdk_variation(samples[:1])['status'],'blocked')

if __name__=='__main__':unittest.main()
