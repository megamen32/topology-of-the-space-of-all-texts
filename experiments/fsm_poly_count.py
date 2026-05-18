#!/usr/bin/env python3
"""
Experiment A: truncated polynomial-matrix counter for the finite FSM student.

We represent each transition as:
  from_state -> to_state with polynomial P(x)=sum multiplicity*x^cost

Then length-N page counts are coefficients of:
  initial_vector * M(x)^N

We truncate to the low-energy frontier:
  energy <= min_energy_per_symbol * N + band

This is the generating-function version of the sparse DP and should be compared
against experiments/fsm_count_1024.py.
"""
from __future__ import annotations
from pathlib import Path
from collections import Counter, defaultdict
import argparse, json, time, pickle, os

ROOT=Path('/home/roomhacker/babel-experiments')
MODEL=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))
OUT=ROOT/'models/fsm_poly_counts_v1'
OUT.mkdir(parents=True, exist_ok=True)

ALPHABET=MODEL['alphabet']
SYM_CLASS=MODEL['symbol_class']
TRANS=MODEL['transition_costs']
EMIT=MODEL['emission_costs']
STATES=sorted(set(MODEL['classes']) | {'START'})
START='START'

# Build matrix as dict[from][to] = Counter(cost -> multiplicity)
M={st:defaultdict(Counter) for st in STATES}
all_costs=[]
for st in STATES:
    for ch in ALPHABET:
        ns=SYM_CLASS[ch]
        c=int(TRANS.get(st,{}).get(ns,1500)) + int(EMIT.get(ns,{}).get(ch,1500))
        M[st][ns][c] += 1
        all_costs.append(c)
MIN_STEP=min(all_costs)
MAX_STEP=max(all_costs)

def trim_poly(poly:Counter, max_energy:int)->Counter:
    return Counter({e:c for e,c in poly.items() if e <= max_energy and c})

def conv(a:Counter,b:Counter,max_energy:int)->Counter:
    # sparse convolution, truncated
    if len(a)>len(b): a,b=b,a
    out=Counter()
    for ea,ca in a.items():
        rem=max_energy-ea
        if rem < 0: continue
        for eb,cb in b.items():
            e=ea+eb
            if e<=max_energy:
                out[e]+=ca*cb
    return out

def mat_mul(A,B,max_energy:int):
    # matrices: dict[i][j] = Counter energy->count
    C={i:defaultdict(Counter) for i in STATES}
    nonzero=0
    for i in STATES:
        for k,poly_ik in A.get(i,{}).items():
            if not poly_ik: continue
            for j,poly_kj in B.get(k,{}).items():
                if not poly_kj: continue
                p=conv(poly_ik,poly_kj,max_energy)
                if p:
                    C[i][j].update(p)
        # trim/update plain Counter
        for j in list(C[i].keys()):
            C[i][j]=trim_poly(C[i][j],max_energy)
            if not C[i][j]: del C[i][j]
            else: nonzero+=len(C[i][j])
    return {i:dict(C[i]) for i in STATES}, nonzero

def vec_mul(v,A,max_energy:int):
    # vector: dict[state]=Counter, matrix A
    out=defaultdict(Counter)
    cells=0
    for i,poly_i in v.items():
        for j,poly_ij in A.get(i,{}).items():
            p=conv(poly_i,poly_ij,max_energy)
            if p:
                out[j].update(p)
    out={j:trim_poly(p,max_energy) for j,p in out.items() if p}
    cells=sum(len(p) for p in out.values())
    return out,cells

def human_int(n:int)->str:
    s=str(n)
    return s if len(s)<16 else f'{s[:8]}…{s[-6:]} ({len(s)}d)'

def run(length:int,band:int,name:str):
    t0=time.time()
    min_energy=length*MIN_STEP
    max_energy=min_energy+band
    meta={
        'version':'fsm_poly_count_v1','length':length,'band':band,
        'min_step':MIN_STEP,'max_step':MAX_STEP,'max_energy':max_energy,
        'states':STATES,'alphabet_size':len(ALPHABET),'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'method':'truncated polynomial matrix exponentiation'
    }
    print(json.dumps(meta,ensure_ascii=False),flush=True)
    (OUT/f'{name}_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')

    # Trim base matrix to max_energy. Base costs are small enough already.
    base={i:{j:trim_poly(poly,max_energy) for j,poly in M[i].items()} for i in STATES}
    powers=[]
    cur=base
    n=length
    bit=0
    while (1<<bit) <= n:
        powers.append(cur)
        cells=sum(len(poly) for row in cur.values() for poly in row.values())
        print(f'power bit={bit} span={1<<bit} matrix_poly_cells={cells} elapsed={time.time()-t0:.1f}s',flush=True)
        if (1<<(bit+1)) <= n:
            cur,cells2=mat_mul(cur,cur,max_energy)
            print(f' squared bit={bit}->bit={bit+1} cells={cells2} elapsed={time.time()-t0:.1f}s',flush=True)
            with (OUT/f'{name}_power{bit+1}.pkl.tmp').open('wb') as f:
                pickle.dump(cur,f,protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(OUT/f'{name}_power{bit+1}.pkl.tmp', OUT/f'{name}_power{bit+1}.pkl')
        bit+=1

    # Apply binary powers to initial vector.
    v={START:Counter({0:1})}
    remaining=length
    bit=0
    while remaining:
        if remaining & 1:
            v,cells=vec_mul(v,powers[bit],max_energy)
            counted=sum(sum(p.values()) for p in v.values())
            print(f'apply bit={bit} span={1<<bit} vector_states={len(v)} vector_cells={cells} counted={human_int(counted)} elapsed={time.time()-t0:.1f}s',flush=True)
        remaining >>= 1
        bit+=1

    hist=Counter()
    for poly in v.values(): hist.update(poly)
    result={
        'length':length,'band':band,'energy_min':min(hist) if hist else None,
        'energy_max':max(hist) if hist else None,'hist_cells':len(hist),
        'counted_pages':str(sum(hist.values())),'counted_digits':len(str(sum(hist.values()))),
        'finished_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'elapsed_seconds':round(time.time()-t0,3),
    }
    (OUT/f'{name}_final.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    with (OUT/f'{name}_hist.pkl').open('wb') as f: pickle.dump(dict(hist),f,protocol=pickle.HIGHEST_PROTOCOL)
    print('FINAL',json.dumps(result,ensure_ascii=False),flush=True)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--length',type=int,default=1024)
    ap.add_argument('--band',type=int,default=10000)
    ap.add_argument('--name')
    args=ap.parse_args()
    name=args.name or f'poly_len{args.length}_band{args.band}'
    run(args.length,args.band,name)
if __name__=='__main__': main()
