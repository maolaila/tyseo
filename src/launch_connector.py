"""Authenticated Sheet reader and scoped TDK writer; no background activity."""
import csv
import io
import json
import subprocess
import time
from pathlib import Path
from cli_adapter import cli_executable
from core import ROOT

SESSION='tyseo-launch-program'
BOOK='1y7VWR6T4ABcd09qa51GM5-7XXGC80w1h21wCL4stvUg'
LAUNCH_URL=f'https://docs.google.com/spreadsheets/d/{BOOK}/edit?gid=2066853497#gid=2066853497'

def parse_rows(text,kind):
    rows=list(csv.reader(io.StringIO(text)))
    expected=['归属','域名','上站詞'] if kind=='pending' else ['日期','归属','域名','詞語','Template','Title','Description','Keyword']
    header=next((i for i,r in enumerate(rows[:8]) if r[:len(expected)]==expected),None)
    if header is None:raise ValueError('Unexpected spreadsheet header; refusing stale/incorrect data')
    result=[]
    for i,row in enumerate(rows[header+1:],header+2):
        row=row+['']*max(0,17-len(row))
        result.append({'row':i,'owner':row[0 if kind=='pending' else 1].strip(),'domain':row[1 if kind=='pending' else 2].strip().lower(),
                       'keyword':row[2 if kind=='pending' else 3].strip(),'cells':row})
    return result

class SheetConnector:
    def __init__(self,folder):
        self.folder=Path(folder).resolve();self.folder.mkdir(parents=True,exist_ok=True)
    def call(self,args,timeout=75,redact=()):
        executable=cli_executable()
        if not executable:raise RuntimeError('浏览器工具不可用，请检查程序安装')
        r=subprocess.run([executable,'-s='+SESSION,*args],cwd=self.folder,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,
                         creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
        text=r.stdout+'\n'+r.stderr
        log=text
        for value in redact:
            if value:log=log.replace(value,'[redacted]').replace(json.dumps(value)[1:-1],'[redacted]')
        (self.folder/'latest-cli.log').write_text(log,encoding='utf-8')
        if r.returncode or '### Error' in text:
            if 'ENOENT' in text:raise RuntimeError('读表脚本文件未找到，请检查程序路径；不是登录失败')
            if 'No browser' in text or 'not open' in text or 'Target page, context or browser has been closed' in text or 'not found' in text and 'session' in text:
                raise RuntimeError('程序浏览器会话不可用，请点击连接 Google 表格')
            raise RuntimeError('浏览器读表操作失败，详情已记录；不能据此判断未登录')
        return text
    def connect(self,url=None):
        profile=ROOT/'private/launch-browser';profile.mkdir(parents=True,exist_ok=True)
        return self.call(['open',url or LAUNCH_URL,'--headed','--persistent','--profile',str(profile)],120)
    def ensure_browser(self):
        try:self.run_script('async(page)=>{await page.title();return {ready:true}}')
        except RuntimeError as e:
            if '程序浏览器会话不可用' not in str(e):raise
            # Clear the dead CLI session without clearing the persistent browser profile.
            try:self.call(['close'])
            except RuntimeError:pass # Already-closed sessions may return an empty CLI error.
            self.connect(LAUNCH_URL)
    def run_script(self,body,redact=()):
        path=self.folder/'read-sheet.js';path.write_text(body,encoding='utf-8')
        try:text=self.call(['run-code','--filename',str(path)],120,redact=redact)
        finally:
            if redact:path.write_text('// Temporary login script removed.\n',encoding='utf-8')
        if '### Result\n' not in text:raise RuntimeError('No verified browser result')
        return json.JSONDecoder().raw_decode(text.split('### Result\n',1)[1].lstrip())[0]
    def read(self):
        result=self.run_script('''async (page) => {
          const out={};
          for (const [name,gid] of [['pending','0'],['launch','2066853497']]) {
            const r=await page.context().request.get('https://docs.google.com/spreadsheets/d/'''+BOOK+'''/export?format=csv&gid='+gid+'&_='+Date.now());
            if(r.status()!==200 || !(r.headers()['content-type']||'').includes('text/csv'))
              return {ok:false,reason:'google_login_required',http_status:r.status()};
            out[name]=await r.text();
          }
          return {ok:true,...out};
        }''')
        if not result.get('ok'):
            if result.get('http_status')==429:raise RuntimeError('Google 表格读取过于频繁（HTTP 429），请稍后重试；无需重新登录')
            if result.get('http_status') not in (401,403):raise RuntimeError('Google 表格读取失败（HTTP '+str(result.get('http_status'))+'），不是登录状态证明')
            raise RuntimeError('请先在程序专用浏览器完成 Google 登录')
        return {'pending':parse_rows(result['pending'],'pending'),'launch':parse_rows(result['launch'],'launch')}

    def write_tdk(self,updates,fresh=None):
        """Write approved E:H only, with fresh row identity and conflict checks."""
        fresh=self.read() if fresh is None else fresh
        if not updates:return fresh
        if len({u['domain'] for u in updates})!=len(updates):raise ValueError('Duplicate metadata update')
        for u in updates:
            matches=[r for r in fresh['launch'] if r['domain']==u['domain']]
            if len(matches)!=1 or matches[0]['owner']!='Pony' or matches[0]['row']!=u['row'] or matches[0]['cells'][:16]!=u['before_cells']:
                raise ValueError('上站表在写入前发生变化，未写入，请重新核对')
        groups=[]
        for u in sorted(updates,key=lambda u:u['row']):
            if not groups or u['row']!=groups[-1][-1]['row']+1:groups.append([])
            groups[-1].append(u)
        writes=[{'range':f"E{g[0]['row']}:H{g[-1]['row']}",'tsv':'\n'.join('\t'.join(u['values']) for u in g)} for g in groups]
        self.run_script('''async(page)=>{
          const sheet=await page.context().newPage();
          await sheet.goto('https://docs.google.com/spreadsheets/d/'''+BOOK+'''/edit?gid=2066853497#gid=2066853497',{waitUntil:'domcontentloaded',timeout:25000});
          await sheet.locator('#t-name-box').waitFor({timeout:25000});
          await sheet.context().grantPermissions(['clipboard-read','clipboard-write'],{origin:'https://docs.google.com'});
          const writes='''+json.dumps(writes,ensure_ascii=False)+''';
          for(const write of writes){
            await sheet.locator('#t-name-box').fill(write.range);await sheet.locator('#t-name-box').press('Enter');
            await sheet.evaluate(text=>navigator.clipboard.writeText(text),write.tsv);
            await sheet.keyboard.press('Control+V');await sheet.waitForTimeout(1000);
          }
          return {pasted:true,ranges:writes.map(x=>x.range)};
        }''')
        for _ in range(5):
            after=self.read();ready=True
            for u in updates:
                rows=[r for r in after['launch'] if r['domain']==u['domain']]
                if len(rows)!=1 or rows[0]['owner']!='Pony':raise ValueError('写入后域名/归属发生变化，停止处理')
                row=rows[0]
                if row['cells'][:4]!=u['before_cells'][:4] or row['cells'][8:16]!=u['before_cells'][8:16]:raise ValueError('非TDK配置发生变化，停止后续处理')
                ready=ready and row['cells'][4:8]==u['values']
            if ready:return after
            time.sleep(1)
        raise ValueError('写入结果未确认，已保留证据，请回读核实后再重试')
