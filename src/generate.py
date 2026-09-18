"""External Jinja drafts only. They are not an alternate business application."""
from pathlib import Path
import shutil
import re
from core import ROOT,save_json,digest,inside

UI_JS='''(() => {
const root=document.documentElement, button=document.querySelector('[data-theme-toggle]');
let saved; try {saved=localStorage.getItem('pony-theme')} catch (_) {}
if(saved==='light'||saved==='dark') root.dataset.theme=saved;
button?.addEventListener('click',()=>{const dark=(root.dataset.theme|| (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'))==='dark';root.dataset.theme=dark?'light':'dark';try{localStorage.setItem('pony-theme',root.dataset.theme)}catch(_){} });
const nav=document.querySelector('[data-mobile-nav]');
nav?.addEventListener('keydown',e=>{if(e.key==='Escape'){nav.open=false;nav.querySelector('summary').focus()}});
matchMedia('(min-width: 900px)').addEventListener('change',e=>{if(e.matches&&nav)nav.open=false});
document.querySelectorAll('img').forEach(img=>img.addEventListener('error',()=>{img.classList.add('image-failed');},{once:true}));
})();'''

BASE_CSS='''
:root{color-scheme:light;--bg:#f2f4f7;--surface:#fff;--ink:#17283d;--muted:#536275;--line:#c5ced8;--accent:#0e596b}
:root[data-theme=dark]{color-scheme:dark;--bg:#111b27;--surface:#1b2939;--ink:#eef5fc;--muted:#bdcbda;--line:#516176;--accent:#80d7e6}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#111b27;--surface:#1b2939;--ink:#eef5fc;--muted:#bdcbda;--line:#516176;--accent:#80d7e6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif;padding-bottom:85px}a{color:var(--accent)}button,input{font:inherit;color:var(--ink);background:var(--surface);border:1px solid var(--line);padding:.55rem;border-radius:.3rem}button,summary{cursor:pointer}img{max-width:100%;object-fit:contain}.image-failed{background:var(--line)}
.wf-header,.wf-footer{padding:1rem 3vw;background:var(--surface);border-block:1px solid var(--line)}.wf-brand{font-size:1.5rem;font-weight:800}.wf-tools{display:flex;gap:.7rem;flex-wrap:wrap;align-items:center}.wf-search{display:flex;gap:.3rem;max-width:100%}.wf-search input{min-width:0;width:12rem}.wf-nav{display:flex;flex-wrap:wrap;gap:1rem}.wf-main{max-width:1440px;margin:auto;padding:1.2rem}.wf-mobile{display:none}.wf-top{position:fixed;right:1rem;bottom:6rem;z-index:99;background:var(--surface);border:1px solid var(--line);padding:.6rem}
.wf-content .container{max-width:100%;width:auto}.wf-content .container_left,.wf-content .container_right{float:none;width:auto;min-width:0}.wf-content .container.float-clear{display:grid;grid-template-columns:minmax(0,3fr) minmax(230px,1fr);gap:24px}.wf-content .container .container{display:block}.wf-content .bgwhite,.wf-content .item-block{background:var(--surface);color:var(--ink)}.wf-content .section-tit{border-color:var(--line);margin-block:1rem}.wf-content p,.wf-content td,.wf-content li{overflow-wrap:anywhere}.wf-content table{max-width:100%;font-size:.9rem}.wf-content .match-item{height:auto;min-height:90px;padding:12px;border-bottom:1px solid var(--line)}.wf-content .info_center{min-width:0}.wf-content .score{font-variant-numeric:tabular-nums;white-space:nowrap;min-width:5rem}.wf-content .home,.wf-content .away{min-width:0}.wf-content .text{overflow-wrap:anywhere}.wf-content .league{color:var(--muted)}
.wf-score-grid{display:grid;gap:12px}.wf-match{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);gap:12px;align-items:center;padding:16px;border:1px solid var(--line);background:var(--surface)}.wf-match .score{font-size:1.3rem;font-weight:800;white-space:nowrap}.wf-match img{width:32px;height:32px}.wf-meta{grid-column:1/-1;color:var(--muted)}.wf-team{min-width:0;overflow-wrap:anywhere}.wf-match a{grid-column:1/-1}.wf-home{display:grid;gap:20px}.wf-lead{padding:24px;background:var(--surface);border-left:5px solid var(--accent)}
@media(max-width:899px){.wf-desktop{display:none}.wf-mobile{display:block}.wf-mobile[open] .wf-nav{display:grid;grid-template-columns:1fr 1fr;max-height:65vh;overflow:auto;padding:1rem}.wf-main{padding:12px}.wf-content .container.float-clear{display:block}.wf-content .container_left,.wf-content .container_right{width:100%}.wf-content .match-item{display:grid;gap:8px}.wf-content .info_left,.wf-content .info_center,.wf-content .info_right{float:none;width:100%;height:auto}.wf-content .info_center{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr)}.wf-content .home,.wf-content .away,.wf-content .score{float:none;width:auto}.wf-content .header_menu{display:none}.wf-match{gap:8px;padding:10px}.wf-search{flex:1}.wf-search input{width:100%}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
'''

