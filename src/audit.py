"""Read-only static audit and bounded real HTTP probes. No application imports."""
import ast
import re
import json
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, meta, nodes
from werkzeug.routing import Map, Rule, BaseConverter
from core import save_json, git

class RegexConverter(BaseConverter):
    def __init__(self, url_map, expression):
        super().__init__(url_map)
        self.regex=expression

def extract(repo, reference):
    repo=Path(repo)
    source=(repo/'run.py').read_text(encoding='utf-8-sig')
    tree=ast.parse(source)
    routes=[]
    for func in tree.body:
        if not isinstance(func,(ast.FunctionDef,ast.AsyncFunctionDef)): continue
        patterns=[]
        for d in func.decorator_list:
            if isinstance(d,ast.Call) and isinstance(d.func,ast.Attribute) and d.func.attr=='route' and d.args and isinstance(d.args[0],ast.Constant):
                patterns.append(d.args[0].value)
        if not patterns: continue
        renders=[]
        for call in ast.walk(func):
            if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id=='render_template' and call.args:
                expr=ast.get_source_segment(source,call.args[0])
                match=re.search(r"(?:\{\}/|"+reference+r"/)([\w/.-]+\.html)",expr)
                if match:
                    renders.append({'entry_template':reference+'/'+match[1], 'source_line':call.lineno,
                                    'variables':{k.arg:ast.unparse(k.value) for k in call.keywords if k.arg}})
        if renders: routes.append({'function':func.name,'route_patterns':patterns,'source_line':func.lineno,'renders':renders})
    graph={}
    env=Environment()
    for p in (repo/'templates'/reference).rglob('*.html'):
        raw=p.read_text(encoding='utf-8-sig')
        try: parsed=env.parse(raw)
        except Exception as e:
            graph[p.relative_to(repo/'templates').as_posix()]={'parse_error':type(e).__name__,'source':p.relative_to(repo).as_posix()}
            continue
        for f in parsed.find_all(nodes.Filter): env.filters.setdefault(f.name, lambda x,*a,**k:x)
        graph[p.relative_to(repo/'templates').as_posix()]={
            'references':list(meta.find_referenced_templates(parsed)),
            'variables':sorted(meta.find_undeclared_variables(parsed)),
            'filters':sorted(set(n.name for n in parsed.find_all(nodes.Filter))),
            'macros':[n.name for n in parsed.find_all(nodes.Macro)],
            'attributes':sorted(set(ast_path(n) for n in parsed.find_all(nodes.Getattr))),
            'assets':sorted(set(re.findall(r'''(?:src|href)=["'](/static/[^"']+)["']''',raw))),
            'source':p.relative_to(repo).as_posix()}
    pages={}
    for route in routes:
        for render in route['renders']:
            name=render['entry_template']
            page=pages.setdefault(name, {'page_type_id':Path(name).stem,'entry_template':name,'route_pattern':[],
                'sample_urls':[], 'required_variables':'unknown: conditional requirements need context inspection',
                'optional_variables':'unknown', 'observed_value_types':{},'data_source':[],
                'canonical_policy':'unknown','indexing_policy':'unknown','data_states':[],
                'navigation_links':[],'pagination_contract':'unknown','search_contract':None,
                'required_content_selectors':['body'],'key_function_selectors':[],
                'baseline_issues':[],'audit_status':'source_only','evidence_file':'route-evidence.json'})
            page['route_pattern']+= [x for x in route['route_patterns'] if x not in page['route_pattern']]
            page['data_source'].append({'function':route['function'],'line':render['source_line'],'bindings':render['variables']})
            page['template_exists']=name in graph
            page['context_dependencies']=graph.get(name,{}).get('variables',[])
            page.update({k:graph.get(name,{}).get(k,[]) for k in ('filters','macros')})
            page['includes_extends']=graph.get(name,{}).get('references',[])
            page['seo_fields']=['website_config.Title','website_config.Description','website_config.Keyword','tdk_seo (where bound)']
            if name not in graph: page['baseline_issues']=['Referenced by backend but missing in r62']
    return routes,graph,list(pages.values())

def ast_path(node):
    if isinstance(node,nodes.Getattr): return ast_path(node.node)+'.'+node.attr
    if isinstance(node,nodes.Name): return node.name
    return '<expression>'

