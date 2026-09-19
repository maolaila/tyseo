"""Saved fixture documents are replayed in isolated browser contexts, never production."""
from pathlib import Path
from collections import Counter
from urllib.parse import urlsplit
import json
from playwright.sync_api import sync_playwright
from core import ROOT,save_json,inside,read_json
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

def compact_review_queue(findings, evidence):
    counts=Counter((f['rule_id'],f['status']) for f in findings if f['status'] in ('needs_review','blocked'))
    return [{'rule_id':rule,'status':status,'occurrences':count,'evidence_paths':[evidence]}
            for (rule,status),count in sorted(counts.items())]

def execute_matrix(task,contract,out,render_dir=None,design=None):
    out=Path(out);(out/'screenshots').mkdir(parents=True,exist_ok=True)
    fixture=render_dir is not None
    environment='fixture' if fixture else 'real_app'
    results=[];matrix=task['browser_matrix']
    layout_js=(ROOT/'scripts/layout-audit.js').read_text(encoding='utf-8')
    shift_js=(ROOT/'scripts/layout-shift-init.js').read_text(encoding='utf-8')
    policy=read_json(ROOT/'config/acceptance-policy.json')
    matrix=dict(matrix)
    if not task.get('_focused_matrix'):
        matrix['widths']=sorted(set(matrix['widths']+policy['widths']))
        matrix['no_js_widths']=sorted(set(matrix['no_js_widths']+policy['no_js_widths']))
        matrix['secondary_engines']=list(dict.fromkeys(matrix['secondary_engines']+['webkit','firefox']))
    with sync_playwright() as pw:
        for engine in [matrix['primary_engine'],*matrix['secondary_engines']]:
            try: browser=getattr(pw,engine).launch()
            except Exception as e:
                results.append({'engine':engine,'status':'blocked','reason':type(e).__name__,
                                'detail':str(e)[:280],'environment':environment});continue
            for p in contract['pages']:
                page_id=p['page_type_id']
                if engine!='chromium' and page_id not in ('index','detail','type_list','search','detail_zb'):continue
                configs=[(w,t,True,'normal',900) for w in matrix['widths'] for t in matrix['themes']]+[(w,t,False,'normal',900) for w in matrix['no_js_widths'] for t in matrix['themes']]
                if engine=='chromium':
                    configs += [(w,t,True,stress,900) for w in (390,1280) if w in matrix['widths'] for t in matrix['themes'] for stress in ('text_resize_200','wcag_text_spacing')]
                    if not task.get('_focused_matrix') and page_id in ('index','detail','type_list','article_list','search','detail_zb'):
                        layout=p.get('layout_contract') if isinstance(p.get('layout_contract'),dict) else {}
                        points=sorted({int(b)+d for b in layout.get('breakpoints',[900]) for d in (-1,0,1) if int(b)+d>=320})
                        configs += [(w,t,True,'normal',900) for w in points for t in matrix['themes']]
                        configs += [(844,t,True,'landscape',390) for t in matrix['themes']]
                else:configs=[(w,t,True,'normal',900) for w in (390,1280) for t in matrix['themes']]
                configs=list(dict.fromkeys(configs))
                if fixture:
                    file=Path(render_dir)/(page_id+'.html')
                    available=file.exists()
                else: available=any(x['status']==200 for x in p.get('http_samples',[]))
                for width,theme,js,stress,height in configs:
                    result={'page_type_id':page_id,'width':width,'height':height,'stress':stress,'theme':theme,'javascript':js,'engine':engine,'environment':environment,'status':'blocked','evidence_paths':[]}
                    if not available:
                        result['reason']='No rendered document or successful real sample';results.append(result);continue
                    if not fixture and next(x['path'] for x in p['http_samples'] if x['status']==200).startswith('/play/'):
                        result.update(reason='Shared playback response outside z template scope',owner_layer='backend_shared_playback')
                        results.append(result)
                        continue
                    context=browser.new_context(viewport={'width':width,'height':height},color_scheme=theme,java_script_enabled=js,
                        user_agent='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36' if width<768 else None)
                    template_id=task.get('reference_template_id')
                    if not fixture and js and template_id and template_id.startswith('z') and template_id[1:].isdigit():
                        context.add_init_script(script=f"try {{ localStorage.setItem('{template_id}-theme', '{theme}'); }} catch (e) {{}}")
                    page=context.new_page();errors=[]
                    if js:page.add_init_script(script=shift_js)
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
                        if stress=='text_resize_200':
                            page.evaluate("""() => {const sizes=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);for(const [e,size] of sizes)if(size)e.style.setProperty('font-size',(size*2)+'px','important');}""")
                        elif stress=='wcag_text_spacing':
                            page.add_style_tag(content='*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}')
                        metrics=page.evaluate(LAYOUT_JS)
                        component_audit=page.evaluate(layout_js,p.get('layout_contract') or {})
                        if js:
                            page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
                        shift=page.evaluate('window.__layoutShiftAudit || null') if js else None
                        if shift:
                            shift['observed_duration_ms']=page.evaluate('performance.now()')-shift['startedAt']
                            shift['threshold']=policy['lab_cls_target']
                            shift['test_stress']=stress
                            shift['sample_end']='before screenshot animation overrides'
                            if stress=='normal' and shift['supported'] and shift['value']>policy['lab_cls_target']:
                                component_audit['findings'].append({'rule_id':'LAYOUT-LAB-CLS','status':'fail','selector':'document','severity':'P1','owner_layer':'template_or_external_asset','expected':policy['lab_cls_target'],'actual':shift['value']})
                        stem=f'{page_id}-{engine}-{width}-{theme}-'+('js' if js else 'nojs')
                        if stress!='normal':stem+='-'+stress
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
                        metrics['component_audit']=component_audit
                        metrics['layout_shift']=shift
                        evidence='screenshots/'+stem+'.json';save_json(out/evidence,metrics)
                        clipped=[s for s in metrics['scoreBoxes'] if s['visible'] and (s['x']<0 or s['right']>width+2)]
                        theme_mismatch=not fixture and js and metrics['effectiveTheme']!=theme
                        result.update(status='fail' if metrics['scrollWidth']>width+2 or not metrics['bodyText'] or errors or clipped or theme_mismatch or any(x['status']=='fail' for x in component_audit['findings']) else 'needs_review',
                                      evidence_paths=images+[evidence],metrics={k:v for k,v in metrics.items() if k not in ('scoreBoxes','component_audit')},clipped_scores=clipped,errors=errors,
                                      screenshot_tiled=document_height>30000,
                                      theme_state={'requested':theme,'observed':metrics['effectiveTheme'],
                                          'state_matches':not theme_mismatch if js else None,
                                          'scope':'DOM theme state only; visual contrast review separate'},
                                      capture_status='pass',ai_visual_review='needs_review',ai_seo_review='needs_review',
                                      component_findings=[x for x in component_audit['findings'] if x['status']=='fail'],
                                      component_audit_evidence=evidence,
                                      tool_review_queue=compact_review_queue(component_audit['findings'],evidence),
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
