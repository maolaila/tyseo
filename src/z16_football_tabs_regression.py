"""Real z16 sport-hub standings tabs, empty state, navigation and no-JS HTML."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup
from acceptance import collect_http
from core import ROOT,fingerprint,git,read_json,save_json


def run(output,base):
    out=(ROOT/output).resolve()
    if not out.is_relative_to(ROOT/'runs') or out.exists():raise ValueError('Use a new runs/ directory')
    if base!='http://127.0.0.1:6316':raise ValueError('Only current z16 local preview is supported')
    cli=shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')
    if not cli or subprocess.check_output([cli,'--version'],text=True).strip()!='0.1.20':
        raise RuntimeError('playwright-cli 0.1.20 required')
    repo=Path(read_json(ROOT/'tasks/bootstrap.json')['repo_root'])
    files=[Path(__file__),ROOT/'scripts/cli-z16-football-tabs.js',ROOT/'config/acceptance-policy.json',
           repo/'templates/z16/type_list.html',repo/'templates/z16/widgets/football-portal/page.html',
           repo/'templates/z16/widgets/football-portal/standings.html',
           repo/'static/z16/js/z16-football.js',repo/'static/z16/css/z16-football-portal.css']
    identity={'template':'z16','commit':git(repo,'rev-parse','HEAD'),'policy':'2.4','cli':'0.1.20'}
    before=fingerprint(identity,files)
    out.mkdir(parents=True)
    raw=[]
    for name,path in [('football','/zuqiu'),('basketball','/lanqiu'),('league','/yingchao')]:
        folder=out/'http'/name
        response=collect_http(base+path,folder)
        soup=BeautifulSoup((folder/'http-body.html').read_text(encoding='utf-8',errors='replace'),'html.parser')
        body=soup.select_one('#fp-stand-body')
        text=body.get_text(' ',strip=True) if body else ''
        raw.append({'page':path,'http':response['status'],'has_body':bool(body),'has_rows':bool(body and body.select('.fp-stand__row:not(.fp-stand__row--empty)')),
                    'has_named_empty':('暂无' in text and '数据' in text),'body_sha256':response['body_sha256']})
    save_json(out/'raw-summary.json',raw)
    generated=out/'run-code.js'
    generated.write_text((ROOT/'scripts/cli-z16-football-tabs.js').read_text(encoding='utf-8')
                         .replace('__BASE__',base).replace('__OUTPUT__',out.relative_to(ROOT).as_posix()),encoding='utf-8')
    session='tyseo-z16-football-'+hashlib.sha256(str(out).encode()).hexdigest()[:8]
    try:
        opened=subprocess.run([cli,f'-s={session}','open',base+'/zuqiu'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
        if opened.returncode:raise RuntimeError('CLI open failed: '+opened.stderr[:140])
        result=subprocess.run([cli,f'-s={session}','run-code','--filename',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
        (out/'cli-output.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
        match=re.search(r'### Result\s*\n(.*?)\n### Ran',result.stdout,re.S)
        data=json.loads(match.group(1)) if result.returncode==0 and match else {'passed':False,'error':'CLI result unavailable'}
        data.update(input_hash=before,source_fresh=before==fingerprint(identity,files),source_commit=identity['commit'],cli_exit=result.returncode)
        save_json(out/'result.json',data)
        failed=[x for x in data.get('states',[]) if x.get('status')!='pass']
        raw_pass=all(x['http']==200 and x['has_body'] and (x['has_rows'] or x['has_named_empty']) for x in raw)
        summary={'tab_states':len(data.get('states',[])),'failed':len(failed),'raw_pages':len(raw),
                 'raw_pass':raw_pass,'passed':bool(data.get('passed') and not failed and raw_pass and data['source_fresh'] and result.returncode==0),
                 'source_fresh':data['source_fresh'],'source_commit':identity['commit']}
        save_json(out/'summary.json',summary)
        save_json(out/'findings.json',[{'rule_id':'ACTION-EFFECT','page':base+x['path'],'viewport':x['width'],'theme':x['theme'],
                                      'status':x['status'],'expected':'league-specific visible result and correct destination',
                                      'actual':x,'severity':'P1','owner_layer':'template','evidence_paths':['result.json','cli-output.txt']} for x in failed])
        print(json.dumps(summary))
        if not summary['passed']:raise SystemExit(1)
    finally:
        subprocess.run([cli,f'-s={session}','close'],cwd=ROOT,capture_output=True,timeout=30)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:6316')
    args=parser.parse_args()
    run(args.output,args.base_url.rstrip('/'))
