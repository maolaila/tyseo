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
