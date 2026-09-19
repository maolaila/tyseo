"""Bounded real-page and in-site link audit for existing z templates."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag

import requests
from bs4 import BeautifulSoup

from acceptance import collect_http
from core import ROOT, fingerprint, git, read_json, save_json
from z_manual_preview import existing_pages


def local_path(base, source, href):
    if href is None:
        return None, 'no_href'
    if href == '#':
        return None, 'placeholder_fragment'
    if not href or href.lower().startswith(('javascript:', 'mailto:', 'tel:', 'data:')):
        return None, 'non_http'
    target = urljoin(urljoin(base, source), href)
    if urlsplit(target).netloc != urlsplit(base).netloc or urlsplit(target).scheme != 'http':
        return None, 'external'
    return urlsplit(urldefrag(target).url).path + (('?' + urlsplit(target).query) if urlsplit(target).query else ''), 'local'


def link_head(base, path):
    url = base + path
    try:
        response = requests.head(url, timeout=12, allow_redirects=False)
        if response.status_code == 405:
            response = requests.get(url, timeout=12, allow_redirects=False, stream=True)
        status = response.status_code
        location = response.headers.get('Location') if 300 <= status < 400 else None
        response.close()
        if location:
            redirect, kind = local_path(base, path, location)
            if kind == 'local' and redirect != path:
                next_response = requests.head(base + redirect, timeout=12, allow_redirects=False)
                next_status = next_response.status_code
                next_response.close()
                return {'status': status, 'redirect': redirect, 'destination_status': next_status}
            return {'status': status, 'redirect': location, 'destination_status': 'external_or_cycle'}
        return {'status': status}
    except requests.RequestException as error:
        return {'status': 'blocked', 'reason': type(error).__name__}


def run(ids, contract_run, output):
    output = (ROOT / output).resolve()
    contracts = (ROOT / contract_run).resolve()
    if not output.is_relative_to(ROOT / 'runs') or output.exists() or not contracts.is_relative_to(ROOT / 'runs'):
        raise ValueError('Use new output and existing contracts under external runs/')
    output.mkdir(parents=True)
    repo = Path(read_json(ROOT / 'tasks/bootstrap.json')['repo_root'])
    inputs = [Path(__file__), ROOT/'config/acceptance-policy.json',
              *(p for number in ids for p in (repo/'templates'/f'z{number}').rglob('*.html')),
              *(p for number in ids for p in (repo/'static'/f'z{number}').rglob('*') if p.is_file())]
    identity = {'commit':git(repo,'rev-parse','HEAD'),'ids':ids,'policy':'2.3'}
    before = fingerprint(identity, inputs)
    samples = defaultdict(list)
    blocked = []
    for number in ids:
        name = f'z{number}'
        contract = read_json(contracts / name / 'page-contract.json')
        for page in existing_pages(repo, name, contract):
            sample = next((s['path'] for s in page.get('http_samples', []) if s['status'] == 200), None)
            if sample:
                samples[(name, sample)].append(page['page_type_id'])
            else:
                blocked.append({'template': name, 'page_type': page['page_type_id'], 'reason': 'no HTTP 200 sample'})
    documents = []
    def fetch(item):
        (name, path), page_types = item
        base = f'http://127.0.0.1:{6300 + int(name[1:])}'
        stem = hashlib.sha256(path.encode()).hexdigest()[:16]
        folder = output / 'http' / name / stem
        meta = collect_http(base + path, folder)
        html = (folder / 'http-body.html').read_text(encoding='utf-8', errors='replace') if meta['status'] == 200 else ''
        soup = BeautifulSoup(html, 'html.parser') if html else None
        links = []
        controls = []
        if soup:
            for node in soup.select('a'):
                href = node.get('href')
                target, kind = local_path(base, path, href)
                if href and href.startswith('#') and href != '#' and not soup.find(id=href[1:]):
                    kind = 'missing_fragment'
                links.append({'href': href, 'target': target, 'kind': kind,
                              'text': node.get_text(' ', strip=True)[:80], 'target_window': node.get('target')})
            for node in soup.select('button,select,input[type=radio],input[type=checkbox],[role=tab]'):
                controls.append({'tag': node.name, 'type': node.get('type'), 'id': node.get('id'),
                                 'classes': node.get('class', []), 'role': node.get('role'),
                                 'name': node.get('name'), 'data': {key: value for key,value in node.attrs.items() if key.startswith('data-')},
                                 'text': node.get_text(' ', strip=True)[:60]})
        return {'template': name, 'path': path, 'page_types': page_types,
                'status': meta['status'], 'headers': meta['headers'],
                'evidence_path': str((folder / 'http-response.json').relative_to(output)).replace('\\','/'),
                'links': links, 'controls': controls}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(fetch, item) for item in samples.items()]
        for future in as_completed(futures):
            try: documents.append(future.result())
            except Exception as error: blocked.append({'reason': type(error).__name__, 'detail': str(error)[:180]})
    save_json(output / 'pages.json', documents)
    targets = defaultdict(list)
    for doc in documents:
        for link in doc['links']:
            if link['kind'] == 'local':
                targets[(doc['template'], link['target'])].append({'source': doc['path'], 'page_types': doc['page_types'], 'text': link['text']})
            elif link['kind'] in ('missing_fragment','placeholder_fragment','no_href'):
                blocked.append({'rule_id':'LINK-NAVIGATION','template':doc['template'],
                                'source':doc['path'],'href':link['href'],'text':link['text'],
                                'reason':link['kind'],'status':'needs_review',
                                'evidence_path':doc['evidence_path']})
    def check(item):
        (name, path), sources = item
        return {'template': name, 'path': path, **link_head(f'http://127.0.0.1:{6300 + int(name[1:])}', path), 'sources': sources[:6], 'source_count': len(sources)}
    checks = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = [pool.submit(check, item) for item in targets.items()]
        for future in as_completed(futures): checks.append(future.result())
    save_json(output / 'links.json', checks)
    failures = [x for x in checks if x['status'] not in (200, 301, 302, 303, 307, 308) or
                isinstance(x.get('destination_status'), int) and x['destination_status'] >= 400]
    unverified = [x for x in checks if x.get('destination_status') == 'external_or_cycle']
    save_json(output / 'findings.json', [dict(x,rule_id='LINK-NAVIGATION',
        expected='Reachable internal link destination',actual=x['status'],
        severity='P1',owner_layer='unknown: template or backend',
        evidence_paths=['links.json']) for x in failures])
    save_json(output / 'unverified.json', unverified)
    summary = {'finished_at': datetime.now(timezone.utc).isoformat(), 'commit': git(repo, 'rev-parse', 'HEAD'),
               'input_hash':before,'source_fresh':before==fingerprint(identity,inputs),
               'ids': ids, 'existing_page_samples': sum(map(len, samples.values())), 'unique_documents':len(samples),
               'current_http_200':sum(x['status']==200 for x in documents), 'link_targets':len(checks),
               'statuses':dict(Counter(str(x['status']) for x in checks)), 'failed_link_targets':len(failures),
               'unverified_redirects':len(unverified),
               'blocked_page_samples':len(blocked), 'other_findings':blocked,
               'scope': 'Observed internal hrefs from current successful server responses; no external target checks or browser clicks'}
    save_json(output / 'summary.json', summary)
    print(json.dumps({key: summary[key] for key in ('existing_page_samples','unique_documents','current_http_200','link_targets','statuses','failed_link_targets','blocked_page_samples')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='+', type=int, default=list(range(1,18)))
    parser.add_argument('--contract-run', default='runs/z-v2-recheck-20260919/contracts')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if any(i < 1 or i > 17 for i in args.ids): raise ValueError('Only confirmed z1..z17')
    run(args.ids, args.contract_run, args.output)
