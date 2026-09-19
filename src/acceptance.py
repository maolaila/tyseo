"""Full coverage plans and evidence gates for the existing semi-automatic workflow.

No scheduler, RS connector, remote writes, or business file mutations.
"""
import hashlib
import json
import sys
from importlib.metadata import version
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup
from core import ROOT, digest, read_json, save_json, inside

KEY_PAGES = {'index','search','detail','detail_zb','type_list','article_list'}
SPORT_STATES = ['number_zero','string_zero','zero_zero','zero_one','one_zero','null',
                'undefined','not_started','two_digit','three_digit','long_zh_name',
                'long_en_name','missing_logo','failed_logo','postponed','cancelled','live','finished']

def input_stamp(task, contract_path):
    repo=Path(task['repo_root']); names={repo/'run.py',repo/'config.py',repo/'cache/cache_data.py',Path(contract_path),
        ROOT/'requirements-lock.txt',ROOT/'AGENTS.md',ROOT/'PRD.md',ROOT/'docs/ACCEPTANCE.md',ROOT/'docs/ACCEPTANCE_INCREMENT.md',ROOT/'docs/TEMPLATE_ACCEPTANCE_STANDARD.md',ROOT/'docs/TEMPLATE_ACCEPTANCE_STANDARD_V2.md',repo/'AGENTS.md'}
    names.update([ROOT/'workflow.py',ROOT/'pipeline.py'])
    for directory in ('src','scripts','config','schemas','fixtures'):
        names.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for template in {task['reference_template_id'],task.get('target_template_id')} - {None}:
        for kind in ('templates','static'):
            names.update(p for p in (repo/kind/template).rglob('*') if p.is_file())
    for key in ('design_spec_path',):
        if task.get(key):names.add(Path(task[key]))
    # Environment contents are not exported; changes invalidate prior observations.
    if (repo/'.env').exists():names.add(repo/'.env')
    names.update(p for p in (repo/'static/js').glob('*') if p.is_file())
    values={str(p.resolve()):digest(p) for p in sorted(names)}
    payload={'task':task,'files':values,'python':sys.version,'packages':{p:version(p) for p in ('playwright','Jinja2','requests')}}
    return hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()

