"""Check sticky standings header and league-tab effects on the real z16 portal."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from core import resolve_repo_root, ROOT,fingerprint,git,read_json,save_json


def run(output,base):
    out=(ROOT/output).resolve()
    if not out.is_relative_to(ROOT/'runs') or out.exists():raise ValueError('Use a new runs/ directory')
    if base!='http://127.0.0.1:6316':raise ValueError('Only the current z16 local preview is supported')
    cli=shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')
    if not cli or subprocess.check_output([cli,'--version'],text=True).strip()!='0.1.20':
        raise RuntimeError('playwright-cli 0.1.20 required')
    repo=resolve_repo_root()
    files=[Path(__file__),ROOT/'scripts/cli-z16-portal-header.js',ROOT/'scripts/layout-audit.js',
           ROOT/'config/acceptance-policy.json',repo/'templates/z16/index.html',
           repo/'templates/z16/widgets/portal/data_center.html',repo/'static/z16/css/z16-portal-home.css',
           repo/'static/z16/css/z16.css',repo/'static/z16/js/z16-portal-home.js']
    identity={'template':'z16','commit':git(repo,'rev-parse','HEAD'),'policy':'2.4','cli':'0.1.20'}
    before=fingerprint(identity,files)
    out.mkdir(parents=True)
    code=(ROOT/'scripts/cli-z16-portal-header.js').read_text(encoding='utf-8')
    code=code.replace('__BASE__',base).replace('__OUTPUT__',out.relative_to(ROOT).as_posix())
    code=code.replace('__LAYOUT_AUDIT__',(ROOT/'scripts/layout-audit.js').read_text(encoding='utf-8'))
    generated=out/'run-code.js';generated.write_text(code,encoding='utf-8')
    session='tyseo-z16-sticky-'+hashlib.sha256(str(out).encode()).hexdigest()[:8]
    try:
        opened=subprocess.run([cli,f'-s={session}','open',base+'/'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
        if opened.returncode:raise RuntimeError('CLI open failed: '+opened.stderr[:150])
        result=subprocess.run([cli,f'-s={session}','run-code','--filename',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
        (out/'cli-output.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
        match=re.search(r'### Result\s*\n(.*?)\n### Ran',result.stdout,re.S)
        data=json.loads(match.group(1)) if result.returncode==0 and match else {'passed':False,'error':'CLI result unavailable'}
        data.update(input_hash=before,source_fresh=before==fingerprint(identity,files),source_commit=identity['commit'],cli_exit=result.returncode)
        save_json(out/'result.json',data)
        findings=[{'rule_id':'LAYOUT-STICKY-HEADER-INTEGRITY','page':base+'/','viewport':x.get('width'),
                   'theme':x.get('theme'),'scrollTop':x.get('scrollTop'),'status':x.get('status'),
                   'expected':'Opaque, readable, hit-testable sticky header and no page overflow',
                   'actual':x,'severity':'P1','owner_layer':'template','evidence_paths':['result.json','cli-output.txt']}
                  for x in [*data.get('states',[]),*data.get('tabs',[])] if x.get('status')!='pass']
        save_json(out/'findings.json',findings)
        summary={'states':len(data.get('states',[])),'tab_switches':len(data.get('tabs',[])),
                 'failed':len(findings),'passed':bool(data.get('passed') and data['source_fresh'] and result.returncode==0),
                 'source_fresh':data['source_fresh'],'source_commit':identity['commit']}
        save_json(out/'summary.json',summary)
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
