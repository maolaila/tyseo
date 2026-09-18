"""Saved fixture documents are replayed in isolated browser contexts, never production."""
from pathlib import Path
from urllib.parse import urlsplit
import json
from playwright.sync_api import sync_playwright
from core import save_json,inside
from checks import html_checks

LAYOUT_JS="""() => ({
  width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
  bodyText:document.body.innerText.length,
  headings:[...document.querySelectorAll('h1')].map(x=>x.innerText),
  brokenImages:[...document.images].filter(x=>x.complete&&!x.naturalWidth).length,
  scoreBoxes:[...document.querySelectorAll('.score')].map(x=>{let r=x.getBoundingClientRect();return {text:x.innerText,x:r.x,right:r.right,width:r.width,visible:r.width>0&&r.height>0}}),
  background:getComputedStyle(document.body).backgroundColor,
  color:getComputedStyle(document.body).color,
  effectiveTheme:document.documentElement.getAttribute('data-theme')
})"""

def execute_matrix(task,contract,out,render_dir=None,design=None):
    out=Path(out);(out/'screenshots').mkdir(parents=True,exist_ok=True)
    fixture=render_dir is not None
    environment='fixture' if fixture else 'real_app'
    results=[];matrix=task['browser_matrix']
    with sync_playwright() as pw:
        for engine in [matrix['primary_engine'],*matrix['secondary_engines']]:
            try: browser=getattr(pw,engine).launch()
            except Exception as e:
                results.append({'engine':engine,'status':'blocked','reason':type(e).__name__,
                                'detail':str(e)[:280],'environment':environment});continue
            for p in contract['pages']:
                page_id=p['page_type_id']
                if engine!='chromium' and page_id not in ('index','detail','type_list','search','detail_zb'):continue
                configs=[(w,t,True) for w in matrix['widths'] for t in matrix['themes']]+[(w,'light',False) for w in matrix['no_js_widths']]
                if engine!='chromium':configs=[(390,'light',True),(1280,'dark',True)]
                if fixture:
                    file=Path(render_dir)/(page_id+'.html')
                    available=file.exists()
                else: available=any(x['status']==200 for x in p.get('http_samples',[]))
                for width,theme,js in configs:
                    result={'page_type_id':page_id,'width':width,'theme':theme,'javascript':js,'engine':engine,'environment':environment,'status':'blocked','evidence_paths':[]}
                    if not available:
                        result['reason']='No rendered document or successful real sample';results.append(result);continue
                    if not fixture and next(x['path'] for x in p['http_samples'] if x['status']==200).startswith('/play/'):
                        result.update(reason='Shared playback response outside z template scope',owner_layer='backend_shared_playback')
                        results.append(result)
                        continue
                    context=browser.new_context(viewport={'width':width,'height':900},color_scheme=theme,java_script_enabled=js,
                        user_agent='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36' if width<768 else None)
                    template_id=task.get('reference_template_id')
                    if not fixture and js and template_id and template_id.startswith('z') and template_id[1:].isdigit():
                        context.add_init_script(script=f"try {{ localStorage.setItem('{template_id}-theme', '{theme}'); }} catch (e) {{}}")
                    page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)[:180]))
                    if fixture:
                        root=Path(render_dir).parents[2]/'drafts'/design
                        repo=Path(task['repo_root'])
                        def handle(route):
                            path=urlsplit(route.request.url).path
                            if path.startswith('/static/draft/'):
                                asset=root/'static/draft'/path[len('/static/draft/'):]
                            elif path.startswith('/static/'):
                                asset=repo/path.lstrip('/')
                            else: asset=None
                            if asset and (inside(asset,root/'static') or inside(asset,repo/'static')) and asset.is_file():route.fulfill(path=str(asset));return
                            if route.request.resource_type=='document':route.fulfill(body=file.read_text(encoding='utf-8'),content_type='text/html');return
                            route.abort() # No production trackers/remote images from fixture documents.
                        context.route('**/*',handle)
                        url='http://fixture.local/'+page_id
                    else:
                        url=task['preview_base_url']+next(x['path'] for x in p['http_samples'] if x['status']==200)
                    try:
                        response=page.goto(url,wait_until='domcontentloaded',timeout=25000)
                        if response and response.status>=500:raise ValueError('Server error; do not save debugger locals')
                        page.locator('body').wait_for()
                        # Layout measurements need loaded stylesheets; DOMContentLoaded alone can capture bare markup.
                        page.wait_for_load_state('load',timeout=15000)
                        metrics=page.evaluate(LAYOUT_JS)
                        stem=f'{page_id}-{engine}-{width}-{theme}-'+('js' if js else 'nojs')
                        image='screenshots/'+stem+'.png'
                        dom_dir=out/('rendered-dom' if js else 'nojs-dom');dom_dir.mkdir(exist_ok=True)
                        (dom_dir/(stem+'.html')).write_text(page.content(),encoding='utf-8')
                        raw_dir=out/'http-responses';raw_dir.mkdir(exist_ok=True)
                        if response:
                            (raw_dir/(stem+'.html')).write_bytes(response.body())
                            save_json(raw_dir/(stem+'.json'),{'kind':'http_response' if not fixture else 'fixture_response',
                                'url':url,'status':response.status,'headers':{k:v for k,v in response.headers.items() if k.lower() not in ('set-cookie','authorization')}})
                        document_height=page.evaluate('Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)')
                        if document_height <= 30000:
                            page.screenshot(path=str(out/image),full_page=True,animations='disabled')
                            images=[image]
                        else:
                            images=[]
                            for part,start in enumerate(range(0,document_height,12000),1):
                                tile=f'screenshots/{stem}-part{part}.png'
                                page.screenshot(path=str(out/tile),clip={'x':0,'y':start,'width':width,
                                    'height':min(12000,document_height-start)},full_page=True,animations='disabled')
                                images.append(tile)
                        viewport_image=f'screenshots/{stem}-viewport.png'
                        page.evaluate('window.scrollTo(0,0)')
                        page.screenshot(path=str(out/viewport_image),animations='disabled')
                        images.append(viewport_image)
                        evidence='screenshots/'+stem+'.json';save_json(out/evidence,metrics)
                        clipped=[s for s in metrics['scoreBoxes'] if s['visible'] and (s['x']<0 or s['right']>width+2)]
                        theme_mismatch=not fixture and js and metrics['effectiveTheme']!=theme
                        result.update(status='fail' if metrics['scrollWidth']>width+2 or not metrics['bodyText'] or errors or clipped or theme_mismatch else 'needs_review',
                                      evidence_paths=images+[evidence],metrics={k:v for k,v in metrics.items() if k!='scoreBoxes'},clipped_scores=clipped,errors=errors,
                                      screenshot_tiled=document_height>30000,
                                      theme_state={'requested':theme,'observed':metrics['effectiveTheme'],
                                          'state_matches':not theme_mismatch if js else None,
                                          'scope':'DOM theme state only; visual contrast review separate'},
                                      capture_status='pass',ai_visual_review='needs_review',ai_seo_review='needs_review',
                                      http_evidence=str((raw_dir/(stem+'.html')).relative_to(out)),
                                      dom_evidence=str((dom_dir/(stem+'.html')).relative_to(out)),
                                      scope='geometry/body/script observations; functions, semantics and visual review separate')
                        if fixture and js:
                            interactions={}
                            button=page.locator('[data-theme-toggle]')
                            if button.count():
                                button.click();interactions['theme_toggle']=page.locator('html').get_attribute('data-theme')!=theme
                                page.reload(wait_until='domcontentloaded');interactions['theme_persist']=page.locator('html').get_attribute('data-theme')!=theme
                            nav=page.locator('[data-mobile-nav]')
                            if width<900 and nav.count():
                                nav.locator('summary').click();interactions['nav_open']=nav.get_attribute('open') is not None
                                nav.press('Escape');interactions['nav_close']=nav.get_attribute('open') is None
                                interactions['body_scroll_restored']=page.evaluate("getComputedStyle(document.body).overflow")!='hidden'
                            top=page.locator('.wf-top')
                            if top.count():
                                page.evaluate('scrollTo(0,document.body.scrollHeight)');top.click();interactions['goto_top']=page.evaluate('scrollY')==0
                            result['interactions']=interactions
                            if not all(interactions.values()):result['status']='fail'
                    except Exception as e:result.update(status='blocked',reason=type(e).__name__,detail=str(e)[:280])
                    finally:context.close()
                    results.append(result)
                    save_json(out/'matrix-results.json',results)
            browser.close()
    save_json(out/'matrix-results.json',results)
    return results
