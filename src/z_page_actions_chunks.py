"""Bound long per-template CLI runs without reducing page or viewport coverage."""
import argparse
import json
from pathlib import Path

from core import ROOT, read_json, save_json
from z_page_actions import run


def run_chunks(input_dir, output, template, chunk_size):
    source=(ROOT/input_dir).resolve()
    out=(ROOT/output).resolve()
    if not source.is_relative_to(ROOT/'runs') or not out.is_relative_to(ROOT/'runs') or out.exists():
        raise ValueError('Existing HTTP input and new output must be under runs/')
    if chunk_size<1:raise ValueError('Positive chunk size required')
    pages=read_json(source/'pages.json')
    name=f'z{template}'
    paths=sorted({p['path'] for p in pages if p['template']==name and p['status']==200})
    if not paths:raise ValueError('No current HTTP200 page samples')
    out.mkdir(parents=True)
    summaries=[]
    all_results=[]
    for i in range(0,len(paths),chunk_size):
        index=i//chunk_size+1
        selected=set(paths[i:i+chunk_size])
        chunk_input=out/f'input-{index}'
        chunk_input.mkdir()
        save_json(chunk_input/'pages.json',[p for p in pages if p['template']==name and p['path'] in selected])
        chunk_output=out/f'part-{index}'
        try:
            run(chunk_input.relative_to(ROOT),chunk_output.relative_to(ROOT),[template])
            result=read_json(chunk_output/f'{name}-results.json')
            summary=read_json(chunk_output/'summary.json')[0]
        except Exception as error:
            result={'pages':[]}
            summary={'template':name,'status':'blocked','states_attempted':len(selected)*2,
                     'states_checked':0,'reason':str(error)[:180]}
            save_json(chunk_output/'blocked.json',summary)
        summaries.append(summary)
        all_results.extend(result['pages'])
        save_json(out/'progress.json',summaries)
    tested={(x['path'],x['width']) for x in all_results}
    expected={(path,width) for path in paths for width in (390,1280)}
    merged={'template':name,'pages_planned':len(paths),'states_planned':len(expected),
            'states_observed':len(tested),'states_missing':sorted(map(list,expected-tested)),
            'part_summaries':summaries,'input_hashes':sorted({read_json(out/f'part-{j}'/f'{name}-results.json')['input_hash'] for j in range(1,len(summaries)+1)
                                                       if (out/f'part-{j}'/f'{name}-results.json').exists()})}
    save_json(out/'summary.json',merged)
    save_json(out/f'{name}-results.json',all_results)
    print(json.dumps({k:merged[k] for k in ('template','states_planned','states_observed','states_missing')},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--id',type=int,required=True)
    parser.add_argument('--chunk-size',type=int,default=7)
    args=parser.parse_args()
    if not 1<=args.id<=17:raise ValueError('Current task only z1-z17')
    run_chunks(args.input,args.output,args.id,args.chunk_size)
