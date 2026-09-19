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
            self.assertEqual(sum(c['engine']=='chromium' and c['width'] in self.task['browser_matrix']['widths'] and c['stress']=='normal' for c in cases),14)
            self.assertEqual(sum(not c['javascript'] for c in cases),4)
            self.assertTrue(any(c['width']==320 for c in cases))
        self.assertEqual(len(self.plan['reviews']),8)
    def test_assignment_is_not_fixed_to_z(self):
        task={**self.task,'target_template_id':'x66','mode':'repair-template'}
        contract={'pages':[{'page_type_id':'index','sample_urls':['/'],'template_exists':True},
                           {'page_type_id':'missing','sample_urls':[],'template_exists':False},
                           {'page_type_id':'no_data','sample_urls':[],'template_exists':True}]}
        plan=make_plan(task,contract,'new')
        self.assertEqual(plan['template_id'],'x66')
        self.assertEqual([p['page_type_id'] for p in plan['excluded_pages']],['missing'])
        self.assertTrue(any(c['page_type_id']=='no_data' and c['status']=='blocked' for c in plan['cases']))
        self.assertEqual(len({c['case_id'] for c in plan['cases']}),len(plan['cases']))
    def test_daily_policy_excludes_artificial_enlargement_but_keeps_responsive_pressure(self):
        self.assertFalse(any(c['stress'] in ('text_resize_200','wcag_text_spacing') or c['text_scale']!=1 for c in self.plan['cases']))
        self.assertNotIn('text_resize_spacing',self.plan['required_checks'])
        self.assertTrue(any(c['stress']=='landscape' for c in self.plan['cases']))
        self.assertTrue(any(c['width']==899 for c in self.plan['cases']))
    def test_tool_evidence_can_resolve_without_ai_but_missing_check_cannot(self):
        plan=copy.deepcopy(self.plan);record=self.record()
        plan['cases']=[plan['cases'][0]];plan['page_requirements']=[]
        plan['reviews']=[{'page_type_id':record['page_type_id'],'width':record['width'],'theme':record['theme']}]
        record['checks']={name:{'status':'pass','method':'tool','verifier':'fixture-verifier',
            'evidence':[record['artifacts']['dom']]} for name in plan['required_checks']}
        self.assertTrue(assess(plan,[record],self.root,'v1')['ready_for_human_review'])
        del record['checks']['seo_contract']
        result=assess(plan,[record],self.root,'v1')
        self.assertFalse(result['ready_for_human_review'])
        self.assertFalse(result['ai_review_queue'])
        self.assertTrue(result['tool_work_pending'])
        record['review_triggers']=['SEO semantic contract cannot be determined by the current tool']
        self.assertTrue(assess(plan,[record],self.root,'v1')['ai_review_queue'])
        record['checks']['seo_contract']=dict(record['checks']['layout_geometry'])
        plan['required_checks']=[]
        self.assertTrue(assess(plan,[record],self.root,'v1')['policy_mismatch'])
    def test_fixture_states_separate(self):
        self.assertIn('filter_results',self.plan['required_checks'])
        self.assertIn('layout_integrity',self.plan['required_checks'])
        c=copy.deepcopy(self.contract);c['pages'][0]['score_contract']={'selectors':['.score']}
        p=make_plan(self.task,c,'v1')
        fixture=[x for x in p['cases'] if x['environment']=='fixture']
        self.assertEqual(len(fixture),18*4)
        self.assertTrue(any(x['data_state']=='undefined' for x in fixture))
    def test_functional_and_layout_gate_reject_missing_or_failed_evidence(self):
        plan=copy.deepcopy(self.plan);record=self.record()
        plan['cases']=[plan['cases'][0]];plan['page_requirements']=[];plan['reviews']=[]
        record['checks']={name:{'status':'pass','method':'tool','verifier':'regression',
            'evidence':[record['artifacts']['dom']]} for name in plan['required_checks']}
        self.assertTrue(assess(plan,[record],self.root,'v1')['ready_for_human_review'])
        for key in ('filter_results','layout_integrity','link_navigation','action_effect'):
            original=record['checks'].pop(key)
            self.assertFalse(assess(plan,[record],self.root,'v1')['ready_for_human_review'])
            record['checks'][key]={**original,'status':'fail'}
            self.assertFalse(assess(plan,[record],self.root,'v1')['ready_for_human_review'])
            record['checks'][key]=original
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
