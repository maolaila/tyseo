"""Program-owned authenticated Sheet reader using a dedicated Playwright CLI session."""
import csv
import io
import json
import subprocess
from pathlib import Path
from cli_adapter import cli_executable
from core import ROOT

SESSION='tyseo-launch-program'
BOOK='1y7VWR6T4ABcd09qa51GM5-7XXGC80w1h21wCL4stvUg'
ADMIN_URL='https://s213016.abcd-cms.com/mgradm/optdata.html'

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
    def call(self,args,timeout=75):
        executable=cli_executable()
        if not executable:raise RuntimeError('浏览器工具不可用，请检查程序安装')
        r=subprocess.run([executable,'-s='+SESSION,*args],cwd=self.folder,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout,
                         creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name=='nt' else 0)
        text=r.stdout+'\n'+r.stderr
        (self.folder/'latest-cli.log').write_text(text,encoding='utf-8')
        if r.returncode or '### Error' in text:
            if 'ENOENT' in text:raise RuntimeError('读表脚本文件未找到，请检查程序路径；不是登录失败')
            if 'No browser' in text or 'not open' in text or 'not found' in text and 'session' in text:
                raise RuntimeError('程序浏览器会话不可用，请点击连接 Google 表格')
            raise RuntimeError('浏览器读表操作失败，详情已记录；不能据此判断未登录')
        return text
    def connect(self):
        profile=ROOT/'private/launch-browser';profile.mkdir(parents=True,exist_ok=True)
        return self.call(['open',f'https://docs.google.com/spreadsheets/d/{BOOK}/edit?gid=0#gid=0','--headed','--persistent','--profile',str(profile)],120)
    def run_script(self,body):
        path=self.folder/'read-sheet.js';path.write_text(body,encoding='utf-8')
        text=self.call(['run-code','--filename',str(path)],120)
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
        if not result.get('ok'):raise RuntimeError('请先在程序专用浏览器完成 Google 登录')
        return {'pending':parse_rows(result['pending'],'pending'),'launch':parse_rows(result['launch'],'launch')}

    def prefill_admin(self,script):
        # This action deliberately never clicks the submit button or posts the form.
        return self.run_script('''async(page)=>{
          const url='''+json.dumps(ADMIN_URL)+''';
          let admin=page.context().pages().find(p=>p.url()===url);
          if(!admin)admin=await page.context().newPage();
          await admin.goto(url,{waitUntil:'domcontentloaded'});await admin.bringToFront();
          if(await admin.locator('#optdata001').count()!==1)return {prefilled:false,submitted:false,reason:'backend_login_required'};
          const value='''+json.dumps(script,ensure_ascii=False)+''';
          await admin.locator('#optdata001').fill(value);
          return {prefilled:await admin.locator('#optdata001').inputValue()===value,submitted:false,lines:value.split('\\r\\n').length};
        }''')

def classify(domains,snapshot):
    changes=[]
    for item in domains:
        name=item['domain'].lower()
        launch=[r for r in snapshot['launch'] if r['domain']==name]
        pending=[r for r in snapshot['pending'] if r['domain']==name]
        if len(launch)>1 or any(r['owner']!='Pony' for r in launch+pending):
            changes.append({'domain':name,'observed':'needs_attention','reason':'Duplicate domain or owner mismatch'})
        elif launch and pending:
            changes.append({'domain':name,'observed':'needs_attention','reason':'Present in both sheets; purchase transition ambiguous'})
        elif launch:
            changes.append({'domain':name,'observed':'purchased_in_launch_sheet','row':launch[0]['row'],'keyword':launch[0]['keyword'],
                            'tdk_present':all(launch[0]['cells'][i].strip() for i in (5,6,7)),
                            'script_present':bool(launch[0]['cells'][16].strip())})
        elif pending:changes.append({'domain':name,'observed':'waiting_purchase'})
        else:changes.append({'domain':name,'observed':'needs_attention','reason':'Domain missing from both sheets'})
    return changes
