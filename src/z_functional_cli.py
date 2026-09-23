"""Repeatable real-app z homepage interactions through playwright-cli 0.1.20."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests

from core import resolve_repo_root, ROOT, fingerprint, git, read_json, save_json


def run_one(number, root, cli, repo):
    name = f"z{number}"
    out = root / name
    out.mkdir(parents=True, exist_ok=True)
    session = f"tyseo-{name}-functional"
    port = 6200 + number
    base = f"http://127.0.0.1:{port}"
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
                    if requests.get(base + "/static/js/jquery.min.js", timeout=2).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.5)
            else:
                raise RuntimeError(f"{name}: preview not ready")
            opened = subprocess.run([cli, f"-s={session}", "open", base + "/"], cwd=root,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
            if opened.returncode:
                raise RuntimeError(f"{name}: CLI open failed; see output")
            result = subprocess.run([cli, f"-s={session}", "run-code", "--filename",
                                     str(ROOT / "scripts/cli-z-function.js")], cwd=root,
                                    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150)
            (out / "cli-output.txt").write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
            match = re.search(r"### Result\s*\n(.*?)\n### Ran Playwright code", result.stdout, re.S)
            data = json.loads(match.group(1)) if result.returncode == 0 and match else {"error": "CLI result unavailable"}
            data["template"] = name
            inputs = [repo / "run.py", repo / "config.py", repo / "cache/cache_data.py",
                      ROOT / "src/z_functional_cli.py", ROOT / "scripts/cli-z-function.js",
                      ROOT / "tasks/bootstrap.json",
                      *(repo / "templates" / name).rglob("*.html"),
                      *(p for p in (repo / "static" / name).rglob("*") if p.is_file())]
            data["input_hash"] = fingerprint({"template": name, "commit": git(repo, "rev-parse", "HEAD"),
                                              "playwright_cli": "0.1.20"}, inputs)
            save_json(out / "functional.json", data)
            print(name, {key: data.get(key) for key in ("navigation", "theme", "gotoTop", "search")}, flush=True)
        finally:
            try:
                subprocess.run([cli, f"-s={session}", "close"], cwd=root,
                               capture_output=True, timeout=45)
            except subprocess.TimeoutExpired:
                print(f"{name}: CLI close timed out; session cleanup needs review", flush=True)
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", type=int, default=list(range(1, 18)))
    parser.add_argument("--output", default="runs/z-functional-20260918")
    args = parser.parse_args()
    root = (ROOT / args.output).resolve()
    if not root.is_relative_to(ROOT / "runs") or any(i < 1 or i > 17 for i in args.ids):
        raise ValueError("Output must be under runs/ and IDs z1..z17")
    root.mkdir(parents=True, exist_ok=True)
    cli = shutil.which("playwright-cli.cmd") or shutil.which("playwright-cli")
    if not cli or subprocess.check_output([cli, "--version"], text=True).strip() != "0.1.20":
        raise RuntimeError("playwright-cli 0.1.20 required")
    repo = resolve_repo_root()
    for number in args.ids:
        run_one(number, root, cli, repo)
