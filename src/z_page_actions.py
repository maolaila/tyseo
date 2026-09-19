"""Per-existing-page browser clicks; raw href checking is in z_link_audit.py."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from core import ROOT, fingerprint, git, read_json, save_json


def run(input_dir, output, ids, max_pages=None):
    source = (ROOT/input_dir).resolve()
    out = (ROOT/output).resolve()
    if not source.is_relative_to(ROOT/'runs') or not out.is_relative_to(ROOT/'runs') or out.exists():
        raise ValueError('Use an existing HTTP run and a new browser run under runs/')
    cli = shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')
    if not cli or subprocess.check_output([cli,'--version'],text=True).strip()!='0.1.20':
        raise RuntimeError('playwright-cli 0.1.20 required')
    pages = read_json(source/'pages.json')
    repo = Path(read_json(ROOT/'tasks/bootstrap.json')['repo_root'])
    script = (ROOT/'scripts/cli-z-page-actions.js').read_text(encoding='utf-8')
    out.mkdir(parents=True)
    summary = []
    for number in ids:
        name=f'z{number}'
        all_paths=sorted({x['path'] for x in pages if x['template']==name and x['status']==200})
        paths=all_paths[:max_pages] if max_pages else all_paths
        if not paths:
            summary.append({'template':name,'status':'blocked','reason':'no current HTTP200 page samples'})
            continue
        generated=out/f'{name}-run-code.js'
        generated.write_text(script.replace('__PORT__',str(6300+number)).replace('__PATHS__',json.dumps(paths,ensure_ascii=False)),encoding='utf-8')
        session=f'tyseo-{name}-pages-{hashlib.sha256(str(out).encode()).hexdigest()[:8]}'
        template_inputs=[*(repo/'templates'/name).rglob('*.html'),*(p for p in (repo/'static'/name).rglob('*') if p.is_file()),ROOT/'config/acceptance-policy.json',ROOT/'src/z_page_actions.py',ROOT/'scripts/cli-z-page-actions.js']
        identity={'commit':git(repo,'rev-parse','HEAD'),'template':name,'policy':'2.3','cli':'0.1.20'}
        stamp=fingerprint(identity,template_inputs)
        try:
            opened=subprocess.run([cli,f'-s={session}','open',f'http://127.0.0.1:{6300+number}/'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=50)
            if opened.returncode: raise RuntimeError('CLI open failed: '+opened.stderr[:140])
            result=subprocess.run([cli,f'-s={session}','run-code','--filename',str(generated)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=max(300,len(paths)*45))
            (out/f'{name}-cli.txt').write_text(result.stdout+result.stderr,encoding='utf-8')
            match=re.search(r'### Result\s*\n(.*?)\n### Ran',result.stdout,re.S)
            data=json.loads(match.group(1)) if result.returncode==0 and match else []
            save_json(out/f'{name}-results.json',{'pages':data,'input_hash':stamp,'source_fresh':stamp==fingerprint(identity,template_inputs),'source_commit':identity['commit'],'cli_exit':result.returncode})
            failed=[{'template':name,'page':f'http://127.0.0.1:{6300+number}{x["path"]}',
                     'viewport':{'width':x['width'],'height':844},'theme':'observed browser preference',
                     'data_state':'real_app','rule_id':a['rule_id'],'status':a['status'],
                     'selector':a.get('control',{}).get('id') or a.get('control',{}).get('text') or a.get('href'),
                     'expected':'Actual navigation to a reachable page' if a['rule_id']=='LINK-NAVIGATION' else 'Observable documented action effect',
                     'actual':a,'severity':'P1','owner_layer':'backend or shared page' if x['path'].startswith('/play/') else 'template or data contract',
                     'evidence_paths':[f'{name}-results.json',f'{name}-cli.txt']}
                    for x in data for a in x['links']+x['actions'] if a['status'] in ('fail','blocked')]
            save_json(out/f'{name}-findings.json',failed)
            item={'template':name,'pages_planned':len(all_paths),'states_attempted':len(paths)*2,
                  'states_checked':sum(x.get('status')=='observed' and not x.get('error') for x in data),
                  'page_errors':sum(bool(x.get('error')) for x in data),
                  'failed_actions':len(failed),'untested_actions':sum(len(x['untested']) for x in data),
                  'source_fresh':stamp==fingerprint(identity,template_inputs),'cli_exit':result.returncode}
            summary.append(item)
            print(json.dumps(item,ensure_ascii=False),flush=True)
        except (RuntimeError,subprocess.TimeoutExpired) as error:
            summary.append({'template':name,'status':'blocked','reason':str(error)[:200]})
        finally:
            subprocess.run([cli,f'-s={session}','close'],cwd=ROOT,capture_output=True,timeout=35)
            save_json(out/'summary.json',summary)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--ids',nargs='+',type=int,default=list(range(1,18)))
    parser.add_argument('--max-pages',type=int,help='Development smoke only; remaining pages stay unverified')
    args=parser.parse_args()
    if any(n<1 or n>17 for n in args.ids):raise ValueError('This adapter only accepts assigned z1-z17')
    run(args.input,args.output,args.ids,args.max_pages)
