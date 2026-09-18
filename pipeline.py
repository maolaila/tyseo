"""Safe dispatcher for implemented local tasks; never enables remote side effects."""
import argparse
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'src'))
from core import ROOT,read_json

parser=argparse.ArgumentParser(description='List and run supported local pipelines')
parser.add_argument('action',choices=['list','run','task'])
parser.add_argument('pipeline',nargs='?')
args=parser.parse_args()
registry=read_json(ROOT/'config/pipelines.json')['pipelines']
if args.action=='list':
    for name,p in registry.items():print(name+': '+p['state'])
elif args.action=='task' and args.pipeline in read_json(ROOT/'tasks/ad-hoc.json')['tasks']:
    temporary=read_json(ROOT/'tasks/ad-hoc.json')['tasks'][args.pipeline]
    subprocess.run([sys.executable,str(ROOT/temporary['entrypoint'])],cwd=ROOT,check=True)
else:
    parser.error('Use the documented workflow.py phase commands. Temporary assignments require explicit task selection; they are not permanent pipeline stages.')
