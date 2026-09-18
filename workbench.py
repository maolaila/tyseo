"""Manual Pony TDK workbench. No poller, launch submission, or background jobs."""
import argparse
import hashlib
import json
import os
import secrets
import sys
import threading
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).parent/'src'))
from core import ROOT,read_json,save_json
from launch_connector import LAUNCH_URL,SheetConnector
from tdk import ensure_unique_tdks,plan_sheet_write,prior_tdks,record_tdk_history,require_current_review

def utc():return datetime.now(timezone.utc).isoformat()

class Workbench:
    def __init__(self,state_path):
        self.path=Path(state_path).resolve()
        self.state=read_json(self.path)
        self.connector=SheetConnector(self.path.parent/'program-browser')
        self.lock=threading.Lock()
        receipt_path=self.path.parent/'sheet-write-receipt.json'
        if not self.state.get('tdk_write_result') and receipt_path.exists():
            receipt=read_json(receipt_path)
            verified=receipt.get('readback_verified') or receipt.get('verified_by')=='Google Sheets UI clipboard readback'
            if verified and receipt.get('count')==self.state['expected_count']:
                self.state['tdk_write_result']={'domains_verified':receipt['count'],
                                                'rows_written':receipt.get('rows',[])}

    def revision(self):
        values=[(d['domain'],(d.get('tdk') or {}).get('revision'),d.get('row')) for d in self.state['domains']]
        return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()

    def readiness(self):
        if self.state['business_date']!=datetime.now().date().isoformat():
            return False,'这是旧日期批次，请先建立当次任务'
        if len(self.state['domains'])!=self.state['expected_count']:
            return False,'本批域名数量与台账不一致'
        if self.state.get('tdk_write_result') and all(d.get('status')=='sheet_filled' for d in self.state['domains']):
            return False,'本批 TDK 已填入并回读确认，无需重复写入'
        try:
            ensure_unique_tdks(self.state['domains'],prior_tdks(self.path))
            for item in self.state['domains']:require_current_review(item)
        except ValueError as error:return False,str(error)
        return True,None

    def status(self):
        ready,reason=self.readiness()
        done=bool(self.state.get('tdk_write_result')) and all(d.get('status')=='sheet_filled' for d in self.state['domains'])
        return {'batch_id':self.state['batch_id'],'business_date':self.state['business_date'],
                'expected_count':self.state['expected_count'],'ready':ready,'done':done,'reason':reason,
                'domains':[{k:d.get(k) for k in ('domain','keyword','status','row','tdk','leo_review','reason')} for d in self.state['domains']],
                'revision':self.revision(),'last_result':self.state.get('tdk_write_result'),
                'program':{'mode':'tdk_only','pid':os.getpid(),'background_monitor':False}}

    def connect(self):
        self.connector.ensure_browser()
        self.connector.run_script('''async(page)=>{
          const tab=await page.context().newPage();
          await tab.goto('''+json.dumps(LAUNCH_URL)+''',{waitUntil:'domcontentloaded',timeout:25000});
          await tab.bringToFront();
          return {opened:true};
        }''')
        return {'opened':True,'url':LAUNCH_URL}

    def write_tdk(self,revision):
        if not self.lock.acquire(blocking=False):raise ValueError('上站表写入正在进行，请等待结果')
        try:
            if not revision or revision!=self.revision():raise ValueError('TDK 已变化，请刷新后重新核对')
            ready,reason=self.readiness()
            if not ready:raise ValueError(reason)
            self.connector.ensure_browser()
            snapshot=self.connector.read()
            history=prior_tdks(self.path)
            updates=plan_sheet_write(self.state['domains'],snapshot,history)
            save_json(self.path.parent/'sheet-write-intent.json',
                      {'at':utc(),'revision':revision,'rows':[u['row'] for u in updates],
                       'domains':[u['domain'] for u in updates]})
            after=self.connector.write_tdk(updates,fresh=snapshot)
            if plan_sheet_write(self.state['domains'],after,history):
                raise ValueError('部分 TDK 未回读确认；请先检查表格，再决定是否重试')
            rows={r['domain']:r for r in after['launch']}
            for item in self.state['domains']:
                item.update(status='sheet_filled',tdk_present=True,row=rows[item['domain']]['row'])
            record_tdk_history(self.state['domains'],self.state['batch_id'])
            result={'at':utc(),'domains_verified':len(self.state['domains']),
                    'rows_written':[u['row'] for u in updates],
                    'source':'Google 上站表 E:H 回读','next_step':'由用户手动处理'}
            self.state['tdk_write_result']=result
            save_json(self.path,self.state)
            save_json(self.path.parent/'sheet-write-receipt.json',result)
            return result
        finally:self.lock.release()

def serve(state_path,port=8766):
    workbench=Workbench(state_path)
    token=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,data,kind='application/json'):
            payload=data.encode('utf-8') if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/':self.reply(200,(ROOT/'web/workbench.html').read_text(encoding='utf-8'),'text/html')
            elif path=='/api/status':self.reply(200,{**workbench.status(),'control_token':token})
            else:self.reply(404,{'error':'Not found'})
        def do_POST(self):
            origin=self.headers.get('Origin','')
            if self.path!='/api/control' or self.headers.get('X-Workbench-Token')!=token or (origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}')):
                self.reply(403,{'error':'Forbidden'});return
            length=int(self.headers.get('Content-Length','0'))
            if length<1 or length>2048:self.reply(400,{'error':'Invalid request length'});return
            try:
                data=json.loads(self.rfile.read(length))
                if data['action']=='connect':result=workbench.connect()
                elif data['action']=='write_tdk':result=workbench.write_tdk(data.get('revision'))
                else:raise ValueError('Unknown control')
                self.reply(200,result)
            except (ValueError,KeyError) as error:self.reply(409,{'error':str(error)[:180]})
            except Exception:self.reply(503,{'error':'表格操作失败，写入结果不明。请先核对目标行，再重试。'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(json.dumps({'url':f'http://127.0.0.1:{port}','mode':'tdk_only','pid':os.getpid()}),flush=True)
    server.serve_forever()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--state',default='runs/site-launch/2026-09-18-pony-20/state.json')
    parser.add_argument('--port',type=int,default=8766)
    options=parser.parse_args()
    serve(options.state,options.port)
