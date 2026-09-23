"""Capture real server-rendered z home HTML and basic head/heading facts."""
import argparse
import os
import subprocess
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from core import resolve_repo_root, ROOT, fingerprint, git, read_json, save_json


def capture(number, output):
    name = f"z{number}"
    repo = resolve_repo_root()
    out = output / name
    out.mkdir(parents=True, exist_ok=True)
    inputs = [repo / "run.py", repo / "config.py", repo / "cache/cache_data.py",
              ROOT / "src/z_raw_home.py", *(repo / "templates" / name).rglob("*.html"),
              *(p for p in (repo / "static" / name).rglob("*") if p.is_file())]
    stamp = fingerprint({"template": name, "commit": git(repo, "rev-parse", "HEAD")}, inputs)
    summary_path = out / "summary.json"
    if summary_path.exists():
        if read_json(summary_path).get("input_hash") != stamp:
            raise ValueError(f"{name}: stale result; use a new output directory")
        print(f"resume {name}", flush=True)
        return
    port = 6500 + number
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
                    raise RuntimeError(f"{name}: preview process exited")
                try:
                    if requests.get(base + "/static/js/jquery.min.js", timeout=2).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(.5)
            else:
                raise RuntimeError(f"{name}: preview not ready")
            response = requests.get(base + "/", timeout=30)
            (out / "response.html").write_bytes(response.content)
            soup = BeautifulSoup(response.content, "html.parser")
            meta = lambda key: (soup.select_one(f'meta[name="{key}"]') or {}).get("content", "")
            headings = [h.get_text(" ", strip=True) for h in soup.select("h1")]
            result = {"template": name, "input_hash": stamp, "url": base + "/",
                      "status": response.status_code,
                      "headers": {k: v for k, v in response.headers.items()
                                  if k.lower() not in ("set-cookie", "authorization")},
                      "title": soup.title.get_text(" ", strip=True) if soup.title else "",
                      "description": meta("description"), "keywords": meta("keywords"),
                      "robots": meta("robots"), "h1": headings,
                      "main_links": len(soup.select("main a[href]")),
                      "main_text_chars": len(" ".join(m.get_text(" ", strip=True) for m in soup.select("main"))),
                      "evidence": "response.html"}
            result["checks"] = {"http_200": response.status_code == 200, "one_h1": len(headings) == 1,
                                "head_fields_present": bool(result["title"] and result["description"] and result["keywords"]),
                                "semantic_main_present": bool(soup.select_one("main"))}
            save_json(summary_path, result)
            print(name, result["checks"], flush=True)
        finally:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                process.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="+", type=int, default=list(range(1, 18)))
    parser.add_argument("--output", default="runs/z-raw-home")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT / "runs") or any(i < 1 or i > 17 for i in args.ids):
        raise ValueError("Output must be under runs/ and IDs z1..z17")
    for i in args.ids:
        capture(i, output)
