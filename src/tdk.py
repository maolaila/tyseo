"""Generate launch metadata from approved template capabilities, then require Leo review."""
import hashlib
import json
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

def prepare_updates(domains,snapshot):
    updates=[];existing=[]
    for item in domains:
        if item.get('status') in ('verified','submitting','submission_unknown','verifying'):continue
        matches=[r for r in snapshot['launch'] if r['domain']==item['domain'].lower()]
        pending=[r for r in snapshot['pending'] if r['domain']==item['domain'].lower()]
        if not matches:continue
        if len(matches)!=1 or pending or matches[0]['owner']!='Pony':raise ValueError('Purchase/owner/row ambiguity; refusing metadata write')
        row=matches[0]
        if row['keyword']!=item['keyword']:raise ValueError('Assigned launch keyword changed; review required')
        desired=generate_tdk(row['keyword'])
        values=[desired[k] for k in ('template','title','description','keywords')]
        old=row['cells'][4:8]
        if any(old):
            if old==values:existing.append({'domain':item['domain'],'row':row['row'],'tdk':desired})
            else:raise ValueError('Existing template/TDK differs; preserve human edits')
        else:updates.append({'domain':item['domain'],'row':row['row'],'before':old,'values':values,'tdk':desired})
    return updates,existing

def require_leo_approval(item):
    review=item.get('leo_review') or {}
    if review.get('status')!='approved' or review.get('reviewer')!='Leo' or not review.get('evidence'):
        raise ValueError('Leo review is required before site launch')
    if review.get('revision')!=(item.get('tdk') or {}).get('revision'):raise ValueError('TDK changed after approval')

def backend_script(domains,snapshot):
    if not domains:raise ValueError('No confirmed domains to prefill')
    lines=[]
    for item in domains:
        matches=[r for r in snapshot['launch'] if r['domain']==item['domain']]
        if len(matches)!=1 or matches[0]['owner']!='Pony':raise ValueError('Backend payload owner/domain mismatch')
        if any(r['domain']==item['domain'] for r in snapshot.get('pending',[])):raise ValueError('Purchase transition ambiguous')
        row=matches[0];draft=item.get('tdk') or {}
        expected=[draft.get(k) for k in ('template','title','description','keywords')]
        if row['cells'][4:8]!=expected:raise ValueError('请先确认回填上站表，或重新核对已修改的TDK')
        script=row['cells'][16].strip();parts=script.split('$')
        if '\r' in script or '\n' in script or len(parts)<14:raise ValueError('上站表尚未生成有效的单行脚本')
        if parts[:6]!=[item['domain'],item['keyword'],draft['title'],draft['description'],draft['keywords'],draft['template']]:
            raise ValueError('生成脚本与工作台确认内容不一致')
        if row['cells'][12].strip()!='s213016':raise ValueError('本批分配服务器不是当前已确认后台，需先核实地址')
        lines.append(script)
    return '\r\n'.join(lines)
