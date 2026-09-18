"""Real-app z-template matrix using the existing browser checker and isolated preview."""
import argparse
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import requests

from browser_checks import execute_matrix
from core import ROOT, fingerprint, git, read_json, save_json


def decorate_failures(records, contract):
    urls = {page["page_type_id"]: next((sample["path"] for sample in page.get("http_samples", [])
            if sample["status"] == 200), "unknown") for page in contract["pages"]}
    for record in records:
        if record.get("status") != "fail":
            continue
        metrics = record.get("metrics", {})
        width = record.get("width")
        evidence = record.get("evidence_paths", [])
        common = {"page": urls.get(record.get("page_type_id"), "unknown"), "viewport": width,
                  "theme": record.get("theme"), "data_state": record.get("environment"),
                  "engine": record.get("engine"), "evidence_paths": evidence}
        findings = []
        def add(rule_id, selector, expected, actual, severity="high", owner="template_or_asset"):
            findings.append({**common, "rule_id": rule_id, "selector": selector,
                             "expected": expected, "actual": actual, "severity": severity,
                             "owner_layer": owner})
        if width and metrics.get("scrollWidth", 0) > width + 2:
            add("LAYOUT-PAGE-OVERFLOW", "document.documentElement", f"scrollWidth <= {width + 2}", metrics["scrollWidth"])
        if not metrics.get("bodyText"):
            add("CONTENT-EMPTY-BODY", "body", "server-rendered readable body", metrics.get("bodyText", 0), "critical")
        if record.get("clipped_scores"):
            add("LAYOUT-CLIPPED-SCORE", ".score", "score remains inside viewport", record["clipped_scores"][:5])
        if record.get("errors"):
            add("JS-PAGE-ERROR", "window", "no page errors", record["errors"][:5], owner="template_or_external_needs_triage")
        state = record.get("theme_state", {})
        if record.get("javascript") and state.get("state_matches") is False:
            add("THEME-STATE-MISMATCH", "html[data-theme]", state.get("requested"), state.get("observed"))
        failed_interactions = {key: value for key, value in record.get("interactions", {}).items() if value is False}
        if failed_interactions:
            add("FUNCTION-INTERACTION", "relevant control", "all exercised interactions succeed", failed_interactions)
        if not findings:
            add("MATRIX-UNCLASSIFIED", "unknown", "no unresolved failure", record.get("reason", "unknown"), owner="tool_needs_triage")
        record["findings"] = findings
    return records


def run_one(number, output, page_types=None, widths=None, no_js_widths=None, contract_root=None):
    name = f"z{number}"
    repo = Path(read_json(ROOT / "tasks/bootstrap.json")["repo_root"])
    out = output / name
    out.mkdir(parents=True, exist_ok=True)
    contract_run = contract_root or ROOT / "runs" / ("z-review-fake-free-20260918" if 14 <= number <= 20 else "z-review-final-20260918")
    contract_path = contract_run / name / "page-contract.json"
    inputs = [repo / "run.py", repo / "config.py", repo / "cache/cache_data.py",
              ROOT / "src/browser_checks.py", ROOT / "src/z_acceptance.py", ROOT / "tasks/bootstrap.json", contract_path,
              *(repo / "templates" / name).rglob("*.html"),
              *(p for p in (repo / "static" / name).rglob("*") if p.is_file())]
    stamp = fingerprint({"template": name, "commit": git(repo, "rev-parse", "HEAD"),
                         "page_types": sorted(page_types) if page_types else "all",
                         "widths": widths or "default", "no_js_widths": no_js_widths or "default"}, inputs)
    if (out / "summary.json").exists():
        if read_json(out / "summary.json").get("input_hash") != stamp:
            raise ValueError(f"{name}: changed source; preserve old evidence and choose a new output directory")
        print(f"resume {name}", flush=True)
        return
    contract = read_json(contract_path)
    if page_types:
        available = {page["page_type_id"] for page in contract["pages"]}
        unknown = set(page_types) - available
        if unknown:
            raise ValueError(f"{name}: unknown page types: {sorted(unknown)}")
        contract["pages"] = [page for page in contract["pages"] if page["page_type_id"] in page_types]
    port = 6000 + number
    base = f"http://127.0.0.1:{port}"
    task = read_json(ROOT / "tasks/bootstrap.json")
    task.update(reference_template_id=name, preview_base_url=base)
    if widths:
        task["browser_matrix"]["widths"] = widths
    if no_js_widths:
        task["browser_matrix"]["no_js_widths"] = no_js_widths
    env = os.environ.copy()
    env.update(DEV_MasterID=name, APP_ENV="development", FLASK_HOST="127.0.0.1",
               FLASK_PORT=str(port), PYTHONDONTWRITEBYTECODE="1")
    with (out / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen([str(repo / ".venv/Scripts/python.exe"), "-B", "-u", "run.py"],
                                   cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            for _ in range(40):
                if process.poll() is not None:
                    raise RuntimeError(f"{name}: preview exited")
                try:
                    res = requests.get(base + "/static/js/jquery.min.js", timeout=2)
                    if res.status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.5)
            else:
                raise RuntimeError(f"{name}: preview not ready")
            selection = requests.get(base + "/", timeout=25)
            if selection.status_code != 200 or f"/static/{name}/" not in selection.text:
                raise RuntimeError(f"{name}: selected template not observed")
            records = decorate_failures(execute_matrix(task, contract, out), contract)
            save_json(out / "matrix-results.json", records)
            counts = Counter(item["status"] for item in records)
            summary = {"template": name, "input_hash": stamp, "environment": "real_app",
                       "page_types": len(contract["pages"]), "status_counts": dict(counts),
                       "coverage": "browser capture only; AI visual/SEO and interactions remain separate"}
            save_json(out / "summary.json", summary)
            print(f"{name} {dict(counts)}", flush=True)
        finally:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", type=int, default=list(range(1, 22)))
    parser.add_argument("--output", default="runs/z-acceptance-20260918")
    parser.add_argument("--page-types", nargs="+", help="Only these audited page type IDs; omit for the full matrix")
    parser.add_argument("--widths", nargs="+", type=int, help="Chromium JS widths; default is the configured full matrix")
    parser.add_argument("--no-js-widths", nargs="+", type=int, help="Chromium no-JS widths; default is configured")
    parser.add_argument("--contract-run", help="Existing z-review directory under runs/ with current page contracts")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "runs") or any(i < 1 or i > 21 for i in args.ids):
        raise ValueError("Output must be under external runs/ and IDs must be z1..z21")
    contract_root = (ROOT / args.contract_run).resolve() if args.contract_run else None
    if contract_root and (not contract_root.is_relative_to(ROOT / "runs") or not contract_root.is_dir()):
        raise ValueError("Contract run must be an existing directory under external runs/")
    for number in args.ids:
        run_one(number, output, args.page_types, args.widths, args.no_js_widths, contract_root)
