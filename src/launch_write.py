"""把一批已写好、已查重的 TDK 填进 Bing 上站表本人那几行（命令行入口，给机器人用；做的事和工作台"确认写入本批 TDK"一样）。

  python src/launch_write.py --batch runs/site-launch/<批次>            只核对，不写（默认）
  python src/launch_write.py --batch runs/site-launch/<批次> --write    核对通过后写 E:H 并回读

规则（docs/SITE_LAUNCH_RUNBOOK.md）：按 日期 + 归属 Pony + 域名 + 分配词 在"上站202609"里逐个唯一匹配；
只写 E:H（Template、Title、Description、Keyword）；E:H 已有不同内容就整批停下不写；写后回读，A:D 和 I:P 不能变。
TDK 来自批次目录的 tdk-drafts.json，并要求 tdk-draft-validation.json 里查重为 0。结果写到批次目录的 launch-write-receipt.json。
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from core import ROOT
from launch_connector import SheetConnector


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    batch = Path(args.batch) if Path(args.batch).is_absolute() else ROOT / args.batch
    drafts = json.loads((batch / 'tdk-drafts.json').read_text(encoding='utf-8'))
    check = json.loads((batch / 'tdk-draft-validation.json').read_text(encoding='utf-8'))
    date = batch.name[:10]
    problems = []
    if check.get('duplicates') != 0 or check.get('count') != len(drafts):
        problems.append(f"TDK 查重结果不对（duplicates={check.get('duplicates')}，count={check.get('count')}，稿子 {len(drafts)} 份）")
    for d in drafts:
        if not all(str(d.get(k) or '').strip() for k in ('domain', 'keyword', 'title', 'description', 'keywords', 'template')):
            problems.append(f"{d.get('domain')}：TDK 有空字段")
    connector = SheetConnector(batch / 'sheet-session')
    connector.ensure_browser()
    fresh = connector.read()
    updates, report = [], []
    for d in drafts:
        domain = d['domain'].strip().lower()
        rows = [r for r in fresh['launch'] if r['domain'] == domain]
        if len(rows) != 1:
            problems.append(f'{domain}：上站表里找到 {len(rows)} 行（要正好 1 行）')
            continue
        r = rows[0]
        cells = r['cells']
        if r['owner'] != 'Pony' or cells[0].strip() != date or r['keyword'] != d['keyword'].strip():
            problems.append(f"{domain}：第 {r['row']} 行对不上（日期 {cells[0]!r}、归属 {r['owner']!r}、分配词 {r['keyword']!r}）")
            continue
        values = [d['template'].strip(), d['title'].strip(), d['description'].strip(), d['keywords'].strip()]
        current = [c.strip() for c in cells[4:8]]
        if current == values:
            report.append({'row': r['row'], 'domain': domain, 'state': 'already_same'})
            continue
        if any(current):
            problems.append(f"{domain}：第 {r['row']} 行 E:H 已经有不一样的内容，不覆盖")
            continue
        updates.append({'row': r['row'], 'domain': domain, 'values': values, 'before_cells': cells[:16]})
        report.append({'row': r['row'], 'domain': domain, 'state': 'to_write'})
    rows = sorted(x['row'] for x in report)
    summary = {'batch': batch.name, 'date': date, 'checked_at': datetime.now(timezone.utc).isoformat(), 'drafts': len(drafts),
               'matched_rows': f'{rows[0]}-{rows[-1]}' if rows else '', 'to_write': len(updates),
               'already_same': sum(x['state'] == 'already_same' for x in report), 'problems': problems, 'written': False}
    if problems:
        print('不写：' + '；'.join(problems))
    elif args.write and updates:
        after = connector.write_tdk(updates, fresh)
        for u in updates:
            row = next(r for r in after['launch'] if r['domain'] == u['domain'])
            if [c.strip() for c in row['cells'][4:8]] != u['values']:
                raise SystemExit(f"{u['domain']}：回读和写入的不一致")
        summary.update(written=True, written_rows=[u['row'] for u in updates], readback='E:H 与写入一致，A:D、I:P 未变')
        print(f"已写入并回读：第 {summary['matched_rows']} 行，共 {len(updates)} 行 E:H")
    elif args.write:
        print('不用写：这些行的 E:H 已经和本批 TDK 一致')
    else:
        print(f"核对通过：第 {summary['matched_rows']} 行，要写 {len(updates)} 行，已一致 {summary['already_same']} 行（加 --write 才会写）")
    (batch / ('launch-write-receipt.json' if args.write else 'launch-write-check.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
