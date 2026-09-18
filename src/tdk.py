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

def backend_script(domains,snapshot):
    if not domains:raise ValueError('No confirmed domains to prefill')
    lines=[]
    for item in domains:
        matches=[r for r in snapshot['launch'] if r['domain']==item['domain']]
        if len(matches)!=1 or matches[0]['owner']!='Pony':raise ValueError('Backend payload owner/domain mismatch')
        if any(r['domain']==item['domain'] for r in snapshot.get('pending',[])):raise ValueError('Purchase transition ambiguous')
        row=matches[0];draft=item.get('tdk') or {}
        require_leo_approval(item)
        script=row['cells'][16].strip();parts=script.split('$')
        if not script:raise ValueError('参考表没有现成脚本，后台资料格式待核实；无需编辑参考表')
        if '\r' in script or '\n' in script or len(parts)<14:raise ValueError('参考脚本格式不明确，不能猜测后台资料')
        if parts[:2]!=[item['domain'],item['keyword']]:raise ValueError('参考脚本域名或关键词不一致')
        local=[item['domain'],item['keyword'],draft['title'],draft['description'],draft['keywords'],draft['template']]
        if any(any(c in value for c in '$\r\n') for value in local):raise ValueError('TDK contains unsupported script delimiters')
        # Overlay only the reviewed local metadata; never mutate the reference row.
        script='$'.join(local+parts[6:])
        # The user-confirmed admin entry is distinct from the assigned deployment server.
        if not row['cells'][12].strip():raise ValueError('本批分配服务器缺失，需先核实采购配置')
        lines.append(script)
    return '\r\n'.join(lines)
