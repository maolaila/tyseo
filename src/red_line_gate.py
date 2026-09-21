"""红线门槛（政策 2.5，用户 2026-09-21 定）：所有点击都要成功、不能有 404、本地页面和接口不能 500、手机端菜单必须是抽屉。

对指定模板：
  1. 取每种页面类型的真实样例页，抓出全部站内链接，逐个请求；超时的串行重试（机器忙时的假失败不算数，也不放过）。
  2. 每个失败目标都打开看原因并归类：
       frontend_missing_page  —— TemplateNotFound：这套模板缺页面，前端要补
       frontend_template_error —— 出错位置在 templates/ 里：模板写法问题，前端修
       backend_code           —— 出错位置在 run.py / cache 等 Python 代码里：后端问题
       not_found              —— 404：先怀疑链接地址/参数拼错（前端），登记为后端问题前必须有依据
       timeout                —— 重试后仍超时
     后端问题只有在 config/backend-issues.json 里登记了（查明的原因 + 带图报告 + 已经告诉负责人 Pony 的时间 owner_notified_at）才不拦交付；
     前端原因、没登记的后端问题、没结论的 404、超时，一律拦。
  3. 手机端菜单：每种页面类型的样例页上，390 宽，点汉堡按钮必须是当前页上盖出来的抽屉/浮层
     （scripts/cli-red-line-mobile-nav.js），任何一条不满足都是失败。
  4. 输出 gate.json / gate.md（每套模板通过或不通过及原因）、confirmed.md（可以对主管说"已完全确认"的模板清单）、
     backend-problems.json（给 problem_report.py 出带图报告用）。

不改业务仓库，不启动/重启预览（预览没起来就判 blocked），输出目录必须是 runs/ 下的新目录。
"""
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urldefrag

import requests
from bs4 import BeautifulSoup

from core import ROOT, git, read_json, save_json

OK = (200, 301, 302, 303, 307, 308)


def template_ids(values):
    ids = []
    for value in values:
        number = int(str(value).lower().lstrip('z'))
        if number < 1:
            raise ValueError(f'bad template id: {value}')
        ids.append(number)
    return sorted(set(ids))


def changed_ids(repo, since):
    """这次改动涉及哪些 z 模板：since..HEAD 的提交 + 还没提交的改动。"""
    names = set()
    for args in (['diff', '--name-only', f'{since}..HEAD'], ['diff', '--name-only', 'HEAD'], ['ls-files', '--others', '--exclude-standard']):
        try:
            names.update(git(repo, *args).splitlines())
        except Exception:
            pass
    found = set()
    for name in names:
        match = re.match(r'(?:templates|static)/z(\d+)/', name.replace('\\', '/'))
        if match:
            found.add(int(match.group(1)))
    return sorted(found)


def samples_for(repo, contracts, number, borrow):
    """每种页面类型一个真实样例地址。没有自己的页面契约的模板（如新做的 z18）借用 borrow 那套的样例——后端数据和路由是同一份。"""
    name = f'z{number}'
    source = name if (contracts / name / 'page-contract.json').is_file() else borrow
    contract = read_json(contracts / source / 'page-contract.json')
    samples, missing = defaultdict(list), []
    for page in contract['pages']:
        entry = page['entry_template'].split('/', 1)[1]
        if not (repo / 'templates' / name / entry).is_file():
            if source != name:
                missing.append({'page_type': page['page_type_id'], 'reason': f'templates/{name}/{entry} 不存在（{source} 有这一页）'})
            continue
        sample = next((s['path'] for s in page.get('http_samples', []) if s['status'] == 200), None)
        if sample and not sample.startswith('/play/'):
            samples[sample].append(page['page_type_id'])
    return samples, missing, source


def internal(base, source, href):
    if not href or href == '#' or href.lower().startswith(('javascript:', 'mailto:', 'tel:', 'data:')):
        return None
    target = urljoin(urljoin(base, source), href)
    parts = urlsplit(target)
    if parts.netloc != urlsplit(base).netloc or parts.scheme != 'http':
        return None
    clean = urlsplit(urldefrag(target).url)
    return clean.path + (('?' + clean.query) if clean.query else '')