def make_plan(task, contract, stamp):
    matrix=task['browser_matrix']; cases=[]; reviews=[]; requirements=[]; excluded=[]; case_ids=set()
    policy=read_json(ROOT/'config/acceptance-policy.json')
    page_scope=task.get('page_scope','existing_only' if task.get('mode')=='repair-template' else 'full_site')
    def add(page,engine,width,theme,js,state='observed',scale=1,stress='normal',height=900):
        item={'page_type_id':page['page_type_id'],'engine':engine,'width':width,'theme':theme,
              'javascript':js,'data_state':state,'text_scale':scale,
              'stress':stress,'height':height,
              'environment':'real_app' if state=='observed' else 'fixture'}
        item['case_id']=hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()[:20]
        if item['case_id'] in case_ids:return
        case_ids.add(item['case_id'])
        item['sample_urls']=page.get('sample_urls',[])
        item['status']='blocked' if not item['sample_urls'] and state=='observed' else 'not_run'
        cases.append(item)
    for page in contract['pages']:
        if page_scope=='existing_only' and page.get('template_exists') is False:
            excluded.append({'page_type_id':page['page_type_id'],'reason':'confirmed existing-page repair scope; template file absent','status':'not_applicable'})
            continue
        for w in sorted(set(matrix['widths']+policy['widths'])):
            for theme in matrix['themes']:add(page,'chromium',w,theme,True)
        for w in sorted(set(matrix['no_js_widths']+policy['no_js_widths'])):
            for theme in matrix['themes']:add(page,'chromium',w,theme,False)
        if policy.get('artificial_text_stress',False):
            for w in (390,1280):
                for theme in matrix['themes']:
                    add(page,'chromium',w,theme,True,scale=2,stress='text_resize_200')
                    add(page,'chromium',w,theme,True,stress='wcag_text_spacing')
        if page['page_type_id'] in KEY_PAGES:
            for engine in dict.fromkeys(matrix['secondary_engines']+['webkit','firefox']):
                for w in (390,1280):
                    for theme in matrix['themes']:add(page,engine,w,theme,True)
            layout=page.get('layout_contract') if isinstance(page.get('layout_contract'),dict) else {}
            breakpoints=layout.get('breakpoints',[900])
            for w in sorted({int(b)+delta for b in breakpoints for delta in (-1,0,1) if int(b)+delta>=320}):
                for theme in matrix['themes']:add(page,'chromium',w,theme,True)
            for theme in matrix['themes']:add(page,'chromium',844,theme,True,stress='landscape',height=390)
        # No guessed score mapping: mandatory applicability resolution, then fixture cases.
        score=page.get('score_contract')
        if isinstance(score,dict) and score.get('selectors'):
            for state in SPORT_STATES:
                for w in (390,1280):
                    for theme in matrix['themes']:add(page,'chromium',w,theme,True,state)
        requirements.append({'page_type_id':page['page_type_id'],
            'layout_contract':page.get('layout_contract','unknown: identify critical components, overlap pairs and legitimate scroll regions'),
            'required_checks':policy['required_checks'],
            'score_contract':score or 'unknown: resolve fields/states/selectors before sports acceptance',
            'search_contract':page.get('search_contract') or 'unknown',
            'pagination_contract':page.get('pagination_contract','unknown'),
            'keyword_policy':page.get('keyword_policy','unknown: no density/length rule invented'),
            'function_checks':['all current-page internal href targets and representative browser clicks',
                'all visible controls inventoried; actual effect checked or explicitly unresolved',
                'theme toggle/reload/cross-page/storage-failure','search Enter/button/Chinese/special/empty/no-result/detail/pagination-if-supported',
                'navigation open/close/Escape/focus/breakpoint/scroll','goto-top click/keyboard/overlap','existing filters/pagination'],
            'status':'needs_review'})
        for w in (390,1280):
            for theme in matrix['themes']:
                reviews.append({'page_type_id':page['page_type_id'],'width':w,'theme':theme,'visual':'needs_review','seo':'needs_review','trigger':'only checks not resolved by evidence-backed tools'})
    return {'version':3,'policy_version':policy['version'],'review_mode':'tools_first','excluded_pages':excluded,'page_scope':page_scope,'required_checks':policy['required_checks'],'input_hash':stamp,'template_id':task.get('target_template_id') or task['reference_template_id'],
            'cases':cases,'page_requirements':requirements,'reviews':reviews,
            'matrix_source':'task browser_matrix + PRD key-page supplemental checks; first-pass z results are not full acceptance',
            'states':{'ai_review_completed':False,'human_review':'pending','deployed':False,'bing_crawl_observed':False}}

def collect_http(url,out):
    """Capture actual HTTP bytes separately from DOM. Redact potentially secret headers."""
    parsed=urlsplit(url)
    if parsed.scheme not in ('http','https') or parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Only explicit local preview origins are probed by this command')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    r=requests.get(url,timeout=25,allow_redirects=False)
    # No Werkzeug error locals in the persisted response.
    omitted=r.status_code>=500
    (out/'http-body.html').write_bytes(b'<!-- Server error body intentionally omitted -->' if omitted else r.content)
    meta={'kind':'http_response','url':url,'status':r.status_code,'body_omitted':omitted,
          'headers':{k:v for k,v in r.headers.items() if k.lower() not in ('set-cookie','authorization','proxy-authorization') and not any(s in k.lower() for s in ('token','secret','key'))},
          'body_sha256':digest(out/'http-body.html'),'requests_version':requests.__version__}
    save_json(out/'http-response.json',meta)
    return meta

