"""Render the actual generated Jinja entry with explicit synthetic sports edges."""
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Environment,FileSystemLoader,StrictUndefined
from core import ROOT,save_json

def render_sports(design):
    root=ROOT/'drafts'/design
    env=Environment(loader=FileSystemLoader(str(root/'templates')),undefined=StrictUndefined,autoescape=True)
    site=dict(Name='FIXTURE_ONLY 体育测试',Title='FIXTURE_ONLY 比分边界',Keyword='FIXTURE_ONLY',Description='外部合成夹具，不是生产文案',Domain='fixture.invalid',Logo='',HeaderJS='',FooterJS='',Address='',PhoneNum='',LinkList=[],Icp='')
    scores=[(None,'未开赛','VS'),('', '未开赛','VS'),(0,'进行中','0'),('0','进行中','0'),('0-0','进行中','0-0'),('0-1','完场','0-1'),('1-0','完场','1-0'),('118-115','完场','118-115'),('12-10','完场','12-10')]
    items=[dict(id=i,matchtime='2026-09-18 23:59',name='FIXTURE_ONLY 联赛',status_up_name=status,score=score,
                hteam_name='FIXTURE_ONLY 超长主队中文名称 Long Home Team',ateam_name='FIXTURE_ONLY 超长客队名称 Long Away Team',
                hteam_logo='/missing-image.png',ateam_logo='/missing-image.png',is_hot_match=False,match_type_pinyin_flag='zuqiu',pinyin='fixture') for i,(score,status,expected) in enumerate(scores)]
    context=dict(website_config=site,request=SimpleNamespace(path='/'),list_match_all=items,list_news=[],list_hot_league=[])
    output=ROOT/'runs/rendered'/design/'sports-boundaries.html'
    output.write_text(env.get_template('draft/index.html').render(context),encoding='utf-8')
    save_json(output.with_suffix('.json'),{'environment':'fixture','expected_scores':[x[2] for x in scores],'items':items})
    return output
