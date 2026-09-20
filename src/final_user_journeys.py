"""Real-app, reusable common journeys plus template-owned component cases."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core import ROOT, fingerprint, git, read_json, save_json
from z_manual_preview import existing_pages


def run_one(name, output, cli, repo, contract_root, cases, base):
    out = output / name
    out.mkdir(parents=True, exist_ok=True)
    contract = read_json(contract_root / name / 'page-contract.json')
    pages = existing_pages(repo, name, contract)
    candidates = {}
    missing = []
    excluded_shared = []
    for page in pages:
        sample = next((s['path'] for s in page.get('http_samples', []) if s['status'] == 200), None)
        if sample:
            if sample.startswith('/play/'):
                excluded_shared.append({'page_type':page['page_type_id'], 'path':sample,
                                        'reason':'shared playback route outside assigned template'})
            else:
                candidates.setdefault(sample, []).append(page['page_type_id'])
        else:
            missing.append(page['page_type_id'])

    inputs = [Path(__file__), ROOT/'scripts/cli-final-user-journeys.js', ROOT/'scripts/layout-audit.js',
              ROOT/'config/final-user-cases.json', ROOT/'config/acceptance-policy.json',
              contract_root/name/'page-contract.json', repo/'run.py', repo/'config.py', repo/'.env',
              repo/'static/js/jquery.min.js', repo/'static/js/ajs.js',
              *(repo/'templates'/name).rglob('*.html'),
              *(p for p in (repo/'static'/name).rglob('*') if p.is_file())]
    identity = {'template': name, 'base_url': base, 'commit': git(repo, 'rev-parse', 'HEAD'),
                'cli': '0.1.20', 'cases': cases['version']}
    before = fingerprint(identity, inputs)

    def fetch(item):
        path, types = item
        try:
            response = requests.get(base+path, timeout=20)
            html = response.content if response.status_code == 200 else b''
            soup = BeautifulSoup(html, 'html.parser') if html else None
            raw = {'path': path, 'page_types': types, 'status': response.status_code,
                   'body_sha256': hashlib.sha256(response.content).hexdigest(),
                   'title': soup.title.get_text(' ', strip=True)[:140] if soup and soup.title else None,
                   'main_chars': len(soup.select_one('main').get_text(' ', strip=True)) if soup and soup.select_one('main') else None,
                   'hrefs': len(soup.select('a[href]')) if soup else 0}
            if html and b'Werkzeug Debugger' not in html:
                (out / 'http' / hashlib.sha256(path.encode()).hexdigest()[:16]).with_suffix('.html').write_bytes(html)
            return raw
        except requests.RequestException as error:
            return {'path': path, 'page_types': types, 'status': 'blocked', 'error': type(error).__name__}

    (out/'http').mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=6) as pool:
        raw = list(pool.map(fetch, candidates.items()))
    save_json(out/'http-pages.json', raw)
    valid = [{'path': x['path'], 'types': x['page_types']} for x in raw if x['status'] == 200]
    if not valid or '/' not in {x['path'] for x in valid}:
        result = {'pages': [], 'common': [], 'specific': [], 'error': 'No usable homepage sample'}
    else:
        script = (ROOT/'scripts/cli-final-user-journeys.js').read_text(encoding='utf-8')
        for marker, value in {'__BASE__':base, '__NAME__':name, '__PATHS__':valid,
                              '__SPEC__':cases['specific'][name], '__OUTPUT__':out.relative_to(ROOT).as_posix()}.items():
            script = script.replace(marker, json.dumps(value, ensure_ascii=False))
        script = script.replace('__LAYOUT_AUDIT__', (ROOT/'scripts/layout-audit.js').read_text(encoding='utf-8').strip())
        generated = out/'run-code.js'
        generated.write_text(script, encoding='utf-8')
        session = 'tyseo-final-'+name+'-'+hashlib.sha256(str(out).encode()).hexdigest()[:6]
        try:
            opened = subprocess.run([cli, f'-s={session}', 'open', base+'/'], cwd=ROOT, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=45)
            if opened.returncode:
                result = {'pages': [], 'common': [], 'specific': [], 'error': 'CLI open failed'}
            else:
                completed = subprocess.run([cli, f'-s={session}', 'run-code', '--filename', str(generated)],
                                           cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=900)
                (out/'cli-output.txt').write_text(completed.stdout+completed.stderr, encoding='utf-8')
                match = re.search(r'### Result\s*\n(.*?)\n### Ran', completed.stdout, re.S)
                result = json.loads(match.group(1)) if completed.returncode == 0 and match else {
                    'pages': [], 'common': [], 'specific': [], 'error': 'CLI run failed or result unavailable', 'cli_exit': completed.returncode}
        except (subprocess.TimeoutExpired, ValueError) as error:
            result = {'pages': [], 'common': [], 'specific': [], 'error': str(error)[:180]}
        finally:
            subprocess.run([cli, f'-s={session}', 'close'], cwd=ROOT, capture_output=True, timeout=45)
    save_json(out/'browser.json', result)
    counts = Counter(x.get('status') for x in [*result.get('pages', []), *result.get('common', []), *result.get('specific', [])])
    source_fresh = before == fingerprint(identity, inputs)
    summary = {'template': name, 'source_commit': identity['commit'], 'source_hash': before, 'source_fresh': source_fresh,
               'real_app': True, 'preview_base_url': base, 'existing_pages': len(pages), 'sampled_page_types': sum(map(len, candidates.values())),
               'unique_sample_urls': len(candidates), 'raw_http_200': sum(x['status'] == 200 for x in raw),
               'raw_not_200': [x['path'] for x in raw if x['status'] != 200], 'missing_page_samples': missing,
               'excluded_shared_routes': excluded_shared,
               'browser_page_states': len(result.get('pages', [])), 'common_cases': len(result.get('common', [])),
               'specific_cases': len(result.get('specific', [])), 'counts': dict(counts), 'error': result.get('error'),
               'status': 'fail' if counts['fail'] else 'blocked' if result.get('error') or counts['blocked'] or missing or any(x['status'] != 200 for x in raw) else
                         'needs_review' if counts['needs_review'] else 'automated_pass'}
    save_json(out/'summary.json', summary)
    findings = []
    for category in ('pages', 'common', 'specific'):
        for item in result.get(category, []):
            if item.get('status') in ('fail', 'blocked', 'needs_review'):
                findings.append({'rule_id': item.get('rule_id', 'PAGE-SMOKE'), 'page': item.get('path'),
                                 'viewport': item.get('width'), 'theme': item.get('theme'), 'status': item['status'],
                                 'expected': 'usable page or documented action effect', 'actual': item.get('actual', item),
                                 'severity': 'P1' if item['status'] == 'fail' else 'unknown',
                                 'owner_layer': 'template_or_backend_needs_triage', 'evidence_path': 'browser.json'})
    save_json(out/'findings.json', findings)
    print(json.dumps({k:summary[k] for k in ('template','status','raw_http_200','browser_page_states','common_cases','specific_cases','counts')}, ensure_ascii=False), flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--output', required=True)
    parser.add_argument('--contracts', default='runs/z-v2-recheck-20260919/contracts')
    parser.add_argument('--base-url-pattern', default='http://127.0.0.1:{port}')
    args=parser.parse_args()
    output=(ROOT/args.output).resolve();contracts=(ROOT/args.contracts).resolve()
    if not output.is_relative_to(ROOT/'runs') or output.exists() or not contracts.is_relative_to(ROOT/'runs'):
        raise ValueError('Use a new runs/ output and existing contract directory')
    output.mkdir(parents=True)
    cli=shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')
    if not cli or subprocess.check_output([cli,'--version'], text=True).strip()!='0.1.20':
        raise RuntimeError('playwright-cli 0.1.20 required')
    repo=Path(read_json(ROOT/'tasks/bootstrap.json')['repo_root'])
    cases=read_json(ROOT/'config/final-user-cases.json')
    names=args.ids or sorted(cases['specific'], key=lambda x:int(re.search(r'\d+$',x).group()))
    if any(name not in cases['specific'] or not re.fullmatch(r'[a-z]+\d+',name) for name in names):
        raise ValueError('Each template must be explicitly registered in final-user-cases.json')
    summaries=[]
    for name in names:
        number=int(re.search(r'\d+$',name).group())
        base=args.base_url_pattern.format(template=name,number=number,port=6300+number).rstrip('/')
        summaries.append(run_one(name, output, cli, repo, contracts, cases, base))
        save_json(output/'progress.json', summaries)
    save_json(output/'summary.json', {'templates': summaries, 'status_counts': dict(Counter(x['status'] for x in summaries)),
                                      'purpose': 'Local automated evidence; human acceptance remains separate'})


if __name__=='__main__': main()