def status_of(base, path, timeout):
    try:
        response = requests.get(base + path, timeout=timeout, allow_redirects=True, stream=True)
        status, final = response.status_code, urlsplit(response.url).path
        response.close()
        return {'status': status, **({'final': final} if final != urlsplit(base + path).path else {})}
    except requests.RequestException as error:
        return {'status': 'timeout' if 'Timeout' in type(error).__name__ else 'blocked', 'reason': type(error).__name__}


def explain(base, path, repo):
    """打开失败的地址，读 Flask 调试页里的异常和出错位置，判断是谁的问题。"""
    try:
        response = requests.get(base + path, timeout=40)
    except requests.RequestException as error:
        return {'kind': 'timeout', 'detail': type(error).__name__}
    body = response.text
    if response.status_code == 404:
        return {'kind': 'not_found', 'status': 404}
    if response.status_code < 500:
        return {'kind': 'ok_on_retry', 'status': response.status_code}
    title = re.search(r'<h1>(.*?)</h1>', body, re.S)
    message = re.search(r'<p class="errormsg">(.*?)</p>', body, re.S)
    exception = html.unescape(title.group(1).strip()) if title else 'unknown'
    detail = html.unescape(re.sub(r'<[^>]+>', '', message.group(1)).strip())[:240] if message else ''
    frames = []
    for match in re.finditer(r'File &quot;(.*?)&quot;,\s*line\s*(?:<em class="line">)?(\d+)(?:</em>)?,\s*in\s*(?:<code class="function">)?([^<\n]+)', body):
        frames.append({'file': html.unescape(match.group(1)).replace('\\', '/'), 'line': int(match.group(2)), 'function': html.unescape(match.group(3)).strip()})
    root = str(repo).replace('\\', '/').lower()
    own = [f for f in frames if f['file'].lower().startswith(root) and '/.venv/' not in f['file'].lower()]
    last = own[-1] if own else (frames[-1] if frames else None)
    where = f"{last['file'][len(root) + 1:] if last['file'].lower().startswith(root) else last['file']}:{last['line']} in {last['function']}" if last else ''
    if 'TemplateNotFound' in exception or 'TemplateNotFound' in detail:
        kind = 'frontend_missing_page'
    elif last and '/templates/' in last['file'].lower():
        kind = 'frontend_template_error'
    elif last:
        kind = 'backend_code'
    else:
        kind = 'server_error_unknown'
    return {'kind': kind, 'status': response.status_code, 'exception': exception, 'message': detail, 'where': where}


def registered(register, path, info):
    for issue in register:
        if re.search(issue['path'], path) and (not issue.get('exception') or re.search(issue['exception'], f"{info.get('exception', '')} {info.get('message', '')}")):
            return issue
    return None


