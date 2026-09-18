"""Browser detector positive/negative samples, not real business acceptance."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from generate import BASE_CSS, UI_JS
from playwright.sync_api import sync_playwright

class BrowserFailures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw=sync_playwright().start();cls.browser=cls.pw.chromium.launch()
    @classmethod
    def tearDownClass(cls):cls.browser.close();cls.pw.stop()
    def setUp(self):
        self.context=self.browser.new_context(viewport={'width':390,'height':844})
        self.page=self.context.new_page()
    def tearDown(self):self.context.close()
    def content(self,extra='',style=''):
        self.page.set_content('<html lang="zh"><style>'+BASE_CSS+style+'</style><body id="top"><h1>FIXTURE_ONLY</h1>'+extra+'</body></html>')
    def test_F12_long_names_and_score_clipping(self):
        row='<div class="wf-match"><div class="wf-team">超长中文球队名称以及 English Long Team Name</div><span class="score">118:115</span><div class="wf-team">客队 Long Team Name</div></div>'
        def fits():return self.page.locator('.score').evaluate('(e)=>{let r=e.getBoundingClientRect();return r.x>=0&&r.right<=innerWidth}')
        self.content(row);self.assertTrue(fits())
        self.content(row,'.wf-match{width:1800px}');self.assertFalse(fits())
    def test_F13_failed_image_layout(self):
        self.content('<img id="logo" width="32" height="32" src="http://invalid.local/missing.png">')
        self.assertEqual(self.page.locator('#logo').bounding_box()['height'],32)
        self.content('<img id="logo" style="width:0;height:0" src="http://invalid.local/missing.png">')
        self.assertEqual(self.page.locator('#logo').bounding_box()['height'],0)
    def test_F14_dark_text_visibility_detector(self):
        def contrast_visible():return self.page.locator('body').evaluate('(e)=>getComputedStyle(e).color!==getComputedStyle(e).backgroundColor')
        self.content('<input placeholder="search">');self.assertTrue(contrast_visible())
        self.content('', 'body{color:#111;background:#111}');self.assertFalse(contrast_visible())
        # Detects invisible text only, not a complete WCAG contrast implementation.
    def test_F15_storage_failure(self):
        self.content('<button data-theme-toggle>theme</button>')
        self.page.evaluate("Object.defineProperty(window,'localStorage',{get(){throw new Error('unavailable')}})")
        errors=[];self.page.on('pageerror',lambda e:errors.append(str(e)))
        self.page.add_script_tag(content=UI_JS);self.page.locator('button').click()
        self.assertEqual(self.page.locator('html').get_attribute('data-theme'),'dark');self.assertFalse(errors)
        self.page.add_script_tag(content="localStorage.getItem('x');")
        self.assertTrue(errors)
    def test_F18_close_scroll(self):
        self.content('<details data-mobile-nav><summary>menu</summary><a href="#top">home</a></details>')
        self.page.add_script_tag(content=UI_JS)
        self.page.locator('summary').click();self.page.locator('details').press('Escape')
        def scrollable():return self.page.evaluate("getComputedStyle(document.body).overflow!=='hidden'")
        self.assertTrue(scrollable());self.page.add_style_tag(content='body{overflow:hidden}');self.assertFalse(scrollable())
    def test_F19_disclosure_focus_restore(self):
        self.content('<details data-mobile-nav><summary>menu</summary><a href="#top">home</a></details><button id="other">other</button>')
        self.page.add_script_tag(content=UI_JS);self.page.locator('summary').click();self.page.locator('a').focus();self.page.locator('a').press('Escape')
        self.assertEqual(self.page.evaluate('document.activeElement.tagName'),'SUMMARY')
        self.page.locator('#other').focus();self.assertNotEqual(self.page.evaluate('document.activeElement.tagName'),'SUMMARY')
        # Production draft uses non-modal details. Modal trapping is not claimed.
    def test_F20_top_overlap(self):
        def overlap():return self.page.evaluate("""()=>{let a=document.querySelector('#score').getBoundingClientRect(),b=document.querySelector('#toplink').getBoundingClientRect();return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top}""")
        self.content('<div id="score">118:115</div><a id="toplink" class="wf-top" href="#top">top</a>');self.assertFalse(overlap())
        self.page.add_style_tag(content='#score,#toplink{position:fixed;top:0;left:0;bottom:auto;right:auto}');self.assertTrue(overlap())

if __name__=='__main__':unittest.main()
