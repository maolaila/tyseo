"""Validate AI-authored launch metadata against the current assignment."""
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from core import ROOT,read_json,save_json

REFERENCE_BOOK='1-3DvtAhJQu83G9fA1TWrEZIKiosOzvwDWYknEFXKGJ0'
TDK_FIELDS=('title','description','keywords')

def _revision(draft):
    contents={k:draft[k] for k in ('template',*TDK_FIELDS)}
    if draft.get('policy_version',1)>=2:
        contents.update({k:draft[k] for k in ('batch_id','business_date','assignment','competitors')})
    return hashlib.sha256(json.dumps(contents,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def _normal(value):
    return re.sub(r'[\W_]+','',unicodedata.normalize('NFKC',value).casefold())

def _fingerprint(value):
    return hashlib.sha256(_normal(value).encode()).hexdigest()

def generate_tdk(keyword,template_id='r62',*,title=None,description=None,keywords=None,assignment=None,competitors=None,batch_id=None,business_date=None):
    """Register freshly authored copy; never synthesize it from fixed patterns."""
    policy=read_json(ROOT/'config/tdk-policy.json')
    if template_id!=policy['template_id']:raise ValueError('No TDK capability policy for target template')
    keyword=keyword.strip()
    if not keyword or keyword[0] in '=+-@' or any(x in keyword for x in '\t\r\n$<>'):raise ValueError('Unsafe or missing assigned keyword')
    if not batch_id or not business_date:raise ValueError('每次上站需要独立批次与日期')
    assignment=assignment or {}
    if not isinstance(assignment,dict):raise ValueError('关键词分组来源格式无效')
    if assignment.get('owner')!='Pony' or not assignment.get('group') or assignment.get('business_date')!=business_date:
        raise ValueError('缺少当次 Pony 关键词分组，不能沿用旧分组或默认 all')
    if REFERENCE_BOOK not in assignment.get('workbook_url','') or assignment.get('sheet')!='bing体育品牌词':
        raise ValueError('需要本次关键词表的分组来源')
    competitors=competitors or []
    if not competitors or any(not isinstance(x,dict) or urlsplit(x.get('url','')).scheme not in ('http','https') or x.get('checked_on')!=business_date for x in competitors):
        raise ValueError('需要当次核对的竞争网站与日期')
    result={'template':template_id,'title':title,'description':description,'keywords':keywords,
            'assignment':assignment,'competitors':competitors,'batch_id':batch_id,'business_date':business_date,
            'review_status':'not_required','policy_version':2}
    for field in TDK_FIELDS:
        value=result[field]
        if not isinstance(value,str) or not value.strip() or keyword not in value or value[0] in '=+-@' or any(x in value for x in '\t\r\n$<>'):
            raise ValueError('TDK 缺少分配词或含不安全字符: '+field)
        if any(x in value for x in policy['forbidden_claims']):raise ValueError('TDK 包含未经证实的宣称: '+field)
    for source in competitors:
        if _normal(title)==_normal(source.get('title','')) or _normal(description)==_normal(source.get('description','')):
            raise ValueError('TDK 不得直接复制竞争网站文案')
    result['revision']=_revision(result)
    return result

def require_current_review(item):
    draft=item.get('tdk') or {}
    source_fields=('batch_id','business_date','assignment','competitors') if draft.get('policy_version',1)>=2 else ()
    if not all(isinstance(draft.get(k),str) and draft[k] for k in ('template',*TDK_FIELDS)) or any(k not in draft for k in source_fields) or draft.get('revision')!=_revision(draft):
        raise ValueError('TDK 内容或版本已变化')
    if draft.get('policy_version',1)>=2:
        assignment=draft.get('assignment') or {}
        if assignment.get('owner')!='Pony' or not assignment.get('group') or assignment.get('business_date')!=draft.get('business_date') or REFERENCE_BOOK not in assignment.get('workbook_url','') or assignment.get('sheet')!='bing体育品牌词':
            raise ValueError('当次 Pony 分组来源无效')
        if not draft.get('competitors') or any(x.get('checked_on')!=draft.get('business_date') for x in draft['competitors']):
            raise ValueError('缺少当次竞争网站证据')
    if item.get('leo_review_required') or item.get('leo_review'):
        require_leo_approval(item)

def ensure_unique_tdks(domains,history=()):
    seen={}
    for item in history:
        draft=item.get('tdk') or {}
        for field in TDK_FIELDS:
            value=(item.get('field_hashes') or {}).get(field)
            if not value and isinstance(draft.get(field),str):value=_fingerprint(draft[field])
            if not value:continue
            key=(field,value)
            seen.setdefault(key,item.get('domain','未知域名'))
    for item in domains:
        draft=item.get('tdk') or {}
        for field in TDK_FIELDS:
            if not isinstance(draft.get(field),str):continue
            key=(field,_fingerprint(draft[field]))
            if key in seen:raise ValueError(f'{field} 与此前上站文案重复：{seen[key]}、{item.get("domain","未知域名")}')
            seen[key]=item.get('domain','未知域名')

def prior_tdks(current_state_path):
    current=Path(current_state_path).resolve()
    root=current.parent.parent
    if root.name!='site-launch':return []
    items=[]
    current_batch=read_json(current).get('batch_id')
    ledger=ROOT/'data/tdk-fingerprints.json'
    if ledger.exists():
        items.extend(x for x in read_json(ledger).get('entries',[]) if x.get('batch_id')!=current_batch)
    for path in root.glob('*/state.json'):
        if path.resolve()==current:continue
        items.extend(x for x in read_json(path).get('domains',[]) if x.get('tdk'))
    return items

def record_tdk_history(domains,batch_id):
    """Persist only fingerprints so another machine can reject repeated copy."""
    path=ROOT/'data/tdk-fingerprints.json'
    data=read_json(path) if path.exists() else {'schema_version':1,'entries':[]}
    changed=False
    for item in domains:
        draft=item.get('tdk') or {}
        if not all(isinstance(draft.get(field),str) for field in TDK_FIELDS):continue
        entry={'batch_id':batch_id,'domain':item['domain'],
               'field_hashes':{field:_fingerprint(draft[field]) for field in TDK_FIELDS}}
        existing=next((x for x in data['entries'] if x['batch_id']==batch_id and x['domain']==item['domain']),None)
        if existing and existing!=entry:raise ValueError('历史上站文案与当前批次冲突，停止更新')
        if not existing:
            data['entries'].append(entry)
            changed=True
    if changed or not path.exists():
        path.parent.mkdir(parents=True,exist_ok=True)
        save_json(path,data)

def prepare_drafts(domains,snapshot):
    entries=[]
    for item in domains:
        if item.get('status') in ('verified','submitting','submission_unknown','verifying'):continue
        matches=[r for r in snapshot['launch'] if r['domain']==item['domain'].lower()]
        if not matches:continue
        if len(matches)!=1 or any(r['domain']==item['domain'].lower() for r in snapshot['pending']) or matches[0]['owner']!='Pony':
            raise ValueError('Purchase/owner/row ambiguity; reference cannot be trusted')
        row=matches[0]
        if row['keyword']!=item['keyword']:raise ValueError('Assigned launch keyword changed; review required')
        # Keep the reviewed local copy until the explicit action writes it to the launch sheet.
        draft=dict(item['tdk']) if item.get('tdk') else None
        entries.append({'domain':item['domain'],'row':row['row'],'tdk':draft})
    return entries


def require_leo_approval(item):
    review=item.get('leo_review') or {}
    if review.get('status')!='approved' or review.get('reviewer')!='Leo' or not review.get('evidence'):
        raise ValueError('Leo review is required before site launch')
    draft=item.get('tdk') or {}
    actual=_revision(draft)
    if review.get('revision')!=draft.get('revision') or draft.get('revision')!=actual:raise ValueError('TDK changed after approval')

def plan_sheet_write(domains,snapshot,history=()):
    if not domains or len({d['domain'] for d in domains})!=len(domains):raise ValueError('Empty or duplicate batch')
    ensure_unique_tdks(domains,history)
    updates=[]
    for item in domains:
        matches=[r for r in snapshot['launch'] if r['domain']==item['domain']]
        if len(matches)!=1 or matches[0]['owner']!='Pony':raise ValueError('上站表域名或归属不唯一，停止写入')
        if any(r['domain']==item['domain'] for r in snapshot.get('pending',[])):raise ValueError('采购移表状态不明确')
        row=matches[0]
        if row['keyword']!=item['keyword']:raise ValueError('分配词发生变化，需重新核对')
        if item.get('status') in ('verified','submitting','submission_unknown','verifying'):raise ValueError('已有上站记录，需先核对状态，不能重复处理')
        require_current_review(item)
        for name,limit in [('title',180),('description',500),('keywords',180)]:
            if len(item['tdk'][name].encode('utf-16-le'))//2>=limit:
                raise ValueError(name+'超出上站表长度限制')
        if not re.fullmatch(r'[A-Za-z]+[0-9]+',item['tdk']['template']):
            raise ValueError('模板编号格式无效')
        values=[item['tdk'][k] for k in ('template','title','description','keywords')]
        if any(value.startswith(('=','+','-','@')) or any(c in value for c in '\t\r\n') for value in values):raise ValueError('表格字段包含不安全的公式或分隔符')
        before=row['cells'][4:8]
        if any(old and old!=new for old,new in zip(before,values)):raise ValueError('表格已有不同模板或TDK，已保留，请先核对')
        if before!=values:updates.append({'domain':item['domain'],'row':row['row'],'before':before,'values':values,'before_cells':row['cells'][:16]})
    return updates
