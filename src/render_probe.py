"""External fixture renderer using captured route context. Never serves a replacement app.

Invoked with the business Python and -B. The render wrapper exists only in this short-lived
test process, not in the user's server. Results are labelled captured_context fixture.
"""
import sys
import os
import json
from pathlib import Path
from jinja2 import ChoiceLoader,FileSystemLoader

def main():
    repo,out,contract_path=sys.argv[1:4]
    repo=Path(repo);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    sys.path.insert(0,str(repo));os.chdir(repo)
    import run
    original=run.render_template
    captured={}
    def capture(name,*args,**kwargs):
        if isinstance(name,str) and name.startswith('r62/'):
            captured['name']=name;captured['context']=kwargs
        return original(name,*args,**kwargs)
    run.render_template=capture
    contract=json.loads(Path(contract_path).read_text(encoding='utf-8'))
    records=[]
    for page in contract['pages']:
        urls=page['sample_urls']
        if not urls:
            records.append({'page_type_id':page['page_type_id'],'status':'blocked','reason':'No real sample URL'});continue
        captured.clear()
        try:
            with run.app.test_client() as client:
                try:
                    response=client.get(urls[0])
                except Exception:
                    if 'context' not in captured: raise
                    response=None  # original missing template, captured data is still fixture-only
                if 'context' not in captured or captured['name']!=page['entry_template']:
                    records.append({'page_type_id':page['page_type_id'],'status':'blocked','reason':'Expected template not reached'});continue
                ctx=captured['context']
                # Store only type observations, never complete configuration or arbitrary values.
                types={k:type(v).__name__ for k,v in ctx.items()}
                for design in ('editorial','rail'):
                    root=out.parents[1]/'drafts'/design
                    env=run.app.jinja_env.overlay(loader=ChoiceLoader([FileSystemLoader(str(root/'templates')),run.app.jinja_loader]))
                    try:
                        with run.app.test_request_context(urls[0]):
                            run.app.update_template_context(ctx)
                            html=env.get_template(captured['name'].replace('r62/','draft/')).render(ctx)
                        target=out/design/(page['page_type_id']+'.html');target.parent.mkdir(exist_ok=True)
                        target.write_text(html,encoding='utf-8')
                        records.append({'page_type_id':page['page_type_id'],'design':design,'environment':'fixture','data_origin':'captured_existing_route_context',
                                        'status':'pass','observed_value_types':types,'source_url':urls[0],'file':str(target),'original_status':response.status_code if response else 500})
                    except Exception as e:
                        records.append({'page_type_id':page['page_type_id'],'design':design,'status':'blocked','reason':type(e).__name__})
        except Exception as e:
            records.append({'page_type_id':page['page_type_id'],'status':'blocked','reason':type(e).__name__})
        (out/'render-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    (out/'render-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
