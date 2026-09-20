"""Human-readable final user journey handoff without upgrading missing evidence."""
import argparse
from collections import Counter

from core import ROOT, read_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True)
    args=parser.parse_args()
    run=(ROOT/args.run).resolve()
    if not run.is_relative_to(ROOT/'runs') or not (run/'summary.json').is_file():
        raise ValueError('Completed run under runs/ required')
    summary=read_json(run/'summary.json')
    nojs=read_json(run/'nojs-summary.json') if (run/'nojs-summary.json').is_file() else None
    seo=read_json(run/'raw-seo-summary.json') if (run/'raw-seo-summary.json').is_file() else None
    rows=summary['templates']
    lines=['# 模板最终用户操作复查','',
           '本报告只统计当前本地业务预览及实际执行证据。旧页面契约只提供样例，缺真实样例的已有页面保持 blocked；共享 `/play` 由后端另行处理。本轮按用户指示不处理无关404。',
           '',f"原始HTTP 200样例：{sum(x['raw_http_200'] for x in rows)}；浏览器页面/宽度状态：{sum(x['browser_page_states'] for x in rows)}；公共操作：{sum(x['common_cases'] for x in rows)}；专用组件状态：{sum(x['specific_cases'] for x in rows)}。",
           f"无JS：{nojs['status_counts'] if nojs else '未运行'}；原始HTML SEO规则：{seo['checks'] if seo else '未运行'}。",'',
           '|模板|本轮状态|HTTP 200|页面×宽度|公共操作|专用状态|缺样例|主要待处理|',
           '|---|---|---:|---:|---:|---:|---:|---|']
    for row in rows:
        name=row['template']
        browser=read_json(run/name/'browser.json')
        pending=[x for x in browser.get('common',[])+browser.get('specific',[]) if x.get('status') not in ('pass','not_applicable')]
        brief='; '.join(f"{x['rule_id']}:{x['status']}" for x in pending[:3]) or '无已执行操作失败'
        if row['raw_not_200']:
            brief+='; 原始HTTP异常 '+', '.join(row['raw_not_200'][:2])
        if row.get('error'):brief=row['error']
        lines.append(f"|{name}|{row['status']}|{row['raw_http_200']}|{row['browser_page_states']}|{row['common_cases']}|{row['specific_cases']}|{len(row['missing_page_samples'])}|{brief}|")
    lines+=['','## 待确认和证据界限','']
    for row in rows:
        if row['missing_page_samples']:
            lines.append(f"- {row['template']} 缺真实样例：{', '.join(row['missing_page_samples'])}。")
        if row['raw_not_200']:
            lines.append(f"- {row['template']} 本轮原始HTTP非200：{', '.join(row['raw_not_200'])}，详见 `{row['template']}/http-pages.json`。")
    lines+=['','## 人工截图索引','']
    for row in rows:
        name=row['template']
        shots=read_json(run/name/'browser.json').get('screenshots',[])
        links=[f"[{shot.rsplit('/',1)[-1]}]({name}/{shot.rsplit('/',1)[-1]})" for shot in shots]
        lines.append(f"- {name}："+('、'.join(links) if links else '未生成截图。'))
    lines+=['','每套详细操作在 `zN/browser.json`，失败/待定在 `zN/findings.json`，原始HTML、截图和来源指纹位于同目录。浏览器和无JS未覆盖的页面、SEO策略未知项、Firefox/WebKit、完整布局矩阵、人工视觉及线上验证均未在此升级为通过。`automated_pass`、人工验收、公司合并和上线是不同状态。','']
    (run/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    print({'templates':len(rows),'status_counts':dict(Counter(x['status'] for x in rows)),
           'report':str(run/'report.md')})


if __name__=='__main__':main()
