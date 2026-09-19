"""Usage: .venv/Scripts/python.exe workflow.py --help"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'src'))
import argparse
import json
import html
from core import *
from audit import run_audit
from generate import generate
from checks import html_checks

def report(task,out):
    contract=read_json(out/'page-contract.json')
    matrix=[]
    for p in out.glob('*/matrix-results.json'):
        matrix += [dict(r,matrix_directory=p.parent.name) for r in read_json(p)]
    raw=[]
    for p in (out/'raw-responses').glob('*.html'):
        headers=read_json(p.with_suffix('.json'))
        if headers['status']==200:
            raw += [dict(x,evidence_paths=[p.relative_to(out).as_posix()],environment='real_app') for x in html_checks(p.read_text(encoding='utf-8'),headers['headers'])]
    results={'counts':contract['counts'],'matrix':{s:sum(r['status']==s for r in matrix) for s in ('pass','fail','blocked','needs_review')},
             'raw_html_findings':raw,'matrix_total':len(matrix),'formal_template_id':task['target_template_id'],
             'states':{'workflow_implemented':'partial','fixture_verified':'partial','real_app_verified':'reference_only',
                       'automated_quality_passed':False,'ai_review_completed':False,'human_review':'pending','deployed':False,'bing_crawl_observed':False}}
    save_json(out/'report.json',results)
    lines=['# 工作流实施报告','',json.dumps({k:v for k,v in results.items() if k!='raw_html_findings'},ensure_ascii=False,indent=2),
           '\n目标编号未分配；真实 r62 只读基线不是新模板真实联调。缺失页面/样例仍阻断。没有部署或 Bing 抓取证据。',
           '\n全部规则实现覆盖见 rule-coverage.json；未实现规则不返回 PASS。']
    (out/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    cards=['<!doctype html><meta charset="utf-8"><title>模板证据索引</title><style>body{font:16px system-ui;margin:24px;background:#f4f6f8}article{background:white;padding:16px;margin:12px}img{width:280px;max-height:400px;object-fit:contain;object-position:top}code{word-break:break-all}.blocked,.fail{border-left:6px solid #b42318}</style><h1>模板逐页证据索引</h1><p>真实参考基线与外部草稿分开；截图存在不代表 AI 已复核。无正式编号，未部署、未观测 Bing。</p>']
    for page in contract['pages']:
        cards.append('<h2>'+html.escape(page['page_type_id'])+'</h2>')
        page_results=[r for r in matrix if r.get('page_type_id')==page['page_type_id']]
        if not page_results:cards.append('<article class="blocked">blocked：没有执行截图矩阵</article>')
        for r in page_results:
            cards.append('<article class="'+r['status']+'">'+html.escape(str({k:r.get(k) for k in ('environment','engine','width','theme','javascript','status','reason')})))
            for evidence in r.get('evidence_paths',[]):
                # Matrix directories retain their own provenance; avoid linking nonexistent images.
                found=[out/r['matrix_directory']/evidence]
                for path in found:
                    if not path.is_file():continue
                    link=path.relative_to(out).as_posix()
                    if path.suffix=='.png':cards.append(f'<a href="{link}"><img loading="lazy" src="{link}"></a>')
            cards.append('</article>')
    (out/'review-index.html').write_text('\n'.join(cards),encoding='utf-8')
    registry=read_json(ROOT/'config/rules.json')
    automated={'PATH-01','PATH-02','PATH-03','CON-05','SEO-01','SEO-02','SEO-04','SEO-06','SEO-10','SEO-11','QA-01','QA-02','QA-03','QA-04','QA-05','QA-07'}
    save_json(out/'rule-coverage.json',[{'id':r['id'],'handler_implemented':r['id'] in automated,
        'scope':'partial predicates; see tests and actual findings' if r['id'] in automated else 'not implemented; needs_review/blocked',
        'actual_run_status':'needs_review'} for r in registry['rules']])
    (out/'handoff.md').write_text('# 交付边界\n\n业务目录没有生成目标模板；没有目标编号。工具源代码、测试和草稿仅在外部目录。\n查看 report.md / review-index.html / rule-coverage.json，不得把夹具通过等同真实项目验收。\n待人工验收；未推送、未部署、未写表、未采购、未观测 Bing。\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description='Local-only Jinja workflow; no remote actions')
    parser.add_argument('command',choices=['validate','audit','generate','check-boundary','report','resume','browser','plan-acceptance','assess-acceptance'])
    parser.add_argument('--task',default='config/task.example.json')
    parser.add_argument('--run',default='runs/bootstrap')
    parser.add_argument('--design',choices=['editorial','rail'])
    parser.add_argument('--fixture-dir')
    parser.add_argument('--contract')
    args=parser.parse_args(); task=validate_task(args.task)
    out=Path(args.run).resolve()
    if not inside(out,ROOT/'runs'):raise ValueError('Run output must be under external runs/')
    out.mkdir(parents=True,exist_ok=True)
    inputs=[ROOT/'PRD.md',ROOT/'config/rules.json',Path(args.task),*list((ROOT/'src').glob('*.py')),
            *list((Path(task['repo_root'])/'templates'/task['reference_template_id']).rglob('*.html')),
            Path(task['repo_root'])/'run.py']
    current=fingerprint(task,inputs)
    if args.command=='validate':print('Task schema and workspace boundaries valid');return
    if args.command=='resume':
        old=read_json(out/'checkpoint.json') if (out/'checkpoint.json').exists() else {}
        print(json.dumps({'can_reuse':resume_valid(old,current),'reason':'Input/source/contract hashes must match; otherwise rerun'},ensure_ascii=False));return
    if args.command in ('plan-acceptance','assess-acceptance'):
        from acceptance import input_stamp,make_plan,write_ledger,assess
        contract_path=Path(args.contract or task.get('page_contract_path') or out/'page-contract.json')
        stamp=input_stamp(task,contract_path)
        if args.command=='plan-acceptance':
            if (out/'acceptance-plan.json').exists():raise ValueError('Preserve previous plan; use a fresh run directory')
            plan=make_plan(task,read_json(contract_path),stamp);write_ledger(plan,out)
            print(json.dumps({'planned_cases':len(plan['cases']),'review_slots':len(plan['reviews']),'executed':0}))
        else:
            plan=read_json(out/'acceptance-plan.json')
            records=read_json(out/'capture-records.json') if (out/'capture-records.json').exists() else []
            reviews=read_json(out/'review-ledger.json').get('reviews',[])
            result=assess(plan,records,out,stamp,reviews);save_json(out/'acceptance-status.json',result)
            print(json.dumps({k:v for k,v in result.items() if k not in ('missing_case_ids','invalid','contract_pending','checks_pending','ai_review_queue','tool_work_pending')}))
        return
    if args.command=='audit':
        if not (out/'business-before.json').exists():save_json(out/'business-before.json',baseline(task['repo_root']))
        save_json(out/'task-resolved.json',task);run_audit(task,out)
    elif args.command=='generate':
        if not args.design:raise ValueError('--design required')
        contract=read_json(out/'page-contract.json')
        design=read_json(ROOT/'config'/('design-'+args.design+'.json'))
        Draft202012Validator(read_json(ROOT/'schemas/design.schema.json')).validate(design)
        print(generate(task,contract,args.design,design))
    elif args.command=='check-boundary':
        result=compare_baseline(read_json(out/'business-before.json'),baseline(task['repo_root']))
        save_json(out/'changed-files.json',result);print(json.dumps(result,ensure_ascii=False))
        if result['status']!='pass':raise SystemExit(2)
    elif args.command=='browser':
        from browser_checks import execute_matrix
        name=args.design or 'real-baseline'
        execute_matrix(task,read_json(out/'page-contract.json'),out/name,args.fixture_dir,args.design)
    elif args.command=='report':report(task,out)
    save_json(out/'checkpoint.json',{'input_hash':current,'last_command':args.command})
    print(args.command+' complete (not a quality PASS)')

if __name__=='__main__':main()
