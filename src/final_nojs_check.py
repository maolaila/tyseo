"""No-JavaScript navigation/readability supplement for the final user run."""
import argparse
from collections import Counter

from playwright.sync_api import sync_playwright

from core import ROOT, read_json, save_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args=parser.parse_args()
    run=(ROOT/args.run).resolve()
    if not run.is_relative_to(ROOT/'runs') or not (run/'summary.json').is_file():
        raise ValueError('Completed final journey run required under runs/')
    cases=read_json(ROOT/'config/final-user-cases.json')['specific']
    results=[]
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        try:
            for folder in sorted(run.iterdir()):
                if not folder.is_dir() or not (folder/'summary.json').exists():continue
                name=folder.name;base=read_json(folder/'summary.json')['preview_base_url']
                paths=sorted({'/',cases[name]['path']})
                for width in (390,1280):
                    context=browser.new_context(viewport={'width':width,'height':900},java_script_enabled=False)
                    page=context.new_page()
                    for path in paths:
                        try:
                            response=page.goto(base+path,wait_until='load',timeout=25000)
                            evidence=page.evaluate('''() => ({text:document.body.innerText.trim().length,
                                main:document.querySelector('main')?.innerText.trim().length||0,
                                links:[...document.querySelectorAll('nav a[href],header a[href],main a[href]')]
                                    .filter(x=>x.getClientRects().length).length,
                                overflow:document.documentElement.scrollWidth-innerWidth,
                                overflow_elements:[...document.querySelectorAll('body *')]
                                    .filter(x=>x.getClientRects().length&&x.getBoundingClientRect().right>innerWidth+2)
                                    .slice(0,8).map(x=>({tag:x.tagName,cls:String(x.className).slice(0,90),
                                        right:Math.round(x.getBoundingClientRect().right)}))})''')
                            status='pass' if response.status==200 and evidence['text']>20 and evidence['links']>0 and evidence['overflow']<=2 else 'fail'
                            results.append({'template':name,'path':path,'width':width,'status':status,'http':response.status,**evidence})
                        except Exception as error:
                            results.append({'template':name,'path':path,'width':width,'status':'blocked','error':str(error)[:180]})
                    context.close()
        finally:browser.close()
    save_json(run/'nojs-results.json',results)
    summary={'states':len(results),'status_counts':dict(Counter(x['status'] for x in results)),
             'scope':'Home and assigned template-specific path at 390/1280 CSS px, Chromium without JavaScript'}
    save_json(run/'nojs-summary.json',summary)
    print(summary)


if __name__=='__main__':main()
