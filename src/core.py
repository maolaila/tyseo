"""Local-only task, path, provenance and evidence gates."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import re
import uuid
import time
from concurrent.futures import ThreadPoolExecutor
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
DISABLED = ('remote_writes_enabled', 'deployment_enabled', 'site_tdk_generation_enabled',
            'domain_workflow_mutation_enabled', 'indexnow_enabled', 'scheduler_enabled')

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    for attempt in range(8):
        try:
            os.replace(temp,path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (attempt + 1))

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args]).decode('utf-8', 'replace').strip()

def resolve_repo_root(explicit=None):
    """预览服务跑的是哪个检出，证据就该记哪个。

    以前这里写死读 tasks/bootstrap.json 的 repo_root，于是在 worktree 里改代码、
    用 worktree 起预览时，落盘的 commit / dirty / input_hash 全是主检出的，
    等于给错代码盖了章。优先级：显式参数 > 环境变量 PONY_REPO_ROOT > bootstrap.json。
    """
    local = ROOT / 'tasks/local.json'
    fallback = local if local.is_file() else ROOT / 'tasks/bootstrap.json'
    raw = explicit or os.environ.get('PONY_REPO_ROOT') or read_json(fallback)['repo_root']
    repo = Path(raw).resolve()
    if not (repo / 'run.py').is_file():
        raise ValueError(f'{repo} 不像业务检出：里面没有 run.py')
    return repo

def repo_provenance(repo):
    """证据里要能看出测的是哪个检出、哪个分支、干不干净。"""
    return {'repo_root': str(repo),
            'commit': git(repo, 'rev-parse', 'HEAD'),
            'branch': git(repo, 'branch', '--show-current') or '(detached HEAD)',
            'dirty': bool(git(repo, 'status', '--porcelain').strip())}

def preview_source_check(repo, name, base, timeout=30):
    """核对"预览真正跑的检出"是不是 repo_root。

    对不上就说明测的检出和记的检出不是同一个（最常见是在 worktree 里改代码、
    用 worktree 起预览，工具却在给主检出盖章）。返回 (ok, 说明)，
    调用方据此判 blocked，不让盖错章的证据悄悄变成 pass。

    两道校验：
    1) 该模板 static 下所有 css/js 与磁盘逐字节比对——静态资源改了就能发现；
    2) 磁盘上 master.html 里写的静态资源引用（含 ?v= 版本号）必须原样出现在
       预览返回的首页 HTML 里——这把"服务端用的模板"也绑上了，
       光比静态文件抓不到只改模板的情况。
    """
    import urllib.request
    import urllib.error

    def fetch(url, binary=True):
        with urllib.request.urlopen(url, timeout=timeout) as response:
            raw = response.read()
        return raw if binary else raw.decode('utf-8', 'replace')

    static_dir = repo / 'static' / name
    if not static_dir.is_dir() and not (repo / 'templates' / name).is_dir():
        # repo_root 里压根没有这套模板：多半是 --repo-root / PONY_REPO_ROOT 指错了检出。
        # 这种情况不能当"没东西可比，跳过"，否则会静悄悄地查 0 个页面。
        return False, (f'{repo} 里没有 templates/{name} 或 static/{name}：'
                       f'repo_root 指错了检出，用 --repo-root 或 PONY_REPO_ROOT 指到预览实际使用的目录')
    assets = sorted(p for p in static_dir.rglob('*') if p.is_file() and p.suffix.lower() in ('.css', '.js'))
    checked = 0
    for asset in assets:
        url = f"{base}/static/{name}/{asset.relative_to(static_dir).as_posix()}"
        try:
            served = fetch(url)
        except (urllib.error.URLError, OSError) as error:
            return False, f'取不到预览的 {url}：{error}'
        if hashlib.sha256(served).hexdigest() != digest(asset):
            return False, (f'预览 {base} 提供的 {url} 与 {repo} 里的同名文件不一致：'
                           f'预览跑的不是这个检出，证据会盖错提交号。'
                           f'用 --repo-root 或 PONY_REPO_ROOT 指到预览实际使用的目录再跑')
        checked += 1

    master = repo / 'templates' / name / 'master.html'
    refs = []
    if master.is_file():
        pattern = re.escape(f'/static/{name}/') + r'[^"\'\s>]+'
        refs = sorted(set(re.findall(pattern, master.read_text(encoding='utf-8'))))
    if refs:
        try:
            home = fetch(f'{base}/', binary=False)
        except (urllib.error.URLError, OSError) as error:
            return False, f'取不到预览首页 {base}/：{error}'
        missing = [ref for ref in refs if ref not in home]
        if missing:
            return False, (f'{repo} 的 {name}/master.html 里写着 {missing[0]}，'
                           f'但预览 {base} 返回的首页里没有：服务端用的模板不是这个检出的，'
                           f'证据会盖错提交号。用 --repo-root 或 PONY_REPO_ROOT 指到预览实际使用的目录再跑')
    if not checked and not refs:
        return True, f'{name} 没有可比对的静态资源或母版引用，跳过来源校验'
    return True, f'来源已核对：{checked} 个 css/js 与磁盘一致，母版 {len(refs)} 处静态引用在预览首页里都能对上'

def inside(child, parent):
    return Path(child).resolve().is_relative_to(Path(parent).resolve())

def validate_task(path):
    task = read_json(path)
    Draft202012Validator(read_json(ROOT/'schemas/task.schema.json'), format_checker=FormatChecker()).validate(task)
    repo, external = Path(task['repo_root']).resolve(), Path(task['workflow_root']).resolve()
    if not (repo/'.git').exists() or not (repo/'run.py').is_file():
        raise ValueError('Existing business checkout required; do not create a substitute')
    if inside(external, repo) or inside(repo, external):
        raise ValueError('External workspace must be separate, not parent/child of business repository')
    if external != ROOT:
        raise ValueError('workflow_root must identify this tool checkout')
    if task['target_template_id'] == task['reference_template_id'] and task['mode'] != 'verify-template':
        raise ValueError('Reference template is read-only in this workflow')
    return task

def safe_business_path(task, relative, allocation=None):
    """Fail closed, including traversal, ADS, symlink and junction ancestors."""
    target = task.get('target_template_id')
    if task['mode'] not in ('new-template', 'repair-template') or not target or not task['target_id_confirmed']:
        raise ValueError('No confirmed writable template id')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', target):
        raise ValueError('Invalid id')
    if target.lower() == task['reference_template_id'].lower():
        raise ValueError('Reference is protected')
    if not allocation or allocation.get('template_id') != target or not allocation.get('source'):
        raise ValueError('Team allocation evidence required separately from boolean')
    parts = relative.replace('\\', '/').split('/')
    if len(parts) < 3 or parts[0] not in ('templates', 'static') or parts[1] != target:
        raise ValueError('Outside exact target directories')
    if any(p in ('', '.', '..') or ':' in p or p.endswith((' ', '.')) for p in parts):
        raise ValueError('Unsafe path segment')
    if Path(parts[-1]).suffix.lower() not in ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.ico', '.gif', '.woff', '.woff2'):
        raise ValueError('Disallowed production artifact type')
    repo = Path(task['repo_root']).resolve()
    path = repo.joinpath(*parts)
    for parent in [path, *path.parents]:
        if parent == repo:
            break
        if parent.is_symlink() or (parent.exists() and getattr(parent.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Reparse point or symbolic link in write path')
    if not inside(path, repo/parts[0]/target):
        raise ValueError('Resolved path escaped target')
    if task['mode'] == 'new-template' and any((repo/k/target).exists() for k in ('templates', 'static')):
        raise ValueError('Template id already occupied; never overwrite')
    return path

def baseline(repo):
    repo = Path(repo)
    names = set(git(repo, 'ls-files', '-z').split('\0'))
    names.update(git(repo, 'ls-files', '--others', '--exclude-standard', '-z').split('\0'))
    names.update(p.relative_to(repo).as_posix() for p in (repo/'.local-records/domains').rglob('*') if p.is_file())
    names.update(['.env', 'AGENTS.md', 'LOCAL_MAINTENANCE.md', '.git/info/exclude'])
    def hash_one(n):
        return (n,digest(repo/n)) if n and (repo/n).is_file() else None
    with ThreadPoolExecutor(max_workers=8) as pool:
        files=dict(x for x in pool.map(hash_one,sorted(names)) if x)
    return {'commit': git(repo, 'rev-parse', 'HEAD'), 'branch': git(repo, 'branch', '--show-current'),
            'status': git(repo, 'status', '--porcelain=v1'),
            'files': files}

def compare_baseline(before, after):
    a, b = before['files'], after['files']
    changed = [k for k in sorted(a.keys() | b.keys()) if a.get(k) != b.get(k)]
    return {'status': 'pass' if not changed and before['commit']==after['commit'] and before['status']==after['status'] else 'fail',
            'changed_files': changed, 'git_status_before': before['status'], 'git_status_after': after['status']}

def fingerprint(task, files):
    return hashlib.sha256(json.dumps({'task': task, 'files': {str(p):digest(p) for p in sorted(map(Path, files))}}, sort_keys=True).encode()).hexdigest()

def resume_valid(checkpoint, current_hash):
    return checkpoint.get('input_hash') == current_hash

def validate_result(result, run):
    if result.get('status') not in ('pass','fail','blocked','needs_review','not_applicable'):
        raise ValueError('Unknown status')
    if result.get('environment') not in ('real_app','fixture'):
        raise ValueError('Explicit environment required')
    if result['status'] == 'not_applicable' and not result.get('reason'):
        raise ValueError('N/A needs rationale')
    if result['status'] == 'pass':
        evidence=result.get('evidence_paths', [])
        if not evidence or any(not inside(Path(run)/p, run) or not (Path(run)/p).is_file() for p in evidence):
            raise ValueError('PASS requires existing evidence within run')
    if result.get('claims_real_app') and result['environment']!='real_app':
        raise ValueError('Fixture cannot claim real-app success')

def allowed_action(action):
    return action in ('read_source','get_local_page','write_external','capture_screenshot','run_checks')
