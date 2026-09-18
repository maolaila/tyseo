"""Local program-owned poller and dashboard. No Codex heartbeat or model polling."""
import argparse
import json
import secrets
import threading
import time
import sys
import os
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).parent/'src'))
from core import ROOT,read_json,save_json
from launch_connector import SheetConnector,classify
from site_launch_state import completion

def utc():return datetime.now(timezone.utc).isoformat()

class Monitor:
    def __init__(self,state_path,interval=1800):
        self.path=Path(state_path);self.interval=interval;self.lock=threading.RLock();self.scan_lock=threading.Lock();self.wake=threading.Event()
        self.state=read_json(self.path);self.connector=SheetConnector(self.path.parent/'program-browser')
        enabled=self.state.get('monitor',{}).get('enabled',True) and not completion(self.state)['completed']
        self.state['automation_status']='deleted';self.state['monitor']={'executor':'local_program','enabled':enabled,'status':'starting' if enabled else 'paused','pid':os.getpid(),
            'interval_seconds':interval,'next_check_at':time.time() if enabled else None,'last_check_at':None,'last_success_at':None,'last_error':None,
            'connection_state':'unchecked','login_check_until':None}
        self.state.setdefault('events',[]);self.event('started','本地工作流程序已启动；Codex定时跟进已删除');self.persist()
    def persist(self):save_json(self.path,self.state)
    def event(self,kind,message):
        self.state['events'].append({'at':utc(),'kind':kind,'message':message});self.state['events']=self.state['events'][-150:]
    def status(self):
        with self.lock:
            return {'batch_id':self.state['batch_id'],'business_date':self.state['business_date'],'expected_count':self.state['expected_count'],
                    'monitor':dict(self.state['monitor']),'completion':completion(self.state),
                    'domains':[{k:d.get(k) for k in ('domain','keyword','status','observed','reason','row','tdk_present','script_present')} for d in self.state['domains']],
                    'events':list(self.state['events'][-30:]),'worker_status':'purchase monitoring implemented; TDK/release execution adapter not yet enabled'}
    def scan(self):
        if not self.scan_lock.acquire(blocking=False):return
        try:
            with self.lock:
                if datetime.now().date().isoformat()!=self.state['business_date']:
                    self.state['monitor'].update(enabled=False,status='paused',last_error='批次日期已变，保留未完成记录，等待处理')
                    self.event('blocked','批次日期已变，未自动续到新一天');self.persist();return
                m=self.state['monitor'];m.update(status='checking',last_check_at=utc(),next_check_at=None,last_error=None);self.persist()
            snapshot=self.connector.read();changes=classify(self.state['domains'],snapshot)
            with self.lock:
                by_name={x['domain']:x for x in self.state['domains']}
                for change in changes:
                    item=by_name[change['domain']];old=item.get('observed');item.update(change)
                    if old is not None and old!=change['observed']:self.event('state_change',item['domain']+' → '+change['observed'])
                    if change['observed']=='purchased_in_launch_sheet' and item['status']=='waiting_purchase':
                        item['status']='awaiting_tdk_worker';item['purchase_evidence']={'source':'authenticated_sheet_export','gid':2066853497,'row':change['row'],'at':utc()}
                if m.get('last_success_at') is None:self.event('connected','已成功读取表格，本批 '+str(len(changes))+' 个域名已核对')
                m.update(status='waiting',last_success_at=utc(),last_error=None,connection_state='connected',login_check_until=None)
                if any(x['status']=='awaiting_tdk_worker' for x in self.state['domains']):m['status']='action_required'
                if completion(self.state)['completed']:
                    m.update(enabled=False,status='completed');self.event('completed','本批全部上站核验完成，监听已停止')
                self.persist()
        except Exception as e:
            with self.lock:
                m=self.state['monitor'];message=str(e)[:180]
                if m.get('last_error')!=message:self.event('blocked',message)
                m.update(status='blocked',last_error=message,connection_state='login_required' if 'Google 登录' in message else 'read_error');self.persist()
        finally:
            with self.lock:
                m=self.state['monitor']
                retry_login=(m.get('connection_state')=='login_required' and (m.get('login_check_until') or 0)>time.time())
                m['next_check_at']=time.time()+(15 if retry_login else self.interval) if m['enabled'] else None;self.persist()
            self.scan_lock.release()
    def control(self,action):
        if action=='scan':threading.Thread(target=self.scan,daemon=True).start();return
        if action=='connect':
            def connect():
                # Serialize connection/navigation with reads; do not leave an old error after opening.
                if not self.scan_lock.acquire(blocking=False):return
                try:
                    with self.lock:
                        self.state['monitor'].update(status='connecting',last_error=None,connection_state='connecting',next_check_at=None)
                        self.persist()
                    self.connector.connect()
                    with self.lock:
                        self.state['monitor']['login_check_until']=time.time()+300
                except Exception as e:
                    with self.lock:
                        self.state['monitor'].update(status='blocked',last_error=str(e)[:160],connection_state='read_error',
                            next_check_at=time.time()+self.interval if self.state['monitor']['enabled'] else None)
                        self.event('blocked',str(e)[:160]);self.persist()
                    return
                finally:self.scan_lock.release()
                self.scan()
            threading.Thread(target=connect,daemon=True).start();return
        with self.lock:
            if action not in ('start','pause'):raise ValueError('Unknown control')
            m=self.state['monitor'];m['enabled']=action=='start';m['status']='waiting' if m['enabled'] else 'paused'
            m['next_check_at']=time.time() if m['enabled'] else None;self.event(action,'监听已启动' if m['enabled'] else '监听已暂停');self.persist();self.wake.set()
    def loop(self):
        while True:
            with self.lock:m=dict(self.state['monitor'])
            if m['enabled'] and m.get('next_check_at') is not None and time.time()>=m['next_check_at']:self.scan()
            self.wake.wait(1);self.wake.clear()

def serve(state,port=8766,interval=1800):
    token=secrets.token_urlsafe(24)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,data,kind='application/json'):
            data=data.encode('utf-8') if isinstance(data,str) else json.dumps(data,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if urlsplit(self.path).path=='/':self.reply(200,(ROOT/'web/workbench.html').read_text(encoding='utf-8'),'text/html')
            elif self.path=='/api/status':self.reply(200,{**monitor.status(),'control_token':token})
            else:self.reply(404,{'error':'Not found'})
        def do_POST(self):
            origin=self.headers.get('Origin','')
            if self.path!='/api/control' or self.headers.get('X-Workbench-Token')!=token or (origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}')):
                self.reply(403,{'error':'Forbidden'});return
            if int(self.headers.get('Content-Length','0'))>2048:self.reply(400,{'error':'Request too large'});return
            try:
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));monitor.control(data['action']);self.reply(202,{'accepted':True})
            except (ValueError,KeyError):self.reply(400,{'error':'Invalid action'})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler) # Bind first: a second process cannot create another poller.
    monitor=Monitor(state,interval);threading.Thread(target=monitor.loop,daemon=True).start()
    print(json.dumps({'url':f'http://127.0.0.1:{port}','pid':os.getpid(),'mode':'local_program'}),flush=True)
    server.serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',default='runs/site-launch/2026-09-18-pony-20/state.json');p.add_argument('--port',type=int,default=8766);p.add_argument('--interval',type=int,default=1800)
    a=p.parse_args()
    if a.interval<60:raise ValueError('Production polling interval must be at least 60 seconds')
    serve(a.state,a.port,a.interval)
