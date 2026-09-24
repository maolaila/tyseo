"""渲染后内容的确定性检查：页面上不该出现 None，简介不该留 Markdown 原文，每页只能有一个 h1。

这三条都是 2026-09-23/24 排查 z1–z17 时靠人工看页面才发现的，但它们全都能一眼判定，
不该每次都靠人看：

- 页面文本里出现 "None"：模板里 `<td>{{ item.x }}</td>` 这种没兜底，后端给 None 就直接印出来；
  `|default('x')` 不带第二个参数 true 时同理（default 只在"变量未定义"时生效）。
- 简介里留着 Markdown 原文（`### 标题`、`**加粗**`、`| 表头 |`）：后端存的是 Markdown，
  模板用 `|safe` 直接输出就会把原文印在页面上，要用共享过滤器 `|rich_text`。
- h1 不等于 1：母版/组件和页面各写一个就会重复，或者页面标题用了 span 就一个都没有。

用法（预览要先起好）：
    .venv\\Scripts\\python.exe -B src\\z_content_rules.py --ids 1 2 --output runs/z-content-<时间>
    PONY_REPO_ROOT=<worktree> 可指定预览实际跑的检出。
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import (ROOT, preview_source_check, read_json, repo_provenance,  # noqa: E402
                  resolve_repo_root, save_json)

SCRIPT_TAG = re.compile(r'(?s)<script.*?</script>')
NONE_TEXT = re.compile(r'>\s*(?:None|undefined|NaN)\s*<')
H1_TAG = re.compile(r'<h1[\s>]')
# 只在正文/简介容器里找 Markdown 残留，避免正文里正常出现的 ** 之类误报
CONTENT_BLOCK = re.compile(
    r'class="[^"]*(?:custom-league-intro|info-desc-value|article_content|news_content|content_detail)[^"]*"[^>]*>(.{0,8000}?)</div>',
    re.S)
MARKDOWN = re.compile(r'(?m)^\s{0,3}#{2,6}\s|\*\*[^*\n]{1,40}\*\*|(?m)^\s*\|.+\|\s*$')
# 欧联杯数据里的拼音是 oulianbei，但联赛页地址在后端改名后是 oulian；照数据拼链接必 404。
# 固定解法是在拼 URL 的地方换成 oulian（Rechard 2026-09-19 确认，细节见 AGENTS.md）。
# 注意这是这一个联赛的特例，别的 404 不能照猜路由。
RENAMED_LEAGUE = re.compile(r'href="[^"]*/oulianbei(?:[/"?#]|$)')


def sample_urls(contracts, repo, name, borrow='z1'):
    """页面契约里的真实样例，加上 config/extra-page-samples.json 里人工核实过的补充地址。

    新模板（z18、z22 这种）没有自己的页面契约，借用 borrow 那套的样例地址——
    后端数据和路由是同一份，页面类型也一一对应。和红线门槛的 --borrow 同一个做法。
    """
    contract_path = contracts / name / 'page-contract.json'
    if not contract_path.is_file():
        contract_path = contracts / borrow / 'page-contract.json'
    if not contract_path.is_file():
        return []
    extra_path = ROOT / 'config/extra-page-samples.json'
    extra = read_json(extra_path).get('samples', {}) if extra_path.is_file() else {}
    pages = []
    for page in read_json(contract_path)['pages']:
        entry = page['entry_template'].split('/', 1)[1]
        if not (repo / 'templates' / name / entry).is_file():
            continue
        sample = next((s['path'] for s in page.get('http_samples', []) if s['status'] == 200), None)
        sample = sample or extra.get(page['page_type_id'])
        # /play/ 是共享播放路由，不归模板管
        if sample and not sample.startswith('/play/'):
            pages.append((page['page_type_id'], sample))
    return pages


def check(base, page_type, path, timeout=120):
    url = base + path
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            status, body = response.status, response.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as error:
        return {'page_type': page_type, 'path': path, 'status': error.code, 'findings': ['HTTP ' + str(error.code)]}
    except (urllib.error.URLError, OSError) as error:
        return {'page_type': page_type, 'path': path, 'status': 'blocked', 'findings': [type(error).__name__]}

    text = SCRIPT_TAG.sub('', body)
    findings = []
    none_hits = NONE_TEXT.findall(text)
    if none_hits:
        findings.append(f'页面上印出了 None/undefined/NaN，共 {len(none_hits)} 处')
    h1 = len(H1_TAG.findall(text))
    if h1 != 1:
        findings.append(f'h1 有 {h1} 个（应当正好 1 个）')
    for block in CONTENT_BLOCK.finditer(text):
        if MARKDOWN.search(block.group(1)):
            findings.append('简介/正文里留着 Markdown 原文，应当用 |rich_text 而不是 |safe')
            break
    renamed = RENAMED_LEAGUE.findall(text)
    if renamed:
        findings.append(f'还有 {len(renamed)} 条链接指向 /oulianbei（该联赛已改名，拼 URL 时要换成 oulian）')
    return {'page_type': page_type, 'path': path, 'status': status, 'h1': h1,
            'none_hits': len(none_hits), 'findings': findings}


def run(ids, contract_run, output, repo_root=None, borrow='z1'):
    output = (ROOT / output).resolve()
    if not output.is_relative_to(ROOT / 'runs') or output.exists():
        raise SystemExit('输出目录必须是 runs/ 下还不存在的新目录')
    repo = resolve_repo_root(repo_root)
    contracts = (ROOT / contract_run).resolve()
    output.mkdir(parents=True)

    result = {'policy': 'content-rules-1.0', 'started_at': datetime.now(timezone.utc).isoformat(),
              **repo_provenance(repo), 'templates': []}
    for number in ids:
        name, base = f'z{number}', f'http://127.0.0.1:{6300 + number}'
        entry = {'template': name, 'base': base, 'status': 'fail', 'pages': [], 'failed': []}
        ok, note = preview_source_check(repo, name, base)
        entry['source_check'] = note
        if not ok:
            entry['status'] = 'blocked'
            result['templates'].append(entry)
            print(f'{name}: 没法验——{note}', flush=True)
            continue
        for page_type, path in sample_urls(contracts, repo, name, borrow):
            row = check(base, page_type, path)
            entry['pages'].append(row)
            if row['findings']:
                entry['failed'].append(row)
        entry['status'] = 'pass' if entry['pages'] and not entry['failed'] else ('fail' if entry['pages'] else 'blocked')
        result['templates'].append(entry)
        print(f"{name}: {len(entry['pages'])} 页，{len(entry['failed'])} 页有问题", flush=True)

    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    result['status'] = 'pass' if all(t['status'] == 'pass' for t in result['templates']) else 'fail'
    save_json(output / 'content-rules.json', result)

    lines = ['# 渲染后内容检查（None / Markdown 原文 / h1）', '',
             f"业务检出 {result['repo_root']}，分支 {result['branch']}，提交 {result['commit'][:9]}"
             f"{'（有未提交改动）' if result['dirty'] else ''}。", '']
    for entry in result['templates']:
        verdict = {'pass': '通过', 'fail': '不通过', 'blocked': '没法验'}[entry['status']]
        lines.append(f"- **{entry['template']}**：{verdict}（查了 {len(entry['pages'])} 个页面）")
        for row in entry['failed']:
            lines.append(f"  - `{row['path']}`（{row['page_type']}）：" + '；'.join(row['findings']))
    (output / 'content-rules.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:4]))
    return 0 if result['status'] == 'pass' else 1


def main():
    parser = argparse.ArgumentParser(description='渲染后内容的确定性检查')
    parser.add_argument('--ids', nargs='+', type=int, default=list(range(1, 18)))
    parser.add_argument('--output', required=True)
    parser.add_argument('--contract-run', default='runs/z-v2-recheck-20260919/contracts')
    parser.add_argument('--repo-root', help='预览实际跑的业务检出；不填则用 PONY_REPO_ROOT')
    parser.add_argument('--borrow', default='z1', help='没有页面契约的新模板借用哪一套的样例地址')
    args = parser.parse_args()
    return run(args.ids, args.contract_run, args.output, args.repo_root, args.borrow)


if __name__ == '__main__':
    raise SystemExit(main())
