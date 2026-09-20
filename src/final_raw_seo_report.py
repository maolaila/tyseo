"""Reuse project SEO checks over the final journey run's saved original HTML."""
import argparse
import hashlib
from collections import Counter

from checks import html_checks
from core import ROOT, save_json, read_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args=parser.parse_args()
    run=(ROOT/args.run).resolve()
    if not run.is_relative_to(ROOT/'runs') or not (run/'summary.json').is_file():
        raise ValueError('Completed final journey run required under runs/')
    totals=Counter()
    for folder in sorted(run.iterdir()):
        if not folder.is_dir() or not (folder/'http-pages.json').exists():continue
        observations=[]
        for page in read_json(folder/'http-pages.json'):
            if page['status']!=200:continue
            filename=(folder/'http'/hashlib.sha256(page['path'].encode()).hexdigest()[:16]).with_suffix('.html')
            if not filename.is_file():
                observations.append({'path':page['path'],'status':'blocked','reason':'original HTML unavailable'})
                totals['blocked']+=1
                continue
            html=filename.read_text(encoding='utf-8',errors='replace')
            checks=html_checks(html)
            for check in checks:totals[check['status']]+=1
            observations.append({'path':page['path'],'page_types':page['page_types'],'html_sha256':page['body_sha256'],
                                 'status':'fail' if any(x['status']=='fail' for x in checks) else 'needs_review',
                                 'checks':checks})
        save_json(folder/'raw-seo.json',observations)
    summary={'checks':dict(totals),'source':'original HTTP response HTML saved by final_user_journeys.py',
             'limits':'Canonical/indexability policy and TDK input variation require confirmed site config; no production ranking claim'}
    save_json(run/'raw-seo-summary.json',summary)
    print(summary)


if __name__=='__main__':main()
