"""Read-only real-app template review via existing process environment selection.

Never edits .env or Python. Two isolated copies of the existing server at a time.
"""
import asyncio
import os
import sys
import time
import subprocess
import json
from pathlib import Path
from urllib.parse import urlsplit
import requests
from playwright.async_api import async_playwright
from core import ROOT,read_json,save_json,fingerprint,git
from audit import run_audit
from browser_checks import LAYOUT_JS

RUN_ROOT=ROOT/'runs/z-review'

async def review_one(index, browser, semaphore):
    async with semaphore:
        template=f'z{index}';out=RUN_ROOT/template;out.mkdir(parents=True,exist_ok=True)
        repo=Path(read_json(ROOT/'tasks/bootstrap.json')['repo_root'])
        inputs=[repo/'run.py',repo/'config.py',repo/'cache/cache_data.py',*list((repo/'templates'/template).rglob('*.html')),
                *[p for p in (repo/'static'/template).rglob('*') if p.is_file()]]
        input_hash=fingerprint({'template':template,'commit':git(repo,'rev-parse','HEAD')},inputs)
        if (out/'summary.json').exists():
            if read_json(out/'summary.json').get('input_hash')!=input_hash:
                raise ValueError(template+': stale or unversioned review; preserve evidence and start a new run')
            print('resume: '+template+' already has first-pass summary',flush=True);return
        task=read_json(ROOT/'tasks/bootstrap.json');task['reference_template_id']=template
        port=5800+index;task['preview_base_url']=f'http://127.0.0.1:{port}'
        env=os.environ.copy();env.update(DEV_MasterID=template,APP_ENV='development',FLASK_HOST='127.0.0.1',FLASK_PORT=str(port),PYTHONDONTWRITEBYTECODE='1')
        python=Path(task['repo_root'])/'.venv/Scripts/python.exe'
        server=subprocess.Popen([str(python),'-B','-u','run.py'],cwd=task['repo_root'],env=env,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        records=read_json(out/'visual-results.json') if (out/'visual-results.json').exists() else []
        completed={(r.get('page'),r.get('width')) for r in records}
        try:
            ready=False
            for _ in range(25):
                if server.poll() is not None:break
                try:
                    r=await asyncio.to_thread(requests.get,task['preview_base_url']+'/static/js/jquery.min.js',timeout=2)
                    if r.status_code==200:ready=True;break
                except requests.RequestException:pass
                await asyncio.sleep(.4)
            if not ready:
                save_json(out/'summary.json',{'template':template,'status':'blocked','reason':'Preview process failed to start'});return
            contract=read_json(out/'page-contract.json') if (out/'page-contract.json').exists() else await asyncio.to_thread(run_audit,task,out)
            save_json(out/'task-resolved.json',task)
            selection=await asyncio.to_thread(requests.get,task['preview_base_url']+'/',timeout=20)
            selection_ok=f'/static/{template}/' in selection.text
            for p in contract['pages']:
                urls=[x['path'] for x in p.get('http_samples',[]) if x['status']==200]
                if not urls:
                    if (p['page_type_id'],None) not in completed:records.append({'page':p['page_type_id'],'status':'blocked','reason':'No successful real URL','environment':'real_app'})
                    continue
                for width in (390,1280):
                    if (p['page_type_id'],width) in completed:continue
                    ctx=await browser.new_context(viewport={'width':width,'height':900},color_scheme='light',
                        user_agent='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36' if width==390 else None)
                    page=await ctx.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)[:160]))
                    record={'template':template,'page':p['page_type_id'],'url':urls[0],'width':width,'theme':'light','environment':'real_app','status':'blocked','selection_verified':selection_ok}
                    stem=f"{p['page_type_id']}-{width}"
                    try:
                        resp=await page.goto(task['preview_base_url']+urls[0],wait_until='domcontentloaded',timeout=22000)
                        if not resp or resp.status>=500:raise ValueError('HTTP server error, no debugger screenshot stored')
                        metrics=await page.evaluate(LAYOUT_JS)
                        shots=out/'screenshots';shots.mkdir(exist_ok=True)
                        await page.screenshot(path=str(shots/(stem+'.png')),full_page=True,animations='disabled',timeout=15000)
                        await page.screenshot(path=str(shots/(stem+'-viewport.png')),animations='disabled',timeout=15000)
                        features=await page.evaluate("""()=>({searchForms:[...document.forms].map(x=>({action:x.getAttribute('action'),inputs:[...x.elements].map(i=>i.name)})),themeButtons:[...document.querySelectorAll('button,[role=button]')].map(x=>({label:(x.getAttribute('aria-label')||x.innerText).slice(0,60)})).filter(x=>/theme|dark|light|主题|模式/i.test(x.label)),scripts:[...document.scripts].map(x=>x.getAttribute('src')).filter(Boolean),pageTitle:document.title})""")
                        clipped=[s for s in metrics['scoreBoxes'] if s['visible'] and (s['x']<0 or s['right']>width+2)]
                        record.update(status='fail' if metrics['scrollWidth']>width+2 or clipped or errors or not selection_ok else 'needs_review',
                            metrics={k:v for k,v in metrics.items() if k!='scoreBoxes'},clipped_scores=clipped[:20],errors=errors,
                            features=features,screenshot='screenshots/'+stem+'.png',viewport_screenshot='screenshots/'+stem+'-viewport.png',
                            scope='first review, light only; full interaction/theme/no-JS acceptance not claimed')
                    except Exception as e:record['reason']=type(e).__name__
                    finally:await ctx.close()
                    records.append(record);save_json(out/'visual-results.json',records)
            save_json(out/'visual-results.json',records)
            summary={'template':template,'input_hash':input_hash,'selection_verified':selection_ok,'page_counts':contract['counts'],
                'observations':len(records),'fail':sum(r['status']=='fail' for r in records),'blocked':sum(r['status']=='blocked' for r in records),
                'needs_review':sum(r['status']=='needs_review' for r in records),'human_review':'pending','business_modified':False}
            save_json(out/'summary.json',summary)
            print(json.dumps(summary,ensure_ascii=False),flush=True)
        finally:
            # Terminate only this process tree (venv launcher may spawn actual interpreter on Windows).
            if os.name=='nt':
                subprocess.run(['taskkill','/PID',str(server.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:server.terminate()

async def main():
    async with async_playwright() as pw:
        browser=await pw.chromium.launch()
        semaphore=asyncio.Semaphore(4)
        await asyncio.gather(*(review_one(i,browser,semaphore) for i in range(1,22)))
        await browser.close()

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='runs/z-review')
    args=parser.parse_args();RUN_ROOT=(ROOT/args.output).resolve()
    if not RUN_ROOT.is_relative_to(ROOT/'runs'):raise ValueError('Review output must stay in external runs/')
    asyncio.run(main())