def audit_links(number, base, samples, repo, register, out):
    pages, targets = [], defaultdict(list)

    def fetch(item):
        path, types = item
        try:
            response = requests.get(base + path, timeout=40)
        except requests.RequestException as error:
            return {'path': path, 'page_types': types, 'status': 'blocked', 'reason': type(error).__name__, 'links': []}
        links = []
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            for node in soup.select('a[href]'):
                target = internal(base, path, node.get('href'))
                if target:
                    links.append({'href': node.get('href'), 'target': target, 'text': node.get_text(' ', strip=True)[:60]})
        return {'path': path, 'page_types': types, 'status': response.status_code, 'links': links}

    with ThreadPoolExecutor(max_workers=4) as pool:
        pages = list(pool.map(fetch, samples.items()))
    for page in pages:
        for link in page['links']:
            targets[link['target']].append({'source': page['path'], 'href': link['href'], 'text': link['text']})
    name = f'z{number}'
    total = len(targets)
    print(f'{name}: {len(pages)} 个样例页，{total} 个站内链接目标，开始逐个请求', flush=True)
    first, done = {}, 0

    def one(path):
        return path, status_of(base, path, 30)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for path, result in pool.map(one, targets):
            first[path] = result
            done += 1
            if done % 150 == 0 or done == total:
                bad = sum(r['status'] not in OK for r in first.values())
                print(f'{name}: 已查 {done}/{total}，暂有 {bad} 个没通过（含待重试的超时）', flush=True)
    # 第一轮超时的（多半是机器忙）并行放宽时间再试一次；仍然超时的如实记为超时，拦交付
    slow = [p for p, r in first.items() if r['status'] in ('timeout', 'blocked')]
    if slow:
        print(f'{name}: {len(slow)} 个超时，放宽到 90 秒再试', flush=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for path, result in zip(slow, pool.map(lambda p: status_of(base, p, 90), slow)):
                first[path] = result
    bad_paths = [p for p, r in first.items() if r['status'] not in OK]
    with ThreadPoolExecutor(max_workers=4) as pool:
        explained = dict(zip(bad_paths, pool.map(lambda p: explain(base, p, repo) if first[p]['status'] not in ('timeout', 'blocked') else {'kind': 'timeout', 'detail': first[p].get('reason', '')}, bad_paths)))
    failures = []
    for path in bad_paths:
        info = explained[path]
        if info['kind'] == 'ok_on_retry':
            continue
        issue = registered(register, path, info) if info['kind'] in ('backend_code', 'not_found', 'server_error_unknown') else None
        blocking = not (issue and issue.get('owner_notified_at'))
        failures.append({'template': name, 'target': path, **info, 'sources': targets[path][:5], 'source_count': len(targets[path]),
                         'registered_issue': issue['id'] if issue else None, 'blocking': blocking})
    print(f"{name}: 链接查完，{len(failures)} 个没通过，其中 {sum(f['blocking'] for f in failures)} 个拦交付", flush=True)
    bad_pages = [{'path': p['path'], 'page_types': p['page_types'], 'status': p['status']} for p in pages if p['status'] != 200]
    save_json(out / 'links.json', {'pages': [{k: v for k, v in p.items() if k != 'links'} | {'links': len(p['links'])} for p in pages],
                                  'targets': len(targets), 'failures': failures, 'bad_sample_pages': bad_pages})
    return {'sample_pages': len(pages), 'link_targets': len(targets), 'failures': failures, 'bad_sample_pages': bad_pages}


def audit_mobile_nav(number, base, samples, cli, out, max_pages):
    name = f'z{number}'
    items = [{'path': path, 'types': types} for path, types in samples.items()]
    skipped = []
    if max_pages and len(items) > max_pages:
        skipped = [x['path'] for x in items[max_pages:]]
        items = items[:max_pages]
    script = (ROOT / 'scripts/cli-red-line-mobile-nav.js').read_text(encoding='utf-8')
    for marker, value in {'__BASE__': base, '__NAME__': name, '__PATHS__': items, '__OUTPUT__': out.relative_to(ROOT).as_posix()}.items():
        script = script.replace(marker, json.dumps(value, ensure_ascii=False))
    generated = out / 'mobile-nav-run-code.js'
    generated.write_text(script, encoding='utf-8')
    session = f'tyseo-redline-{name}-' + hashlib.sha256(str(out).encode()).hexdigest()[:6]
    result = {'results': [], 'error': None}
    try:
        opened = subprocess.run([cli, f'-s={session}', 'open', base + '/'], cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
        if opened.returncode:
            result['error'] = 'playwright-cli open failed'
        else:
            done = subprocess.run([cli, f'-s={session}', 'run-code', '--filename', str(generated)], cwd=ROOT, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=max(600, len(items) * 40))
            (out / 'mobile-nav-cli-output.txt').write_text(done.stdout + done.stderr, encoding='utf-8')
            match = re.search(r'### Result\s*\n(.*?)\n### Ran', done.stdout, re.S)
            if done.returncode == 0 and match:
                result = {**json.loads(match.group(1)), 'error': None}
            else:
                result['error'] = f'run-code failed (exit {done.returncode})'
    except (subprocess.TimeoutExpired, ValueError) as error:
        result['error'] = str(error)[:200]
    finally:
        subprocess.run([cli, f'-s={session}', 'close'], cwd=ROOT, capture_output=True, timeout=60)
    result['skipped_pages'] = skipped
    save_json(out / 'mobile-nav.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ids', nargs='*', default=[], help='模板编号，如 1 2 z10 18')
    parser.add_argument('--changed-since', help='只查这个提交之后改动过的 z 模板（加上未提交的改动）；给执行器的 verify 用')
    parser.add_argument('--output', required=True)
    parser.add_argument('--contract-run', default='runs/z-v2-recheck-20260919/contracts')
    parser.add_argument('--borrow', default='z1', help='没有页面契约的模板借用哪一套的样例地址')
    parser.add_argument('--skip-browser', action='store_true', help='只查链接，不查手机端菜单（开发试跑用；结果不能算通过）')
    parser.add_argument('--skip-links', action='store_true', help='只查手机端菜单，不查链接（开发试跑用；结果不能算通过）')
    parser.add_argument('--max-pages', type=int, default=0, help='手机端菜单最多查多少个样例页（开发试跑用；没查的页记为未覆盖，不能算通过）')
    args = parser.parse_args()

    repo = Path(read_json(ROOT / 'tasks/bootstrap.json')['repo_root'])
    ids = template_ids(args.ids)
    if args.changed_since:
        ids = sorted(set(ids) | set(changed_ids(repo, args.changed_since)))
    # {now} 换成当前时间，方便从别的程序（机器人的执行器）固定写一条命令
    output = (ROOT / args.output.replace('{now}', datetime.now().strftime('%Y%m%d-%H%M%S'))).resolve()
    if not output.is_relative_to(ROOT / 'runs') or output.exists():
        raise SystemExit('输出目录必须是 runs/ 下还不存在的新目录')
    output.mkdir(parents=True)
    if not ids:
        save_json(output / 'gate.json', {'status': 'pass', 'note': '这次改动不涉及任何 z 模板', 'templates': []})
        print('这次改动不涉及 z 模板，门槛不适用。')
        return 0
    contracts = (ROOT / args.contract_run).resolve()
    register_file = ROOT / 'config/backend-issues.json'
    register = read_json(register_file)['issues'] if register_file.is_file() else []
    cli = shutil.which('playwright-cli.cmd') or shutil.which('playwright-cli')
    if not cli and not args.skip_browser:
        raise SystemExit('需要 playwright-cli 0.1.20')

    gate = {'policy': '2.5', 'started_at': datetime.now(timezone.utc).isoformat(), 'commit': git(repo, 'rev-parse', 'HEAD'),
            'dirty': bool(git(repo, 'status', '--porcelain').strip()), 'templates': []}
    for number in ids:
        name, base = f'z{number}', f'http://127.0.0.1:{6300 + number}'
        out = output / name
        out.mkdir()
        entry = {'template': name, 'base': base, 'status': 'fail', 'reasons': []}
        try:
            home = requests.get(base + '/', timeout=60)
            alive, body = home.status_code, home.text[:20000]
        except requests.RequestException:
            alive, body = None, ''
        if alive != 200:
            # 连不上远端的测试 Redis / Mongo：是本机网络（IP 白名单）的问题，不是模板的问题，也不能算验过
            env = re.search(r'redis\.exceptions\.\w+|pymongo\.errors\.\w+|ServerSelectionTimeoutError', body)
            why = f'本机连不上测试数据库（{env.group(0)}），多半是公网 IP 变了、不在白名单里——环境问题，不是模板问题' if env else f'本地预览 {base} 没起来（首页返回 {alive}）'
            entry.update(status='blocked', reasons=[f'{why}，没法验'])
            gate['templates'].append(entry)
            print(f'{name}: 没法验——{why}', flush=True)
            continue
        samples, missing, source = samples_for(repo, contracts, number, args.borrow)
        entry['sample_source'] = source
        if args.skip_links:
            links = {'sample_pages': len(samples), 'link_targets': 0, 'failures': [], 'bad_sample_pages': []}
            entry['reasons'].append('没查链接（--skip-links），不能算通过')
        else:
            links = audit_links(number, base, samples, repo, register, out)
        entry['links'] = {k: links[k] for k in ('sample_pages', 'link_targets')} | {'failed': len(links['failures']), 'blocking': sum(f['blocking'] for f in links['failures'])}
        kinds = defaultdict(int)
        for failure in links['failures']:
            if failure['blocking']:
                kinds[failure['kind']] += 1
        label = {'frontend_missing_page': '缺模板页（前端要补）', 'frontend_template_error': '模板写法出错（前端要修）', 'backend_code': '后端代码报错但还没登记、没告诉负责人',
                 'not_found': '404 还没有结论（先查是不是链接地址/参数拼错）', 'timeout': '重试后仍然超时', 'server_error_unknown': '500 但读不出原因'}
        for kind, count in kinds.items():
            entry['reasons'].append(f'{label.get(kind, kind)}：{count} 个链接目标')
        if missing:
            entry['reasons'].append(f'缺 {len(missing)} 种页面：' + '、'.join(m['page_type'] for m in missing[:8]))
            entry['missing_pages'] = missing
        if links['bad_sample_pages']:
            entry['reasons'].append(f"{len(links['bad_sample_pages'])} 个样例页本身打不开")
        if args.skip_browser:
            entry['reasons'].append('没查手机端菜单（--skip-browser），不能算通过')
        else:
            nav = audit_mobile_nav(number, base, samples, cli, out, args.max_pages)
            failed = [r for r in nav.get('results', []) if r['status'] != 'pass']
            entry['mobile_nav'] = {'pages': len(nav.get('results', [])), 'failed': len(failed), 'error': nav.get('error'), 'skipped': len(nav.get('skipped_pages', []))}
            if nav.get('error'):
                entry['reasons'].append(f"手机端菜单没验成：{nav['error']}")
            grouped = defaultdict(list)
            for r in failed:
                grouped['；'.join(r['reasons'])[:90]].append(r['path'])
            for reason, paths in grouped.items():
                entry['reasons'].append(f'手机端菜单不合格（{len(paths)} 个页面，如 {paths[0]}）：{reason}')
            if nav.get('skipped_pages'):
                entry['reasons'].append(f"手机端菜单有 {len(nav['skipped_pages'])} 个页面没查（--max-pages），不能算通过")
        entry['status'] = 'pass' if not entry['reasons'] else 'fail'
        entry['backend_waived'] = [{'target': f['target'], 'issue': f['registered_issue']} for f in links['failures'] if not f['blocking']][:50]
        gate['templates'].append(entry)
        print(f"{name}: {'通过' if entry['status'] == 'pass' else '不通过'} {'；'.join(entry['reasons'])[:200]}", flush=True)

    gate['finished_at'] = datetime.now(timezone.utc).isoformat()
    gate['status'] = 'pass' if all(t['status'] == 'pass' for t in gate['templates']) else 'fail'
    save_json(output / 'gate.json', gate)
    problems = []
    for t in gate['templates']:
        file = output / t['template'] / 'links.json'
        if file.is_file():
            problems += [f for f in read_json(file)['failures'] if f['kind'] in ('backend_code', 'server_error_unknown', 'not_found', 'timeout')]
    save_json(output / 'backend-problems.json', problems)
    lines = ['# 红线门槛结果（政策 2.5）', '', f"业务仓库提交 {gate['commit'][:9]}{'（有未提交改动）' if gate['dirty'] else ''}；结论只对这一刻的代码有效，改了要重跑。", '']
    for t in gate['templates']:
        lines.append(f"- **{t['template']}**：{'通过' if t['status'] == 'pass' else '不通过' if t['status'] == 'fail' else '没法验'}"
                     + (f"（查了 {t['links']['sample_pages']} 个样例页、{t['links']['link_targets']} 个链接目标" + (f"、{t['mobile_nav']['pages']} 个页面的手机菜单" if t.get('mobile_nav') else '') + '）' if t.get('links') else ''))
        lines += [f'  - {r}' for r in t['reasons']]
        if t.get('backend_waived'):
            lines.append(f"  - 已登记并告诉负责人的后端问题：{len(t['backend_waived'])} 个链接目标（不拦交付，但页面上仍然点不通，等后端修）")
    (output / 'gate.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    confirmed = [t['template'] for t in gate['templates'] if t['status'] == 'pass']
    (output / 'confirmed.md').write_text('# 可以说"已完全确认"的模板\n\n' + ('、'.join(confirmed) if confirmed else '（没有）') +
                                         '\n\n只包含红线门槛全部通过的模板；排版、双主题、SEO 等其余验收项另见各自的证据。\n', encoding='utf-8')
    print(f"门槛{'通过' if gate['status'] == 'pass' else '不通过'}：" + '、'.join(f"{t['template']}={'过' if t['status'] == 'pass' else '不过'}" for t in gate['templates']))
    return 0 if gate['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
