"""Summarize the real-app z matrix without promoting captures to acceptance."""
import argparse
import os
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from core import ROOT, fingerprint, git, read_json, save_json


def build(run, contract_run=None, reuse_run=None, reuse_commit=None):
    run = (ROOT / run).resolve()
    if not run.is_relative_to(ROOT / "runs") or not run.is_dir():
        raise ValueError("Matrix run must be an existing directory under external runs/")
    contracts = (ROOT / contract_run).resolve() if contract_run else None
    if contracts and (not contracts.is_relative_to(ROOT / "runs") or not contracts.is_dir()):
        raise ValueError("Contract run must be an existing directory under external runs/")
    reuse_runs = [reuse_run] if isinstance(reuse_run, str) else reuse_run or []
    reuse_commits = [reuse_commit] if isinstance(reuse_commit, str) else reuse_commit or []
    if len(reuse_runs) != len(reuse_commits) or (reuse_runs and not contracts):
        raise ValueError("Each reused run needs its source commit and the contract run")
    reuse_pairs = [((ROOT / old).resolve(), old_commit) for old, old_commit in zip(reuse_runs, reuse_commits)]
    if any(not old.is_relative_to(ROOT / "runs") or not old.is_dir() for old, _ in reuse_pairs):
        raise ValueError("Reused runs must be existing directories under external runs/")
    repo = Path(read_json(ROOT / "tasks/bootstrap.json")["repo_root"])
    commit = git(repo, "rev-parse", "HEAD")
    rows = []
    findings = []
    preview = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>z 矩阵截图索引</title>',
               '<style>body{font:15px system-ui;margin:2rem;background:#f1f5f9}section,details{background:white;padding:1rem;margin:.7rem 0;border-radius:8px}img{width:280px;max-height:420px;object-fit:contain}a{color:#075985}summary{cursor:pointer}</style>',
               '<h1>z1–z17 矩阵截图索引</h1><p>缩图仅用于定位；点击查看原图。自动截图和几何检查不等于 AI 或公司验收。</p>']
    for number in range(1, 18):
        name = f"z{number}"
        inputs = [repo / "run.py", repo / "config.py", repo / "cache/cache_data.py",
                  ROOT/'scripts/layout-audit.js', ROOT/'scripts/layout-shift-init.js', ROOT/'config/acceptance-policy.json', ROOT/'src/z_manual_preview.py',
                  ROOT / "src/browser_checks.py", ROOT / "src/z_acceptance.py", ROOT / "tasks/bootstrap.json",
                  contracts / name / "page-contract.json", *(repo / "templates" / name).rglob("*.html"),
                  *(p for p in (repo / "static" / name).rglob("*") if p.is_file())] if contracts else []
        def expected_hash(source_commit):
            return fingerprint({"template": name, "commit": source_commit, "page_types": "all",
                                "widths": "default", "no_js_widths": "default"}, inputs)
        folder = run / name
        source_commit = commit
        if not (folder / "summary.json").exists():
            for old, old_commit in reuse_pairs:
                candidate = old / name / "summary.json"
                if candidate.exists() and (candidate.parent / "matrix-results.json").exists() and read_json(candidate).get("input_hash") == expected_hash(old_commit):
                    folder, source_commit = old / name, old_commit
                    break
        summary_path = folder / "summary.json"
        record_path = folder / "matrix-results.json"
        records = read_json(record_path) if record_path.exists() else []
        counts = dict(Counter(record.get("status", "unknown") for record in records))
        row = {"template": name, "complete": summary_path.exists() and record_path.exists() and bool(records), "records": len(records),
               "status_counts": counts, "source_input_hash": read_json(summary_path).get("input_hash") if summary_path.exists() else None,
               "reused": folder != run / name, "evidence_run": folder.parent.name, "source_commit": source_commit}
        if row["complete"] and contracts:
            row["source_fresh"] = row["source_input_hash"] == expected_hash(source_commit)
        else:
            row["source_fresh"] = None
        rows.append(row)
        preview.append(f'<section><h2>{name} · {"已采集" if row["complete"] else "进行中"}</h2><p>{escape(str(counts))} · 源码新鲜度：{row["source_fresh"]}</p>')
        by_page = defaultdict(list)
        for record in records:
            by_page[record.get("page_type_id", "unknown")].append(record)
            for finding in record.get("findings", []):
                findings.append({"template": name, **finding})
        for page_id, page_records in by_page.items():
            page_counts = dict(Counter(item.get("status", "unknown") for item in page_records))
            preview.append(f'<details><summary>{escape(page_id)} · {escape(str(page_counts))}</summary>')
            for record in page_records:
                label = f'{record.get("engine")} {record.get("width")} {record.get("theme")} JS={record.get("javascript")} · {record.get("status")}'
                shot = next((path for path in record.get("evidence_paths", []) if path.endswith("-viewport.png")), None)
                if shot:
                    relative = (Path(os.path.relpath(folder, run)) / shot).as_posix()
                    preview.append(f'<a href="{escape(relative)}"><img loading="lazy" src="{escape(relative)}" alt="{escape(label)}"></a>')
                else:
                    preview.append(f'<p>{escape(label)} · {escape(record.get("reason", ""))}</p>')
            preview.append('</details>')
        preview.append('</section>')
    total = Counter()
    for row in rows:
        total.update(row["status_counts"])
    overview = {"completed": sum(row["complete"] for row in rows), "expected_templates": 17,
                "fresh_completed": sum(row["source_fresh"] is True for row in rows),
                "reused_templates": [row["template"] for row in rows if row["reused"] and row["source_fresh"]],
                "stale_templates": [row["template"] for row in rows if row["source_fresh"] is False],
                "records": sum(row["records"] for row in rows), "status_counts": dict(total),
                "findings": findings, "templates": rows, "accepted": False,
                "scope": "saved real-app browser observations only; AI visual/SEO and company acceptance separate"}
    save_json(run / "matrix-overview.json", overview)
    report = ["# z1–z17 真实应用矩阵", "",
              f"模板完成采集：{overview['completed']}/17；源码哈希仍匹配：{overview['fresh_completed']}/17；记录：{overview['records']}；状态：{overview['status_counts']}。",
              "", "自动 `needs_review` 不是 PASS，`blocked` 不从分母删除。复用的模板按旧提交参数和当前输入文件逐一重算哈希；图片索引见 `matrix-screenshots.html`，点击可看原图。",
              f"规则失败证据：{len(findings)} 条，详情见 `matrix-overview.json` 的 findings。",
              "", "|模板|证据运行|采集完毕|源码匹配|记录|状态|", "|---|---|---|---|---:|---|"]
    for row in rows:
        report.append(f"|{row['template']}|{row['evidence_run']}|{row['complete']}|{row['source_fresh']}|{row['records']}|{row['status_counts']}|")
    report += ["", "此报告不宣称逐页 AI 复核、主管验收、上线或 Bing 抓取。"]
    (run / "matrix-report.md").write_text("\n".join(report), encoding="utf-8")
    (run / "matrix-screenshots.html").write_text("\n".join(preview) + "</html>", encoding="utf-8")
    print(f"matrix report: {overview['completed']}/17, {overview['records']} records, {len(findings)} findings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--contract-run")
    parser.add_argument("--reuse-run", action="append", help="Older complete run; repeat with a paired source commit")
    parser.add_argument("--reuse-commit", action="append", help="Source commit for the corresponding reused run")
    args = parser.parse_args()
    build(args.run, args.contract_run, args.reuse_run, args.reuse_commit)
