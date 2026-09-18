"""Hash-bound external repairs. Scope/tests/rules cannot be altered by a repair plan."""
from pathlib import Path
from core import ROOT,read_json,save_json,digest,inside

def apply_repair(plan_path):
    plan=read_json(plan_path)
    root=(ROOT/'drafts'/plan['design']).resolve()
    if root.parent!=ROOT/'drafts':raise ValueError('Invalid design path')
    history_path=root/'repair-history.json'
    history=read_json(history_path) if history_path.exists() else []
    if len(history)>=3:raise ValueError('Three repair rounds reached')
    for edit in plan['edits']:
        path=root/edit['path']
        if not inside(path,root) or path.suffix not in ('.css','.js','.html') or path.is_symlink():raise ValueError('Invalid repair scope')
        if digest(path)!=edit['sha256_before']:raise ValueError('Stale repair input')
        if not edit.get('rule_id') or not edit.get('evidence'):raise ValueError('Evidence-linked repair required')
    for edit in plan['edits']:
        path=root/edit['path'];old=path.read_text(encoding='utf-8')
        if edit['old'] not in old:raise ValueError('Repair anchor not found')
        backup=root/'repair-evidence'/str(len(history)+1)/edit['path'];backup.parent.mkdir(parents=True,exist_ok=True);backup.write_text(old,encoding='utf-8')
        path.write_text(old.replace(edit['old'],edit['new']),encoding='utf-8')
    history.append({'plan':plan,'round':len(history)+1,'requires_full_regression':True,'status':'needs_review'})
    save_json(history_path,history)
    return history[-1]