def run_audit(task,out):
    repo=Path(task['repo_root']); out=Path(out); out.mkdir(parents=True,exist_ok=True)
    routes,graph,pages=extract(repo,task['reference_template_id'])
    save_json(out/'route-evidence.json',routes); save_json(out/'dependency-map.json',graph)
    rules=[]; endpoint_pages={}
    for i,route in enumerate(routes):
        endpoint_pages[str(i)]=[x['entry_template'] for x in route['renders']]
        for pattern in route['route_patterns']:
            rules.append(Rule(pattern,endpoint=str(i)))
    mapper=Map(rules,converters={'regex':RegexConverter}).bind('localhost')
    lookup={p['entry_template']:p for p in pages}
    queue=['/','/zuqiu/','/lanqiu/','/search?q=nba','/search','/search?q=%E6%9C%AA%E7%9F%A5%E8%AF%8D']
    seen=set(); captured=set(); attempted=set(); responses=[]
    for depth in range(4):
        next_queue=[]
        for path in queue:
            if path in seen: continue
            seen.add(path)
            try: endpoint,_=mapper.match(urlsplit(path).path)
            except Exception: continue
            names=endpoint_pages[endpoint]
            if all(n in attempted for n in names) and not path.startswith('/search') and path not in ('/zuqiu/','/lanqiu/'): continue
            attempted.update(names)
            try:
                resp=requests.get(urljoin(task['preview_base_url'],path),timeout=18,allow_redirects=False)
                # Never persist Werkzeug debugger pages, which may contain locals/secrets.
                body=resp.text if resp.status_code<500 else '<html><body>Server error: body omitted to protect debugger locals.</body></html>'
                index=len(responses); stem=f'raw-responses/{index:03d}'
                (out/'raw-responses').mkdir(exist_ok=True)
                (out/(stem+'.html')).write_text(body,encoding='utf-8')
                headers={k:v for k,v in resp.headers.items() if k.lower() in ('content-type','x-robots-tag','location','cache-control')}
                save_json(out/(stem+'.json'),{'url':path,'status':resp.status_code,'headers':headers})
                soup=BeautifulSoup(body,'html.parser')
                links=[a.get('href') for a in soup.select('a[href]') if a.get('href','').startswith('/') and not a.get('href','').startswith('//')]
                entry={'path':path,'status':resp.status_code,'pages':names,'evidence':stem+'.html','links':links}
                responses.append(entry)
                for name in names:
                    p=lookup[name]; p['sample_urls'].append(path); p['navigation_links']=links
                    p['audit_status']='http_observed' if resp.status_code==200 else 'blocked'
                    p.setdefault('http_samples',[]).append(entry)
                    if resp.status_code==200: captured.add(name)
                next_queue.extend(links)
            except requests.RequestException as e:
                for name in names: lookup[name]['baseline_issues'].append(type(e).__name__)
        queue=next_queue
    for p in pages:
        if not p['sample_urls']: p['audit_status']='blocked';p['baseline_issues'].append('No real linked sample discovered within bounded crawl; not fabricated')
    search={'method':'GET','route':'/search','parameter':'q','source':'run.py:1075-1112',
            'scope':'allowlisted keywords only; get_search_data_cache_file(keyword,1,50)',
            'empty_input':'redirect /','pagination':'none in audited handler',
            'keyword_echo':'key overwritten with site name before rendering',
            'missing_reference_template':not (repo/'templates'/task['reference_template_id']/'search.html').exists()}
    for p in pages:
        if p['page_type_id']=='search':p['search_contract']=search
    save_json(out/'page-contract.json',{'version':'1','commit':git(repo,'rev-parse','HEAD'),'pages':pages,'search':search,
        'counts':{'jinja_files':len(graph),'rendered_entry_types':len(pages),'missing_entry_files':sum(not p['template_exists'] for p in pages),'http_200_types':len(captured)},
        'discovery_limit':'4 breadth rounds, at most one successful sample per static render candidate; conditional render attribution needs review'})
    save_json(out/'http-probes.json',responses)
    (out/'project-audit.md').write_text('# M0 实际项目审计\n\n'+
        f"Jinja 文件 {len(graph)}；后端静态渲染入口 {len(pages)}；HTTP 200 类型 {len(captured)}。入口列表包含后端引用但 r62 缺失的文件，不能都称为已实现页面。\n\n"+
        'Python 3.10 / Flask 2.1.1 / Jinja 3.1.2（业务 requirements 与既有环境）。启动为现有 run.py。\n'+
        '选择机制：config.py load_dotenv 默认不覆盖进程环境，cache/cache_data.py:191-192 在 development 下用 DEV_MasterID；仅源码确认，未以未分配编号启动。\n'+
        '运行缓存位于既有 LOCAL_CACHE_FOLDER；请求可能增加缓存，此为既有运行副作用；源码与 .env 不修改。\n'+
        'Search: GET /search?q=，受 list_search_allow 白名单限制，r62/search.html 缺失；不能称完整任意关键词搜索。\n'+
        'HeaderJS/FooterJS 与 jQuery/ajs.js 为保留契约。canonical 使用 website_config.Domain + request.path；查询分页的政策待确认，不能擅自修改后端。\n'+
        '属性类型/条件必填字段尚需真实上下文验证；静态 meta 变量不等于必填字段。\n',encoding='utf-8')
    (out/'backend-requests.md').write_text('# 后端/契约待协调\n\n1. 搜索白名单是否为正式能力范围；返回 key 被覆盖为站点名，需确认关键字回显意图。\n2. r62 缺失的后端渲染模板见 page-contract；需确认哪些页面属于新模板必交付范围，不能删分母。\n3. canonical 查询参数及搜索页索引策略待明确。\n4. 无可达真实样例的页面保留 blocked，不伪造 id。\n5. 目标模板编号未分配，正式目录写入/实际目标预览被阻断；外部草稿继续。\n',encoding='utf-8')
    # Keep narrative labels consistent when auditing another existing template.
    if task['reference_template_id']!='r62':
        for name in ('project-audit.md','backend-requests.md'):
            p=out/name;p.write_text(p.read_text(encoding='utf-8').replace('r62',task['reference_template_id']),encoding='utf-8')
    return read_contract(out)

def read_contract(out):
    return json.loads((Path(out)/'page-contract.json').read_text(encoding='utf-8'))