def html_summary(text,headers=None):
    soup=BeautifulSoup(text,'html.parser')
    def content(name):
        x=soup.select_one(f'meta[name="{name}"]');return x.get('content') if x else None
    ld=[]
    for node in soup.select('script[type="application/ld+json"]'):
        try:ld.append({'syntax':'valid','value':json.loads(node.get_text())})
        except ValueError:ld.append({'syntax':'invalid'})
    return {'title':soup.title.get_text() if soup.title else None,'description':content('description'),'keywords':content('keywords'),
            'headings':[{'level':x.name,'text':x.get_text(' ',strip=True)} for x in soup.select('h1,h2,h3,h4,h5,h6')],
            'canonical':[x.get('href') for x in soup.select('link[rel=canonical]')],
            'robots_meta':content('robots'),'x_robots_tag':next((v for k,v in (headers or {}).items() if k.lower()=='x-robots-tag'),None),
            'links':[{'href':x.get('href'),'text':x.get_text(' ',strip=True),'operation':x.get('role')=='button' or x.get('aria-controls') is not None} for x in soup.select('a')],
            'images':[{'src':x.get('src'),'alt':x.get('alt')} for x in soup.select('img')],
            'semantic_counts':{name:len(soup.select(name)) for name in ('main','nav','header','footer','article','section','table','th')},
            'jsonld':ld,'body_excerpt':soup.body.get_text(' ',strip=True)[:1200] if soup.body else ''}

def result_record(case,rule,status,expected,actual,evidence,owner='template',severity='P1',selector=None):
    return {**{k:case.get(k) for k in ('case_id','page_type_id','width','theme','data_state','environment')},
            'rule_id':rule,'status':status,'expected':expected,'actual':actual,'severity':severity,
            'owner_layer':owner,'selector':selector,'evidence_paths':evidence,'baseline_or_regression':'unclassified'}

