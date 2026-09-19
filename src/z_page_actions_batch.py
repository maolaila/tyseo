"""Run the bounded per-template functional audit for an assigned ID set."""
import argparse
from pathlib import Path

from core import ROOT
from z_page_actions_chunks import run_chunks


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--ids',nargs='+',type=int,required=True)
    parser.add_argument('--chunk-size',type=int,default=7)
    args=parser.parse_args()
    if any(i<1 or i>17 for i in args.ids):raise ValueError('Only confirmed z1-z17')
    root=(ROOT/args.output).resolve()
    if not root.is_relative_to(ROOT/'runs') or root.exists():raise ValueError('New output under runs/ required')
    root.mkdir(parents=True)
    for number in args.ids:
        print(f'z{number} starting',flush=True)
        run_chunks(args.input,(root/f'z{number}').relative_to(ROOT),number,args.chunk_size)
