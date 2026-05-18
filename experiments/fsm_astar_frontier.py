#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from heapq import heappush, heappop
from collections import Counter
import json, argparse, time

ROOT=Path('/home/roomhacker/babel-experiments')
MODEL=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))
ALPHABET=MODEL['alphabet']
SYM_CLASS=MODEL['symbol_class']
TRANS=MODEL['transition_costs']
EMIT=MODEL['emission_costs']
START='START'

# Pre-sort low-cost symbols.
ROWS={}
for st in set(MODEL['classes'])|{START}:
    arr=[]
    for idx,ch in enumerate(ALPHABET):
        ns=SYM_CLASS[ch]
        c=int(TRANS.get(st,{}).get(ns,1500))+int(EMIT.get(ns,{}).get(ch,1500))
        arr.append((c,idx,ch,ns))
    ROWS[st]=sorted(arr)
MIN_COST=min(r[0] for rows in ROWS.values() for r in rows)

def enumerate_pages(length:int,k:int):
    # A* over partial pages.
    q=[]
    heappush(q,(length*MIN_COST,0,START,''))
    seen=0
    out=[]
    while q and len(out)<k:
        f,g,st,text=heappop(q)
        pos=len(text)
        if pos==length:
            out.append({'rank':len(out),'energy':g,'page':text})
            continue
        rem=length-pos-1
        for c,idx,ch,ns in ROWS[st][:48]: # frontier truncation
            ng=g+c
            nf=ng + rem*MIN_COST
            heappush(q,(nf,ng,ns,text+ch))
        seen+=1
        if seen and seen%100000==0:
            print(f'expanded={seen} queue={len(q)} found={len(out)}',flush=True)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--length',type=int,default=64)
    ap.add_argument('--topk',type=int,default=100)
    args=ap.parse_args()
    t=time.time()
    pages=enumerate_pages(args.length,args.topk)
    print(json.dumps({'length':args.length,'topk':args.topk,'elapsed_seconds':round(time.time()-t,3),'pages':pages[:20]},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
