"""Generate launch metadata from approved template capabilities, then require Leo review."""
import hashlib
import json
import re
from core import ROOT,read_json

def generate_tdk(keyword,template_id='r62'):
    policy=read_json(ROOT/'config/tdk-policy.json')
    if template_id!=policy['template_id']:raise ValueError('No TDK capability policy for target template')
    keyword=keyword.strip()
    if not keyword or keyword[0] in '=+-@' or any(x in keyword for x in '\t\r\n$<>'):raise ValueError('Unsafe or missing assigned keyword')
    index=int(hashlib.sha256(keyword.encode()).hexdigest()[:8],16)%len(policy['title_patterns'])
    result={'template':template_id,'title':policy['title_patterns'][index].format(keyword=keyword),
            'description':policy['description_patterns'][index].format(keyword=keyword),
            'keywords':','.join(dict.fromkeys([keyword,*policy['keyword_terms']])),
            'reviewer':policy['requires_review_by'],'review_status':'pending','policy_version':policy['version']}
    for field in ('title','description','keywords'):
        if keyword not in result[field] or any(x in result[field] for x in policy['forbidden_claims']):raise ValueError('TDK policy violation')
    result['revision']=hashlib.sha256(json.dumps({k:result[k] for k in ('template','title','description','keywords')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return result

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
        # Reference sheet E:H is not a write target or the source of the approved local copy.
        draft=dict(item.get('tdk') or generate_tdk(row['keyword']))
        entries.append({'domain':item['domain'],'row':row['row'],'tdk':draft})
    return entries


def require_leo_approval(item):
    review=item.get('leo_review') or {}
    if review.get('status')!='approved' or review.get('reviewer')!='Leo' or not review.get('evidence'):
        raise ValueError('Leo review is required before site launch')
    draft=item.get('tdk') or {}
    actual=hashlib.sha256(json.dumps({k:draft.get(k) for k in ('template','title','description','keywords')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if review.get('revision')!=draft.get('revision') or draft.get('revision')!=actual:raise ValueError('TDK changed after approval')

def build_script_row(row,draft):
    """Reproduce verified Bing sheet Q3/Q100 formula without writing any cells."""
    cells=row['cells']
    if len(cells)<16:raise ValueError('Reference row is incomplete')
    for label,index in [('AF1',9),('服务器',12),('IP',13)]:
        if not cells[index].strip():raise ValueError(label+'缺失，需核实采购配置')
    for name,limit in [('title',180),('description',500),('keywords',180)]:
        if not draft.get(name) or len(draft[name].encode('utf-16-le'))//2>=limit:
            raise ValueError(name+'不符合参考表公式的必填/长度限制')
    match=re.fullmatch(r'([A-Za-z]+)([0-9]+)',draft.get('template',''))
    if not match:raise ValueError('Invalid template identifier')
    template=match[1].lower()+str(int(match[2]))
    trim=lambda value:re.sub(' +',' ',value.strip(' '))
    fields=[trim(row['domain']),trim(row['keyword']),trim(draft['title']),trim(draft['description']),trim(draft['keywords']),template,
            cells[13],cells[9],'',cells[8],cells[10],cells[12],cells[14],cells[15]]
    if not fields[0] or not fields[1]:raise ValueError('Domain or assigned keyword missing')
    if any(any(c in value for c in '$\r\n') for value in fields):
        raise ValueError('字段包含未定义转义的分隔符或换行，不能生成上站脚本')
    return '$'.join(fields)


def backend_script(domains,snapshot):
    if not domains:raise ValueError('No confirmed domains to prefill')
    if len({d['domain'] for d in domains})!=len(domains):raise ValueError('Duplicate batch domains')
    lines=[]
    for item in domains:
        matches=[r for r in snapshot['launch'] if r['domain']==item['domain']]
        if len(matches)!=1 or matches[0]['owner']!='Pony':raise ValueError('Backend payload owner/domain mismatch')
        if any(r['domain']==item['domain'] for r in snapshot.get('pending',[])):raise ValueError('Purchase transition ambiguous')
        row=matches[0]
        if row['keyword']!=item['keyword']:raise ValueError('Assigned launch keyword changed; review required')
        require_leo_approval(item)
        lines.append(build_script_row(row,item['tdk']))
    return '\r\n'.join(lines)
