"""Evidence-backed z16 inner-page filter and responsive layout regression via CLI."""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from acceptance import collect_http
from core import resolve_repo_root, ROOT, fingerprint, git, read_json, save_json


def run(output, base, browser_name='chrome'):
    out = (ROOT / output).resolve()
    if not out.is_relative_to(ROOT / 'runs') or out.exists():
        raise ValueError('Use a new directory under external runs/')
    origin = urlsplit(base)
    if origin.scheme != 'http' or origin.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('Only local preview URLs are supported')
    cli = shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')
    if not cli or subprocess.check_output([cli, '--version'], text=True).strip() != '0.1.20':
        raise RuntimeError('playwright-cli 0.1.20 is required')
    repo = resolve_repo_root()
    script = ROOT / 'scripts/cli-z16-leo-regression.js'
    inputs = [script, Path(__file__), ROOT/'config/acceptance-policy.json',
              *(repo/'templates/z16').rglob('*.html'),
              *(p for p in (repo/'static/z16').rglob('*') if p.is_file())]
    identity = {'template':'z16', 'commit':git(repo,'rev-parse','HEAD'), 'base':base,'browser':browser_name}
    before = fingerprint(identity, inputs)
    out.mkdir(parents=True)
    for name, path in [('team_info','/yingchao/teams/teaminfo-10012.html'),
                       ('team_matches','/yingchao/teams/10012.html'),
                       ('related','/ajia/4539770.html'),
                       ('reported_sample','/aoweichao/4653594.html')]:
        collect_http(base + path, out/'http'/name)
    generated = out/'run-code.js'
    generated.write_text(script.read_text(encoding='utf-8')
        .replace('http://127.0.0.1:6316', base)
        .replace('runs/z16-leo-regression-20260919/', out.relative_to(ROOT).as_posix()+'/'), encoding='utf-8')
    session = 'tyseo-z16-hardgate-'+browser_name
    try:
        opened = subprocess.run([cli,f'-s={session}','open',base+'/',f'--browser={browser_name}'],cwd=ROOT,
            capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
        if opened.returncode:
            raise RuntimeError('CLI open failed')
        result = subprocess.run([cli,f'-s={session}','run-code','--filename',str(generated)],cwd=ROOT,
            capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
        (out/'cli-output.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
        match = re.search(r'### Result\s*\n(.*?)\n### Ran',result.stdout,re.S)
        data = json.loads(match.group(1)) if result.returncode == 0 and match else {'passed':False,'error':'CLI result unavailable'}
        data.update(browser=browser_name,input_hash=before,source_fresh=before==fingerprint(identity,inputs),source_commit=identity['commit'])
        save_json(out/'result.json',data)
        paths={'team_info':'/yingchao/teams/teaminfo-10012.html',
               'team_match_list':'/yingchao/teams/10012.html','detail_related':'/ajia/4539770.html'}
        findings=[]
        for state in data.get('states',[]):
            if state['status']=='pass':
                continue
            findings.append({
                'rule_id':state.get('rule_id','FILTER-RESULT-SET'),
                'page':base+paths[state['page']], 'viewport':{'width':state['width'],'height':900},
                'theme':state['theme'], 'data_state':state.get('data_state','observed'),
                'environment':state['environment'], 'status':state['status'],
                'selector':'#tab-fixture, .z16-team-match-wrap' if 'checks' in state else '.match_box .match-item .info_center',
                'expected':'Exact filtered row IDs and usable empty/reset states' if 'checks' in state else 'Containment, no unintended overlap, and z16 breakpoint-specific component topology',
                'actual':state, 'severity':'P1', 'owner_layer':'template',
                'evidence_paths':['result.json','cli-output.txt']})
        save_json(out/'findings.json',findings)
        summary={k:data.get(k) for k in ('counts','negative_controls','passed','source_fresh')}
        save_json(out/'summary.json',summary)
        print(json.dumps(summary))
        if not data.get('passed') or not data['source_fresh']:
            raise SystemExit(1)
    finally:
        subprocess.run([cli,f'-s={session}','close'],cwd=ROOT,capture_output=True,timeout=30)


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:6316')
    parser.add_argument('--browser',choices=('chrome','firefox','webkit'),default='chrome')
    args=parser.parse_args()
    run(args.output,args.base_url.rstrip('/'),args.browser)
