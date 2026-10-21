"""Summarize externally recorded local model timing; never initiates inference."""
import argparse
import json
import statistics
from pathlib import Path

def percentile(values, p):
    values=sorted(values)
    if not values:return None
    idx=(len(values)-1)*p
    lo=int(idx);hi=min(lo+1,len(values)-1)
    return round(values[lo]+(values[hi]-values[lo])*(idx-lo),2)

def summarize(records):
    result={}
    for kind in ('cold','warm'):
        group=[r for r in records if r.get('run_type')==kind and r.get('success') is True]
        d={'count':len(group)}
        for key in ('ttft_ms','total_ms','tokens_per_second','cancel_ms'):
            values=[r[key] for r in group if isinstance(r.get(key),(int,float)) and r[key]>=0]
            d[key]={'samples':len(values),'median':round(statistics.median(values),2) if values else None,'p95':percentile(values,.95)}
        result[kind]=d
    result['errors']=[{'case_id':r.get('case_id'),'error':r.get('error')} for r in records if not r.get('success')]
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True,type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    data=json.loads(a.input.read_text())
    result=summarize(data['runs'])
    encoded=json.dumps(result,indent=2)
    if a.output:a.output.write_text(encoded+'\n')
    print(encoded)
if __name__=='__main__':main()
