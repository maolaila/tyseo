"""Synthetic detector checks: failures, legal containment and scroll exceptions."""
import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from core import ROOT
from browser_checks import compact_review_queue

class LayoutAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch()
        cls.script=(ROOT/'scripts/layout-audit.js').read_text(encoding='utf-8')
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.pw.stop()
    def setUp(self):self.page=self.browser.new_page(viewport={'width':390,'height':844})
    def tearDown(self):self.page.close()
    def findings(self,html,contract=None):
        self.page.set_content('<html><style>body{margin:0}button{width:60px;height:44px}</style><body>'+html+'</body></html>')
        return self.page.evaluate(self.script,contract or {})['findings']
    def test_non_text_clip_is_detected_even_when_page_does_not_overflow(self):
        for tag in ('svg','canvas','img','table'):
            with self.subTest(tag=tag):
                contents='<tr><td>data</td></tr>' if tag=='table' else ''
                findings=self.findings(f'<div style="width:80px;height:80px;overflow:hidden"><{tag} id="subject" style="width:180px;height:60px">{contents}</{tag}></div>',
                    {'components':[{'selector':'#subject','critical':True}]})
                self.assertTrue(any(f['rule_id']=='LAYOUT-COMPONENT-CLIP' and f['status']=='fail' for f in findings))
                self.assertFalse(any(f['rule_id']=='LAYOUT-PAGE-OVERFLOW' for f in findings))
    def test_forbidden_overlap_but_not_parent_child(self):
        findings=self.findings('<button id="a">A<svg id="icon" width="8" height="8"></svg></button><button id="b" style="position:absolute;left:20px;top:0">B</button>',
            {'forbidden_overlap_pairs':[['#a','#b'],['#a','#icon']]})
        failures=[f for f in findings if f['rule_id']=='LAYOUT-FORBIDDEN-OVERLAP']
        self.assertEqual(len(failures),1)
        self.assertEqual(failures[0]['other_selector'],'#b')
    def test_legal_local_scroll_does_not_fail_clipping(self):
        findings=self.findings('<div style="width:100px;overflow:auto"><table style="width:300px"><tr><td>data</td></tr></table></div>')
        self.assertFalse(any(f['status']=='fail' for f in findings))
    def test_overlay_intercepts_hit_and_small_critical_target(self):
        findings=self.findings('<button id="a" style="width:20px;height:20px">A</button><div id="overlay" style="position:fixed;inset:0;background:white"></div>',
            {'components':[{'selector':'#a','critical':True}]})
        rules={f['rule_id'] for f in findings if f['status']=='fail'}
        self.assertIn('LAYOUT-TARGET-SIZE',rules);self.assertIn('LAYOUT-CONTROL-OCCLUDED',rules)
    def test_missing_contract_selector_is_blocked_not_pass(self):
        findings=self.findings('<p>content</p>',{'components':[{'selector':'#missing','required':True}]})
        self.assertTrue(any(f['status']=='blocked' for f in findings))
    def test_cls_sessions_and_recent_input_exclusion(self):
        self.page.set_content('<body>fixture</body>')
        self.page.evaluate("""() => {window.PerformanceObserver=class {static supportedEntryTypes=['layout-shift'];constructor(cb){window.feedShift=entries=>cb({getEntries:()=>entries})}observe(){}};}""")
        self.page.evaluate((ROOT/'scripts/layout-shift-init.js').read_text(encoding='utf-8'))
        value=self.page.evaluate("""() => {feedShift([{startTime:100,value:.03,hadRecentInput:false},{startTime:200,value:.04,hadRecentInput:false},{startTime:250,value:.8,hadRecentInput:true},{startTime:2000,value:.05,hadRecentInput:false}]);return __layoutShiftAudit.value;}""")
        self.assertAlmostEqual(value,.07)
    def test_compact_queue_retains_counts_and_full_evidence_reference(self):
        findings=[{'rule_id':'clip','status':'needs_review','selector':f'#n{i}'} for i in range(50)]
        findings.append({'rule_id':'overflow','status':'fail'})
        queue=compact_review_queue(findings,'screenshots/full.json')
        self.assertEqual(queue,[{'rule_id':'clip','status':'needs_review','occurrences':50,'evidence_paths':['screenshots/full.json']}])

if __name__=='__main__':unittest.main()