NAV='<a href="/">首页</a><a href="/nba">NBA</a><a href="/cba">CBA</a><a href="/zuqiu">足球</a><a href="/lanqiu">篮球</a><a href="/allmatch.html">全部赛事</a>'

def generate(task,contract,slug,design):
    if slug not in ('editorial','rail'): raise ValueError('Unknown reviewed layout recipe')
    out=ROOT/'drafts'/slug
    if not inside(out,ROOT) or out.parent.is_symlink():raise ValueError('External draft path escaped workflow root')
    if out.exists(): raise ValueError('Draft already exists; preserve previous output and use repair command')
    ref=task['reference_template_id']; repo=Path(task['repo_root'])
    # External namespace only; not allocated as a business template id.
    dest=out/'templates'/'draft'; assets=out/'static'/'draft'
    shutil.copytree(repo/'templates'/ref,dest); shutil.copytree(repo/'static'/ref,assets)
    for p in dest.rglob('*.html'):
        text=p.read_text(encoding='utf-8-sig').replace(ref+'/', 'draft/')
        p.write_text(text,encoding='utf-8')
    original=(dest/'master.html').read_text(encoding='utf-8')
    head=original[:original.index('<body>')]
    head=head.replace('</head>','<link rel="stylesheet" href="/static/draft/workflow.css"></head>')
    footer=original[original.index('<footer'):original.index('</footer>')+9]
    master=head+'''<body id="top"><header class="wf-header"><a class="wf-brand" href="/">{{ website_config.Name }}</a>
<div class="wf-tools"><button data-theme-toggle type="button" aria-label="切换明暗主题">明暗主题</button>
<form class="wf-search" action="/search" method="get"><label for="wf-q">搜索赛事</label><input id="wf-q" name="q" type="search" required><button>搜索</button></form></div>
<nav class="wf-nav wf-desktop" aria-label="主导航">'''+NAV+'''</nav>
<details class="wf-mobile" data-mobile-nav><summary>☰ 导航</summary><nav class="wf-nav" aria-label="手机导航">'''+NAV+'''</nav></details></header>
<main class="wf-main wf-content">{% block list %}{% endblock %}</main>'''+footer+'''
<a class="wf-top" href="#top" aria-label="返回顶部">↑ 顶部</a>
<script src="/static/js/jquery.min.js"></script><script src="/static/js/jquery.lazyload.min.js"></script>
<script src="/static/js/swiper-bundle.min.js"></script><script src="/static/draft/js/index.js"></script>
<script src="/static/draft/workflow.js"></script>
{% if website_config.FooterJS %}{{ website_config.FooterJS|safe }}{% endif %}
<script src="/static/js/ajs.js"></script></body></html>'''
    (dest/'master.html').write_text(master,encoding='utf-8')
    extra=''
    if slug=='rail':
        extra='@media(min-width:900px){.wf-header{position:fixed;inset:0 auto 0 0;width:260px;overflow:auto}.wf-nav{display:grid}.wf-main,footer{margin-left:260px}.wf-tools{display:grid}.wf-search{flex-wrap:wrap}.wf-home{grid-template-columns:minmax(0,2fr) minmax(220px,1fr)}.wf-lead{grid-column:1/-1}.wf-score-grid{grid-template-columns:1fr 1fr}}'
    else:
        extra='.wf-header{border-top:6px solid var(--accent)}.wf-home{grid-template-columns:1fr}.wf-score-grid{grid-template-columns:repeat(auto-fit,minmax(280px,1fr))}.wf-lead{font-size:1.1rem}.wf-content .article-list{columns:2}'
    (assets/'workflow.css').write_text(BASE_CSS+extra,encoding='utf-8');(assets/'workflow.js').write_text(UI_JS,encoding='utf-8')
    # Representative homepage uses only audited index handler fields. No fabricated data or links.
    (dest/'index.html').write_text('''{% extends 'draft/master.html' %}
{% block title %}{{ website_config.Title }}{% endblock %}{% block Keywords %}{{ website_config.Keyword }}{% endblock %}{% block Description %}{{ website_config.Description }}{% endblock %}
{% block list %}<div class="wf-home"><section class="wf-lead"><h1>{{ website_config.Name }}</h1><p>{{ website_config.Description }}</p></section>
<section><h2>赛事日程</h2><div class="wf-score-grid">{% for item in list_match_all %}<article class="wf-match">
<div class="wf-meta">{{ item.matchtime }} · {{ item.name }} · {{ item.status_up_name }}</div>
<div class="wf-team"><img src="{{ item.hteam_logo }}" alt="" width="32" height="32"><span>{{ item.hteam_name }}</span></div>
<div class="score">{% if item.status_up_name == '未开赛' or item.score is not defined or item.score is none or item.score == '' %}VS{% else %}{{ item.score }}{% endif %}</div>
<div class="wf-team"><img src="{{ item.ateam_logo }}" alt="" width="32" height="32"><span>{{ item.ateam_name }}</span></div>
<a href="/{% if not item.is_hot_match %}{{ item.match_type_pinyin_flag }}/{% endif %}{{ item.pinyin }}/{{ item.id }}.html">{{ item.hteam_name }} vs {{ item.ateam_name }}</a></article>{% else %}<p>暂无赛事</p>{% endfor %}</div></section>
<section><h2>资讯</h2><ul>{% for item in list_news %}<li><a href="/d/{{ item.ID }}.html">{{ item.Title }}</a></li>{% else %}<li>暂无资讯</li>{% endfor %}</ul></section></div>{% endblock %}''',encoding='utf-8')
    # Missing search template can be implemented externally from the verified handler/a15 field contract.
    (dest/'search.html').write_text('''{% extends 'draft/master.html' %}{% block title %}{{ key }} - {{ website_config.Name }}{% endblock %}
{% block list %}<h1>赛事搜索</h1><p>仅支持现有服务配置的赛事与球队关键词。</p><ul>{% for item in list_result %}<li><a href="/{{ item.match_type_pinyin_flag }}/{% if website_config.SeoFlag %}{{ website_config.SeoFlag }}-{% endif %}{{ item.pinyin }}/{{ item.id }}.html">{{ item.hteam_name }} vs {{ item.ateam_name }}</a> {{ item.matchtime }}</li>{% else %}<li>暂无结果或关键词未在服务支持范围内</li>{% endfor %}</ul>{% endblock %}''',encoding='utf-8')
    missing=[p['entry_template'] for p in contract['pages'] if not (dest/Path(p['entry_template']).name).exists()]
    save_json(out/'design-spec.json',design)
    save_json(out/'draft-manifest.json',{'environment':'fixture','formal_template_id':None,'missing_pages':missing,
        'status':'needs_review','production_ready':False,'source_contract':str(ROOT/'runs/bootstrap/page-contract.json'),
        'files':{p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()}})
    (out/'design-brief.md').write_text(f'# 外部草稿：{slug}\n\n'+
        'Jinja 绑定来自真实业务源码；不是替代业务服务。导航、首页赛事展示和内容组织具有结构差异；其余继承页面暂保留原有主体，尚不能声称整套差异化验收通过。\n'+
        '缺正式编号，禁止复制进业务目录。搜索白名单/索引策略和缺失页面仍需确认。\n',encoding='utf-8')
    return out
