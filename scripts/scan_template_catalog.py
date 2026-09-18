"""Read-only source catalog; signals are candidates, never runtime acceptance."""
import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ID = re.compile(r"[a-z]+\d+$")
TEXT = {'.html', '.htm', '.css', '.js', '.svg', '.json', '.md'}
SIGNALS = {
    'tdk': r'website_config\.(?:Title|Description|Keyword)',
    'canonical': r'rel\s*=\s*[\"\']canonical[\"\']',
    'json_ld': r'application/ld\+json',
    'header_dynamic': r'website_config\.HeaderJS',
    'footer_dynamic': r'website_config\.FooterJS',
    'jquery': r'/static/js/jquery\.min\.js',
    'app_download': r'/static/js/ajs\.js',
    'search': r'/search(?:\?|[\"\'])',
    'theme': r'data-theme|prefers-color-scheme|theme-toggle|dark-mode',
    'responsive': r'@media|name=[\"\']viewport',
    'back_top': r'back.?to.?top|scrollTo\(|goto.?top|回到顶部|返回顶部',
    'mobile_nav': r'drawer|hamburger|mobile-menu|mobile-nav|popover',
}


def order(value):
    m = re.fullmatch(r'([a-z]+)(\d+)', value)
    return (m[1], int(m[2]), value) if m else (value, -1, value)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=True, encoding='utf-8').strip()


def analyze(repo, name):
    files = []
    texts = {}
    for base in ('templates', 'static'):
        directory = repo / base / name
        for p in sorted(directory.rglob('*')):
            if not p.is_file() or p.is_symlink():
                continue
            data = p.read_bytes()
            rel = p.relative_to(repo).as_posix()
            files.append({'path': rel, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            if p.suffix.lower() in TEXT:
                texts[rel] = data.decode('utf-8-sig', errors='replace')
    pages = [p for p in texts if p.startswith('templates/') and p.endswith(('.html', '.htm'))]
    evidence = {}
    for signal, pattern in SIGNALS.items():
        hits = []
        for path, raw in texts.items():
            match = re.search(pattern, raw, re.I)
            if match:
                hits.append({'path': path, 'line': raw.count('\n', 0, match.start()) + 1})
        evidence[signal] = hits
    references = []
    components = []
    for path in pages:
        raw = texts[path]
        for m in re.finditer(r'{%[-\s]*(extends|include|from|import)\s+[\"\']([^\"\']+)', raw):
            references.append({'from': path, 'kind': m[1], 'target': m[2],
                               'line': raw.count('\n', 0, m.start()) + 1,
                               'exists': (repo / 'templates' / m[2]).is_file()})
        macros = re.findall(r'{%\s*macro\s+(\w+)\s*\(', raw)
        if '/widgets/' in path or '/macros/' in path or macros:
            components.append({'path': path, 'macros': macros, 'status': 'candidate_unverified'})
    home = texts.get(f'templates/{name}/index.html', '')
    headings = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h)).strip()
                for h in re.findall(r'<h[12]\b[^>]*>(.*?)</h[12]>', home, re.S | re.I)]
    grids = []
    for path, raw in texts.items():
        if path.endswith('.css') or path.endswith('/index.html'):
            grids += [{'path': path, 'value': m[1].strip(), 'line': raw.count('\n', 0, m.start()) + 1}
                      for m in re.finditer(r'grid-template-columns\s*:\s*([^;}]+)', raw)]
    private = sorted({r['target'].split('/')[0] for r in references
                      if '/' in r['target'] and ID.fullmatch(r['target'].split('/')[0])
                      and r['target'].split('/')[0] != name})
    asset_ids = sorted({m for raw in texts.values() for m in re.findall(r'/static/([a-z]+\d+)/', raw) if m != name})
    return {'id': name, 'family': re.sub(r'\d+$', '', name), 'status': 'source_only',
            'has_master': f'templates/{name}/master.html' in texts,
            'has_index': bool(home), 'has_static_directory': (repo/'static'/name).is_dir(),
            'html_files': pages, 'files': files, 'components': components,
            'literal_jinja_references': references, 'other_template_dependencies': private,
            'other_template_asset_ids': asset_ids, 'signals': evidence,
            'home_headings': headings, 'grid_declarations': grids,
            'source_fingerprint': hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}


