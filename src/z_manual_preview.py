"""Serve a manual review index for existing z1-z17 pages and original Flask apps."""
import json
import os
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from core import ROOT, git, read_json, save_json

OUT = ROOT / 'runs/z-manual-preview'
CONTRACTS = ROOT / 'runs/z-review-final-9415e-20260919'
PORT = 8771
PAGE_NAMES = {
    'index':'首页','allmatch':'全部赛事','article_list':'资讯列表','detail':'资讯详情',
    'detail_video':'视频详情','detail_zb':'比赛直播详情','detail_zb_show':'比赛直播展示页',
    'five_leagues':'五大联赛','hot_tag_detail':'热门标签详情','hot_tag_detail_pinyin':'热门标签拼音页',
    'league_best_lineup':'联赛最佳阵容','league_jifen':'联赛积分页','league_match_list':'联赛赛程',
    'league_match_list_folder':'分类联赛赛程','league_paihangbang':'联赛排行榜页',
    'league_player_rank':'联赛球员排名','league_rank':'联赛积分榜','league_rank_team_summary':'联赛球队排名汇总',
    'league_team_rank':'联赛球队排名','league_teams':'联赛球队列表','league_video_list':'联赛视频',
    'league_winner':'联赛历届冠军','list_hot_tag':'热门标签列表','list_jijin_all':'集锦列表',
    'list_luxiang_all':'录像列表','search':'搜索结果','sitemap':'网站地图','tag_list':'标签资讯列表',
    'team_data':'球队数据','team_info':'球队介绍','team_match_list':'球队赛程','team_player':'球队阵容',
    'team_player_honor_list':'球员荣誉','team_player_info':'球员详情','team_player_rank':'球队球员排名',
    'team_transfer':'球队转会','video_list':'视频列表',
}


def existing_pages(repo, template, contract):
    return [p for p in contract['pages']
            if p['entry_template'].startswith(template + '/')
            and (repo / 'templates' / p['entry_template']).is_file()]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    repo = Path(read_json(ROOT / 'tasks/bootstrap.json')['repo_root'])
    state = {'mode': 'z_manual_review', 'scope': 'z1-z17 existing pages only',
             'commit': git(repo, 'rev-parse', 'HEAD'), 'templates': []}
    processes = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                data = json.dumps(state, ensure_ascii=False).encode('utf-8')
                mime = 'application/json; charset=utf-8'
            elif self.path in ('/', '/index.html'):
                data = (OUT / 'index.html').read_bytes()
                mime = 'text/html; charset=utf-8'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)
        def log_message(self, *args): pass
    server = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    def start(number):
        name = f'z{number}'
        base = f'http://127.0.0.1:{6300 + number}'
        item = {'template': name, 'url': base + '/', 'ready': False, 'pid': None}
        with socket.socket() as probe:
            occupied = probe.connect_ex(('127.0.0.1', 6300 + number)) == 0
        if not occupied:
            env = os.environ.copy()
            env.update(DEV_MasterID=name, APP_ENV='development', FLASK_HOST='127.0.0.1',
                       FLASK_PORT=str(6300 + number), PYTHONDONTWRITEBYTECODE='1')
            with (OUT / f'{name}.log').open('a', encoding='utf-8') as log:
                process = subprocess.Popen([str(repo / '.venv/Scripts/python.exe'), '-B', '-u', 'run.py'],
                    cwd=repo, env=env, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            processes.append(process); item['pid'] = process.pid
        for attempt in range(30):
            try:
                response = requests.get(base + '/', timeout=5)
                item['http_status'] = response.status_code
                item['ready'] = response.status_code == 200 and f'/static/{name}/' in response.text
                if item['ready'] or occupied: break
            except requests.RequestException: pass
            time.sleep(.5)
        contract_path = CONTRACTS / name / 'page-contract.json'
        item['pages'] = existing_pages(repo, name, read_json(contract_path)) if contract_path.exists() else []
        print(name, 'ready' if item['ready'] else 'unavailable', flush=True)
        return item
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            state['templates'] = list(pool.map(start, range(1, 18)))
        sections = []
        for item in state['templates']:
            rows = []
            for page in item['pages']:
                sample = next((s['path'] for s in page.get('http_samples', []) if s.get('status') == 200), None)
                if sample and sample.startswith('/') and not sample.startswith('//'):
                    link = f'<a target="_blank" rel="noopener" href="{escape(item["url"].rstrip("/") + sample, quote=True)}">打开页面</a>'
                else: link = '<span class="pending">待有效样例</span>'
                rows.append(f'<tr><td>{escape(PAGE_NAMES.get(page["page_type_id"],page["page_type_id"]))}</td><td>{link}</td><td>{escape(sample or "已有文件，尚无成功访问的样例")}</td></tr>')
            name = item['template']
            sections.append(f'<section id="{name}"><h2>{name} · {"已启动" if item["ready"] else "启动待查"}</h2><p><a target="_blank" rel="noopener" href="{item["url"]}">打开首页</a> · 已有 {len(rows)} 类页面</p><details><summary>展开逐页复查清单</summary><table><thead><tr><th>页面类型</th><th>操作</th><th>历史真实样例路径</th></tr></thead><tbody>{"".join(rows)}</tbody></table></details></section>')
        nav = ''.join(f'<a href="#z{i}">z{i}</a>' for i in range(1,18))
        html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>z1–z17 人工复查</title><style>body{font:16px/1.6 system-ui;margin:0;background:#f1f5f9;color:#152238}main{max-width:1100px;margin:auto;padding:24px}nav{display:flex;gap:8px;flex-wrap:wrap}nav a,section{background:white;border:1px solid #cbd5e1;border-radius:8px;padding:12px}section{margin:16px 0}a{color:#075985}table{width:100%;border-collapse:collapse}th,td{padding:8px;border-bottom:1px solid #ddd;text-align:left;overflow-wrap:anywhere}.pending{color:#92400e}summary{cursor:pointer}@media(max-width:600px){main{padding:12px}td:last-child,th:last-child{display:none}}</style><main><h1>z1–z17 人工复查</h1><p>当前本地修复分支：' + escape(state['commit'][:10]) + '</p><p>检查各模板已有页面的跑版、遮挡、溢出和明暗主题。此入口不代表已验收通过；线上站点也尚未部署这些修复。本分支包含先前功能和SEO改动，暂不是纯样式交付。页面链接来自上次真实响应，数据变化可能使样例失效。</p><nav>' + nav + '</nav>' + ''.join(sections) + '</main></html>'
        (OUT / 'index.html').write_text(html, encoding='utf-8')
        # Runtime metadata excludes source data and secrets.
        save_json(OUT / 'state.json', {**state, 'templates': [{k:v for k,v in x.items() if k != 'pages'} for x in state['templates']]})
        print(f'http://127.0.0.1:{PORT}/', flush=True)
        server.serve_forever()
    finally:
        server.server_close()
        for process in processes:
            if process.poll() is None: process.terminate()


if __name__ == '__main__': main()
