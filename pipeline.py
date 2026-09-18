"""Safe dispatcher for implemented local tasks; never enables remote side effects."""
import argparse
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'src'))
from core import ROOT,read_json

parser=argparse.ArgumentParser(description='List and run supported local pipelines')
parser.add_argument('action',choices=['list','run'])
parser.add_argument('pipeline',nargs='?')
args=parser.parse_args()
registry=read_json(ROOT/'config/pipelines.json')['pipelines']
if args.action=='list':
    for name,p in registry.items():print(name+': '+p['state'])
elif args.pipeline=='z-review':
    subprocess.run([sys.executable,str(ROOT/'src/z_review.py')],cwd=ROOT,check=True)
else:
    parser.error('Only z-review has a single fully routed local execution entry. Other pipelines require their documented steps; remote actions are not dispatched.')