def scan(repo, out):
    names = sorted([p.name for p in (repo/'templates').iterdir() if p.is_dir() and ID.fullmatch(p.name)], key=order)
    start_head = git(repo, 'rev-parse', 'HEAD')
    start_dirty = git(repo, 'status', '--porcelain')
    entries = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for index, entry in enumerate(pool.map(lambda name: analyze(repo, name), names), 1):
            entries.append(entry)
            if index % 100 == 0:
                print(f'Scanned {index}/{len(names)} templates', flush=True)
    families = dict(sorted(Counter(e['family'] for e in entries).items()))
    result = {'schema_version': 1, 'scanned_at_utc': datetime.now(timezone.utc).isoformat(),
              'repo_root': str(repo), 'branch': git(repo, 'branch', '--show-current'),
              'head': start_head, 'dirty_at_start': start_dirty.splitlines(),
              'git_state_changed_during_scan': start_head != git(repo, 'rev-parse', 'HEAD') or start_dirty != git(repo, 'status', '--porcelain'),
              'scope': 'All numbered local template directories and their private static directories; not remote branches or deployed sites.',
              'limitations': 'Regex source signals may include comments and miss dynamic/inherited/shared behavior. No runtime, visual or SEO pass. File hashes describe observed working-tree bytes, not an atomic snapshot.',
              'excluded_template_directories': sorted(p.name for p in (repo/'templates').iterdir() if p.is_dir() and not ID.fullmatch(p.name)),
              'static_only_ids': sorted(p.name for p in (repo/'static').iterdir() if p.is_dir() and ID.fullmatch(p.name) and p.name not in names),
              'family_counts': families, 'templates': entries}
    out.mkdir(parents=True, exist_ok=True)
    (out/'templates.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    lines = ['# 全模板源码目录', '', f"扫描时间：{result['scanned_at_utc']}；本地模板 **{len(entries)}** 套。",
             f"基线：`{result['branch']}` / `{start_head}`，包括当前未提交修改。", '',
             '范围：本地 templates 下全部字母+数字编号目录及对应 static；admin/shared 单独排除，不代表线上已部署数量。',
             '所有条目为 source_only。信号仅表示源码匹配；不代表功能、SEO、浏览器或主管验收通过。详细路径、行号、依赖、文件哈希见 templates.json。', '',
             '分组：'+ '；'.join(f'{k}: {v}' for k,v in families.items()), '',
             '| 编号 | HTML文件数（含组件） | 静态文件数 | 组件候选文件 | master/index | 未命中信号（非缺陷结论） |',
             '|---|---:|---:|---:|---|---|']
    for e in entries:
        missing = ', '.join(k for k,v in e['signals'].items() if not v) or '—'
        lines.append(f"| {e['id']} | {len(e['html_files'])} | {sum(f['path'].startswith('static/') for f in e['files'])} | {len(e['components'])} | {e['has_master']}/{e['has_index']} | {missing} |")
    (out/'TEMPLATES.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    focus = ['# x66–x80 源码参考索引', '', '以下是结构线索，不是浏览器视觉审阅。表中网格是源码声明摘录，可能属于不同断点/组件。', '']
    for e in entries:
        if e['id'] not in {f'x{i}' for i in range(66,81)}: continue
        focus += [f"## {e['id']}", '', '- 首页标题顺序：'+' → '.join(e['home_headings']),
                  '- 首页：`templates/'+e['id']+'/index.html`',
                  '- 网格声明：'+'；'.join(dict.fromkeys(f"`{g['value']}` ({g['path']}:{g['line']})" for g in e['grid_declarations'][:8])),
                  '- 组件候选：'+', '.join('`'+c['path']+'`' for c in e['components']), '']
    (out/'X66-X80.md').write_text('\n'.join(focus).rstrip()+'\n', encoding='utf-8')
    print(json.dumps({'templates': len(entries), 'families': families, 'files': sum(len(e['files']) for e in entries),
                      'component_candidates': sum(len(e['components']) for e in entries),
                      'git_state_changed_during_scan': result['git_state_changed_during_scan']}, ensure_ascii=False))


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        (repo/'templates/x1/widgets').mkdir(parents=True)
        (repo/'templates/x1/index.html').write_text("{% extends 'x1/master.html' %}<h1>Hello</h1>{% include 'x2/card.html' %}", encoding='utf-8')
        (repo/'templates/x1/widgets/score.html').write_text('{% macro score(v) %}{{ v }}{% endmacro %}', encoding='utf-8')
        entry = analyze(repo, 'x1')
        assert entry['home_headings'] == ['Hello'] and entry['other_template_dependencies'] == ['x2']
        assert not entry['has_master'] and not entry['signals']['search']
        assert entry['components'][0]['macros'] == ['score']
        assert all(not r['exists'] for r in entry['literal_jinja_references'])
        fingerprint = entry['source_fingerprint']
        (repo/'templates/x1/index.html').write_text('<h1>Changed</h1>', encoding='utf-8')
        assert analyze(repo, 'x1')['source_fingerprint'] != fingerprint
    print('self-test passed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2]/'cms-sport-tpl-bing')
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1]/'catalog/source-inventory')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        repo, out = args.repo.resolve(), args.out.resolve()
        if out == repo or repo in out.parents:
            parser.error('Catalog output must stay outside the business repository')
        scan(repo, out)
