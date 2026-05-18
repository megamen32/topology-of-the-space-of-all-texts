#!/usr/bin/env python3
"""
Exact FSM counting engine for long pages.

Counts number of pages of fixed length N by student energy using finite-state DP:

  dp[position][state][energy] = count

Optimizations:
- aggregate 256 symbols into (next_state, cost, multiplicity)
- sparse energy dictionaries
- optional low-energy band for practical first runs

This is the real core needed for student-ranked Babel addressing.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter, defaultdict
import argparse, json, time, pickle, math, os

ROOT=Path('/home/roomhacker/babel-experiments')
MODEL=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))
OUT=ROOT/'models/fsm_counts_v1'
OUT.mkdir(parents=True, exist_ok=True)

ALPHABET=MODEL['alphabet']
SYM_CLASS=MODEL['symbol_class']
TRANS=MODEL['transition_costs']
EMIT=MODEL['emission_costs']
CLASSES=sorted(set(MODEL['classes']) | {'START'})
START='START'

# per state aggregated transitions: prev_state -> [(next_state, integer_cost, multiplicity), ...]
AGG={}
for st in CLASSES:
    c=Counter()
    for ch in ALPHABET:
        ns=SYM_CLASS[ch]
        cost=int(TRANS.get(st,{}).get(ns,1500)) + int(EMIT.get(ns,{}).get(ch,1500))
        c[(ns,cost)] += 1
    AGG[st]=[(ns,cost,mult) for (ns,cost),mult in sorted(c.items(), key=lambda x:(x[0][1],x[0][0]))]

MIN_STEP=min(cost for rows in AGG.values() for _,cost,_ in rows)
MAX_STEP=max(cost for rows in AGG.values() for _,cost,_ in rows)

def human_int(n:int)->str:
    s=str(n)
    return s if len(s)<16 else f'{s[:8]}…{s[-6:]} ({len(s)}d)'

def run(length:int, band:int|None, checkpoint_every:int, name:str):
    started=time.time()
    # dp: state -> {energy: count}
    dp={START:{0:1}}
    total_space=256**length
    min_possible=length*MIN_STEP
    max_allowed = min_possible + band if band is not None else None
    meta={
        'version':'fsm_count_v1','length':length,'band':band,'min_step':MIN_STEP,'max_step':MAX_STEP,
        'states':CLASSES,'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'alphabet_size':len(ALPHABET),'space_size_decimal_digits':len(str(total_space)),
        'transition_aggregate_sizes':{k:len(v) for k,v in AGG.items()},
    }
    (OUT/f'{name}_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False), flush=True)
    for pos in range(length):
        ndp=defaultdict(lambda: defaultdict(int))
        active=0; transitions=0
        for st,dist in dp.items():
            rows=AGG[st]
            for e,count in dist.items():
                active += 1
                for ns,cost,mult in rows:
                    ne=e+cost
                    if max_allowed is not None and ne>max_allowed:
                        continue
                    ndp[ns][ne] += count*mult
                    transitions += 1
        dp={st:dict(d) for st,d in ndp.items() if d}
        if (pos+1)%checkpoint_every==0 or pos+1 in {1,2,4,8,16,32,64,128,256,512,768,length}:
            elapsed=time.time()-started
            energies=sum(len(d) for d in dp.values())
            counted=sum(sum(d.values()) for d in dp.values())
            emin=min((min(d) for d in dp.values() if d), default=None)
            emax=max((max(d) for d in dp.values() if d), default=None)
            rate=(pos+1)/elapsed if elapsed else 0
            eta=(length-(pos+1))/rate if rate else 0
            print(f'pos={pos+1}/{length} states={len(dp)} energy_cells={energies} emin={emin} emax={emax} counted={human_int(counted)} active_prev={active} elapsed={elapsed:.1f}s eta={eta:.1f}s', flush=True)
            # checkpoint compact pickle
            with (OUT/f'{name}_checkpoint.pkl.tmp').open('wb') as f:
                pickle.dump({'pos':pos+1,'dp':dp,'meta':meta},f,protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(OUT/f'{name}_checkpoint.pkl.tmp', OUT/f'{name}_checkpoint.pkl')
    # final energy histogram
    hist=Counter()
    for d in dp.values(): hist.update(d)
    final={
        'length':length,'band':band,'finished_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'energy_cells_by_state':{st:len(d) for st,d in dp.items()},
        'energy_min':min(hist) if hist else None,
        'energy_max':max(hist) if hist else None,
        'hist_cells':len(hist),
        'counted_pages':str(sum(hist.values())),
        'counted_digits':len(str(sum(hist.values()))),
        'full_space_digits':len(str(total_space)),
        'complete': band is None,
    }
    (OUT/f'{name}_final.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
    # Write low histogram only top/low compact to JSON, full pickle for exact use.
    with (OUT/f'{name}_hist.pkl').open('wb') as f: pickle.dump(dict(hist),f,protocol=pickle.HIGHEST_PROTOCOL)
    print('FINAL', json.dumps(final,ensure_ascii=False), flush=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--length',type=int,default=1024)
    ap.add_argument('--band',type=int,default=50000, help='energy band above theoretical min; use -1 for full exact distribution')
    ap.add_argument('--checkpoint-every',type=int,default=25)
    ap.add_argument('--name',default=None)
    args=ap.parse_args()
    band=None if args.band<0 else args.band
    name=args.name or f'fsm_len{args.length}_' + ('full' if band is None else f'band{band}')
    run(args.length,band,args.checkpoint_every,name)
if __name__=='__main__': main()
