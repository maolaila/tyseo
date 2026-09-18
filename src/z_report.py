"""Aggregate first-pass observations without promoting them to acceptance."""
from pathlib import Path
import html
from collections import Counter
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from core import ROOT,read_json,save_json
from checks import html_checks

def main(index_only=False):
    root=ROOT/'runs/z-review';rows=[];findings=[]
    cards=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>z1–z21 检查索引</title><style>body{font:16px system-ui;margin:2rem;background:#f1f5f9}section{background:white;padding:1rem;margin-bottom:1rem}img{width:260px;max-height:450px;object-fit:contain;vertical-align:top}a{color:#075985}pre{white-space:pre-wrap}summary{cursor:pointer}.fail{color:#b91c1c}</style><h1>z1–z21 第一轮检查</h1><p>手机390 / 桌面1280，light。自动检查无异常不等于视觉通过；不替代全主题、无JS、全部交互验收。业务文件未修改。</p>']
    for i in range(1,22):
        name=f'z{i}';folder=root/name
        summary=read_json(folder/'summary.json') if (folder/'summary.json').exists() else {'template':name,'status':'in_progress'}
        records=read_json(folder/'visual-results.json') if (folder/'visual-results.json').exists() else []
        row={'template':name,'collection_finished':(folder/'summary.json').exists(),'counts':dict(Counter(r['status'] for r in records)),'records':len(records)}
        rows.append(row)
        cards.append('<section><h2>'+name+'</h2><pre>'+html.escape(str(row))+'</pre>')
        for r in records:
            cards.append('<details><summary class="'+r['status']+'">'+html.escape(f"{r['page']} · {r.get('width','无样例')} · {r['status']}")+'</summary>')
            if r.get('screenshot'):
                shot=name+'/'+r['screenshot'];view=name+'/'+r['viewport_screenshot']
                cards.append(f'<a href="{shot}"><img loading="lazy" src="{view}" alt="{html.escape(r["page"])}"></a>')
            cards.append('<pre>'+html.escape(str({k:r.get(k) for k in ('url','reason','metrics','errors','clipped_scores')}))+'</pre></details>')
            if r['status']=='fail':findings.append(dict(r,owner_layer='template_or_asset_needs_triage',baseline_or_regression='baseline'))
        for p in ([] if index_only else (folder/'raw-responses').glob('*.html')):
            meta=read_json(p.with_suffix('.json'))
            if meta['status']!=200:continue
            raw=p.read_text(encoding='utf-8'); soup=BeautifulSoup(raw,'html.parser')
            scripts={urlsplit(x.get('src','')).path for x in soup.select('script[src]')}
            for expected in ('/static/js/jquery.min.js','/static/js/ajs.js'):
                if expected not in scripts:findings.append({'template':name,'url':meta['url'],'rule':'required_shared_script','status':'needs_review','missing':expected,'evidence':str(p.relative_to(root))})
            for item in html_checks(raw,meta['headers']):
                if item['status']=='fail':findings.append(dict(item,template=name,url=meta['url'],evidence=str(p.relative_to(root))))
        cards.append('</section>')
    if index_only:
        old=read_json(root/'overview.json')
        findings += [f for f in old['findings'] if 'evidence' in f]
    save_json(root/'overview.json',{'templates':rows,'finished':sum(r['collection_finished'] for r in rows),'total':21,'findings':findings,'business_modified':False,'accepted':False,'raw_review':'previous report in same run; index refresh only' if index_only else 'executed'})
    (root/'review-index.html').write_text('\n'.join(cards),encoding='utf-8')
    text=['# z 系列第一轮检查','',f"采集完成 {sum(r['collection_finished'] for r in rows)}/21 套。这里只描述采集完成，不是模板验收完成。",'', '|模板|记录数|结果|采集完毕|','|---|---:|---|---|']
    for r in rows:text.append(f"|{r['template']}|{r['records']}|{r['counts']}|{r['collection_finished']}|")
    text+=['','详细证据见 review-index.html；未发现自动几何错误的条目仍为 needs_review。无成功样例的入口保留 blocked。','未修改业务代码、未推送/PR/合并、未写表、未上站。']
    (root/'report.md').write_text('\n'.join(text),encoding='utf-8')
    print(f"Report: {sum(r['collection_finished'] for r in rows)}/21 collected; {len(findings)} rule observations (not deduplicated defects)")

if __name__=='__main__':
    import sys
    main(index_only='--index-only' in sys.argv)
