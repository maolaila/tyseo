"""Deterministic checks. Unknown policy is review, never invented PASS."""
import re
import json
from bs4 import BeautifulSoup

def html_checks(html, headers=None, policy=None):
    soup=BeautifulSoup(html,'html.parser'); policy=policy or {}; headers=headers or {}
    def result(rule,status,actual): return {'rule_id':rule,'status':status,'actual':actual}
    body=soup.body
    results=[result('SEO-01','pass' if body and body.get_text(' ',strip=True) and body.select('a[href]') else 'fail','Initial body text/link presence only; no invented word-count or text/HTML ratio threshold')]
    bad=[str(x)[:200] for x in soup.select('a[onclick]:not([href]),a[href=""],a[href="#"],a[href^="javascript:"]') if x.get('role')!='button' and not x.has_attr('aria-controls')]
    results.append(result('SEO-02','fail' if bad else 'pass',bad))
    results.append(result('SEO-04','pass' if len(soup.select('h1'))==1 and soup.html and soup.html.get('lang') else 'fail',{'h1_count':len(soup.select('h1'))}))
    can=soup.select_one('link[rel="canonical"]'); canonical=can.get('href') if can else None
    if policy.get('canonical') is not None:
        results.append(result('SEO-06','pass' if canonical==policy['canonical'] else 'fail',canonical))
    else: results.append(result('SEO-06','needs_review',{'observed':canonical,'reason':'No approved canonical policy'}))
    header_robots=next((v for k,v in headers.items() if k.lower()=='x-robots-tag'),'')
    robots=' '.join(x.get('content','') for x in soup.select('meta[name="robots"]'))+' '+header_robots
    indexing=policy.get('indexable')
    results.append(result('SEO-10','needs_review' if indexing is None else 'fail' if indexing and 'noindex' in robots.lower() else 'pass',robots))
    invalid=[]
    for x in soup.select('script[type="application/ld+json"]'):
        try: json.loads(x.get_text())
        except ValueError: invalid.append('Invalid JSON-LD')
    results.append(result('SEO-11','fail' if invalid or 'FIXTURE_ONLY' in html else 'needs_review',invalid or 'Syntax inspected; semantic facts need review'))
    return results

def score_text(value):
    # Only a fixture utility: production score bindings stay those of the source contract.
    return 'VS' if value is None or value=='' else str(value)

def check_scores(expected, visible):
    return all(visible.get(k)==score_text(v) for k,v in expected.items())

def check_dependencies(text,target,known_ids):
    return [i for i in known_ids if i!=target and (f'/static/{i}/' in text or re.search(r"['\"]"+re.escape(i)+r"/",text))]

def coverage(expected,results):
    seen={tuple(r.get(k) for k in ('page_type_id','width','theme','javascript')) for r in results}
    return [x for x in expected if tuple(x) not in seen]

def valid_repair(before_checks,after_checks,before_scope,after_scope,round_no,limit=3):
    return round_no<=limit and before_checks==after_checks and before_scope==after_scope

def genuine_crawl(record):
    return record.get('source')=='verified_server_log' and record.get('identity_verified') is True and not record.get('synthetic')

def distinct_design(a,b):
    axes=('navigation','home_layout','match_presentation','article_layout','detail_layout')
    return sum(a.get(k)!=b.get(k) for k in axes)>=3

def tdk_variation(samples):
    """Compare known input expectations, never infer a site's editorial keyword policy."""
    if len({s.get('page_type_id') for s in samples})<2 or len({s.get('site_config_id') for s in samples})<2:
        return {'status':'blocked','reason':'Multiple page and configuration samples required'}
    findings=[]
    for sample in samples:
        expected=sample.get('expected')
        if not expected or not sample.get('source_evidence'):
            return {'status':'needs_review','reason':'TDK input contract/evidence unknown'}
        for field in ('title','description','keywords'):
            if field not in expected:return {'status':'needs_review','reason':'Unconfirmed '+field+' binding'}
            if sample.get('actual',{}).get(field)!=expected[field]:
                findings.append({'page_type_id':sample['page_type_id'],'site_config_id':sample['site_config_id'],'field':field})
    return {'status':'fail' if findings else 'pass','findings':findings,'scope':'known input/output binding only; semantic review separate'}
