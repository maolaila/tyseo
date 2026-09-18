"""CLI 0.1.20 adapter: external cwd, named session, no shell command construction."""
import json
import shutil
import subprocess
from pathlib import Path
from core import ROOT,save_json

EXPECTED_VERSION='0.1.20'
SESSION='tyseo-acceptance'

def cli_executable():
    local=ROOT/'.runtime-cli/node_modules/.bin/playwright-cli.cmd'
    return str(local) if local.is_file() else shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')

def cli_probe(out):
    out=Path(out).resolve()
    if not out.is_relative_to(ROOT/'runs'):raise ValueError('CLI output must stay outside business repository')
    out.mkdir(parents=True,exist_ok=True)
    executable=cli_executable()
    if not executable:return {'status':'blocked','reason':'CLI not installed; no automatic installation'}
    results={}
    for name,args in [('version',['--version']),('help',['--help']),('run-code-help',['--help','run-code'])]:
        r=subprocess.run([executable,*args],cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
        (out/(name+'.log')).write_text(r.stdout+'\n'+r.stderr,encoding='utf-8')
        results[name]={'returncode':r.returncode,'expected_version_seen':EXPECTED_VERSION in r.stdout}
    result={'expected_version':EXPECTED_VERSION,'session':SESSION,'checks':results,
            'status':'pass' if all(x['returncode']==0 for x in results.values()) and results['version']['expected_version_seen'] else 'blocked'}
    save_json(out/'cli-doctor.json',result);return result

def run_code_file(filename,out):
    out=Path(out).resolve();filename=Path(filename).resolve()
    if not filename.is_relative_to(ROOT) or not filename.is_file():raise ValueError('Use an existing external runner file')
    if cli_probe(out)['status']!='pass':raise RuntimeError('CLI 0.1.20 not healthy; upgrade is owned by another task')
    r=subprocess.run([cli_executable(),'-s='+SESSION,'run-code','--filename',str(filename)],cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    log=r.stdout+'\n'+r.stderr;(out/'run-code.log').write_text(log,encoding='utf-8')
    if r.returncode or '### Error' in log:raise RuntimeError('CLI execution failed; inspect persisted log')
    return {'status':'executed','log':str(out/'run-code.log')}