def assess(plan,records,run,current_hash,reviews=None):
    """Fail closed on incomplete, stale or mislabelled captures; no fake final PASS."""
    run=Path(run); invalid=[]; valid={};expected={c['case_id']:c for c in plan['cases']}
    policy=read_json(ROOT/'config/acceptance-policy.json')
    policy_mismatch=plan.get('version',0)>=3 and (plan.get('policy_version')!=policy['version'] or plan.get('required_checks')!=policy['required_checks'])
    for record in records:
        cid=record.get('case_id');error=None
        if cid not in expected:error='unexpected case'
        elif cid in valid:error='duplicate case'
        elif record.get('input_hash')!=current_hash or plan['input_hash']!=current_hash:error='stale input'
        elif record.get('environment')!=expected[cid]['environment']:error='environment mismatch'
        elif record.get('status') not in ('pass','fail','blocked','needs_review','not_applicable'):error='invalid status'
        elif record.get('status')=='not_applicable' and not record.get('reason'):error='N/A without rationale'
        elif record.get('status') in ('pass','needs_review'):
            required=['http','dom','screenshot'] if expected[cid]['javascript'] else ['http','nojs_dom','screenshot']
            artifacts=record.get('artifacts',{})
            for key in required:
                a=artifacts.get(key,{})
                p=run/a.get('path','')
                if not a.get('path') or not inside(p,run) or not p.is_file() or a.get('sha256')!=digest(p):error='missing/changed '+key;break
            if artifacts.get('http',{}).get('kind')!='http_response':error='DOM cannot be original HTTP'
            if expected[cid]['theme'] in ('light','dark') and record.get('theme_verified') is not True:error='theme not verified'
        if error:invalid.append({'case_id':cid,'reason':error})
        else:valid[cid]=record
    missing=sorted(expected.keys()-valid.keys())
    review_keys={(x.get('page_type_id'),x.get('width'),x.get('theme')):x for x in (reviews or [])}
    pending=[]; tool_pending=[]; tool_resolved=0
    def checks_valid(checks, tool_only=False):
        for name in plan.get('required_checks',[]):
            check=(checks or {}).get(name,{})
            if check.get('status') not in ('pass','not_applicable') or not check.get('verifier'):return False
            if check['status']=='not_applicable' and not check.get('reason'):return False
            if check.get('method') not in (('tool',) if tool_only else ('tool','ai','human')):return False
            artifacts=check.get('evidence',[])
            if not artifacts:return False
            for artifact in artifacts:
                p=run/artifact.get('path','')
                if not artifact.get('path') or not inside(p,run) or not p.is_file() or artifact.get('sha256')!=digest(p):return False
        return True
    for slot in plan['reviews']:
        key=(slot['page_type_id'],slot['width'],slot['theme']);entry=review_keys.get(key,{})
        matching=[r for r in valid.values() if (r.get('page_type_id'),r.get('width'),r.get('theme'))==key]
        if plan.get('review_mode')=='tools_first' and matching and all(r.get('status') in ('pass','not_applicable') and checks_valid(r.get('checks'),True) for r in matching):
            tool_resolved+=1;continue
        if plan.get('review_mode')=='tools_first' and (not matching or any(r.get('status') in ('fail','blocked') for r in matching)):
            tool_pending.append(slot);continue
        if plan.get('review_mode')=='tools_first' and not entry and not any(r.get('review_triggers') or r.get('tool_review_queue') for r in matching):
            tool_pending.append(slot);continue
        # A review record must name the actual evidence and current input revision.
        evidence=entry.get('evidence',[])
        evidence_ok=bool(evidence) and all((run/p).is_file() and inside(run/p,run) for p in evidence)
        if entry.get('input_hash')!=current_hash or not evidence_ok or not entry.get('reviewer') or entry.get('visual')!='pass' or entry.get('seo')!='pass' or not checks_valid(entry.get('checks')):pending.append(slot)
    unfinished=[x for x in valid.values() if x['status'] not in ('pass','not_applicable')]
    # Function/score/contract checks are separate from geometry and capture status.
    contract_pending=[x['page_type_id'] for x in plan['page_requirements'] if x.get('status')!='verified']
    checks_pending=[r['case_id'] for r in valid.values() if not checks_valid(r.get('checks'))]
    return {'expected':len(expected),'recorded':len(records),'valid':len(valid),'missing':len(missing),'missing_case_ids':missing,
            'plan_stale':plan['input_hash']!=current_hash,'policy_mismatch':policy_mismatch,
            'invalid':invalid,'unfinished':len(unfinished),'review_pending':len(pending)+len(tool_pending),'tool_work_pending':tool_pending,'tool_work_pending_count':len(tool_pending),'tool_resolved_review_slots':tool_resolved,'ai_review_queue':pending,'checks_pending':checks_pending,'contract_pending':contract_pending,
            'checks_pending_count':len(checks_pending),'ai_review_needed':bool(pending),
            'ready_for_human_review':bool(expected) and not (missing or invalid or unfinished or pending or tool_pending or checks_pending or contract_pending or policy_mismatch or plan['input_hash']!=current_hash),
            'human_review':'pending','deployed':False,'bing_crawl_observed':False}

def write_ledger(plan,out):
    out=Path(out);save_json(out/'acceptance-plan.json',plan)
    save_json(out/'review-ledger.json',{'input_hash':plan['input_hash'],'reviews':plan['reviews']})
    lines=['# 半自动验收计划','',f"模板 {plan['template_id']}；计划用例 {len(plan['cases'])}；工具未覆盖时的复核槽 {len(plan['reviews'])}。",
           '计划不是执行结果。未运行/缺样例/契约未知都不能通过。机器人接口未启用。','', '|页面|输入与样例|状态|','|---|---|---|']
    for p in plan['page_requirements']:lines.append('|'+p['page_type_id']+'|比分/搜索/分页/关键词契约见 JSON|needs_review|')
    (out/'acceptance-plan.md').write_text('\n'.join(lines),encoding='utf-8')
