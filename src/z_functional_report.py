"""Merge current z functional HTTP/browser evidence without promoting stale PASS."""
import argparse
from collections import Counter,defaultdict
from pathlib import Path

from core import resolve_repo_root, ROOT,fingerprint,git,read_json,save_json


def report(http_run,overrides,browser_runs,output):
    source=(ROOT/http_run).resolve();out=(ROOT/output).resolve()
    if not source.is_relative_to(ROOT/'runs') or not out.is_relative_to(ROOT/'runs') or out.exists():
        raise ValueError('Existing inputs and new output must be under runs/')
    for path in [*overrides,*browser_runs]:
        if not (ROOT/path).resolve().is_relative_to(ROOT/'runs'):raise ValueError('Evidence only under runs/')
    out.mkdir(parents=True)
    repo=resolve_repo_root()
    docs=read_json(source/'pages.json')
    expected={(d['template'],d['path'],width) for d in docs if d['status']==200 for width in (390,1280)}
    checks=defaultdict(list)
    for item in read_json(source/'links.json'):checks[item['template']].append(item)
    for directory in overrides:
        group=defaultdict(list)
        for item in read_json(ROOT/directory/'links.json'):group[item['template']].append(item)
        checks.update(group)
    stamp={}
    for name in sorted({x[0] for x in expected},key=lambda x:int(x[1:])):
        inputs=[*(repo/'templates'/name).rglob('*.html'),*(p for p in (repo/'static'/name).rglob('*') if p.is_file()),
                ROOT/'config/acceptance-policy.json',ROOT/'src/z_page_actions.py',ROOT/'scripts/cli-z-page-actions.js']
        identity={'commit':git(repo,'rev-parse','HEAD'),'template':name,'policy':'2.3','cli':'0.1.20'}
        stamp[name]=fingerprint(identity,inputs)
    observed={};stale=[]
    for directory in browser_runs:
        for file in sorted((ROOT/directory).rglob('z*-results.json')):
            name=file.name.split('-')[0]
            if name not in stamp:continue
            data=read_json(file)
            if not isinstance(data,dict):continue  # combined list has no per-part provenance
            if data.get('input_hash')!=stamp[name] or data.get('cli_exit')!=0 or not data.get('source_fresh'):
                stale.append(file.relative_to(ROOT).as_posix());continue
            for page in data.get('pages',[]):
                key=(name,page['path'],page['width'])
                if key in expected:observed[key]={'data':page,'evidence':file.relative_to(ROOT).as_posix()}
    results=[];dynamic_404=[]
    for name in sorted(stamp,key=lambda x:int(x[1:])):
        actual={k:v for k,v in observed.items() if k[0]==name}
        missing=sorted([k[1:] for k in expected if k[0]==name and k not in actual])
        pages=[v['data'] for v in actual.values()]
        actions=[x for p in pages for x in p['actions']]
        links=[x for p in pages for x in p['links']]
        raw=checks[name]
        def broken(x):
            status=x['status'];target=x.get('destination_status')
            return status=='blocked' or isinstance(status,int) and status>=400 or isinstance(target,int) and target>=400
        raw_fail=[x for x in raw if broken(x)]
        raw_404=[x for x in raw if x['status']==404 or x.get('destination_status')==404]
        raw_backend=[x for x in raw_fail if x not in raw_404]
        for (template,path,width),record in actual.items():
            for action in [*record['data']['links'],*record['data']['actions']]:
                if action.get('http_status')==404 or action.get('navigation_status')==404:
                    dynamic_404.append({'template':name,'source':path,'width':width,'href':action.get('href'),
                                        'target':action.get('navigation_url') or action.get('actual_url'),
                                        'evidence':record['evidence']})
        result={'template':name,'states_planned':sum(k[0]==name for k in expected),
                'states_current':len(actual),'states_missing':missing,
                'pages_blocked':sum(p.get('status')=='blocked' for p in pages),
                'pages_error':sum(bool(p.get('error')) for p in pages),
                'link_results':dict(Counter(x['status'] for x in links)),
                'action_results':dict(Counter(x['status'] for x in actions)),
                'untested':sum(len(p['untested']) for p in pages),
                'http_targets':len(raw),'http_fail':len(raw_fail),'http_backend_blocked':len(raw_backend),
                'http_404':[{'path':x['path'],'sources':x['sources']} for x in raw if x['status']==404],
                'status':'fail' if raw_404 or any(x['status']=='fail' for x in [*links,*actions]) else
                         'blocked' if raw_backend or missing or any(p.get('status')=='blocked' or p.get('error') for p in pages) else
                         'needs_review' if any(x['status']=='needs_review' for x in [*links,*actions]) or sum(len(p['untested']) for p in pages) else 'pass'}
        results.append(result)
    summary={'policy_version':'2.3','source_commit':git(repo,'rev-parse','HEAD'),
             'existing_page_types':sum(x['states_planned'] for x in results)//2+read_json(source/'summary.json')['blocked_page_samples'],
             'current_sample_states':len(expected),'current_states':len(observed),
             'missing_states':len(expected)-len(observed),'stale_files':stale,
             'http_404':sum(len(x['http_404']) for x in results),'dynamic_404':dynamic_404,
             'results':results,'ready_for_human_review':False,
             'reason':'Unresolved raw route errors, backend/shared dependencies, missing samples or review states require resolution'}
    save_json(out/'summary.json',summary)
    lines=['# z1–z17 功能复查（当前证据）','',
           f"样例状态 {len(observed)}/{len(expected)}；过期结果文件 {len(stale)}；原始链接404 {summary['http_404']}；浏览器新增404 {len(dynamic_404)}。",
           '状态来自当前源码指纹；共享/后端错误和未覆盖项不能计PASS。线上、公司验收、合并及部署未在本报告验证。','',
           '|模板|状态|两宽度覆盖|内部目标失败|动作失败|blocked页面|待复核动作|','|---|---|---:|---:|---:|---:|---:|']
    for r in results:
        lines.append(f"|{r['template']}|{r['status']}|{r['states_current']}/{r['states_planned']}|{r['http_fail']}|{r['action_results'].get('fail',0)}|{r['pages_blocked']}|{r['action_results'].get('needs_review',0)+r['untested']}|")
    lines.extend(['','## 本地404（待逐项确认）',''])
    for r in results:
        for item in r['http_404']:
            source_path=item['sources'][0]['source'] if item['sources'] else 'unknown'
            lines.append(f"- {r['template']} `{source_path}` → `{item['path']}`")
    for item in dynamic_404:lines.append(f"- 浏览器新增 {item['template']} `{item['source']}` → `{item['target']}` ({item['width']}px)")
    (out/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print({'states':f'{len(observed)}/{len(expected)}','stale_files':len(stale),'http_404':summary['http_404'],
           'dynamic_404':len(dynamic_404),'status':dict(Counter(x['status'] for x in results))})


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--http-run',required=True)
    parser.add_argument('--http-overrides',nargs='*',default=[])
    parser.add_argument('--browser-runs',nargs='+',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report(args.http_run,args.http_overrides,args.browser_runs,args.output)
