#!/usr/bin/env python3
from pathlib import Path
import json, argparse

ROOT=Path('/home/roomhacker/babel-experiments')

def load_model(n:int):
    if n == 0:
        p=ROOT/'models/top256_retrained/unigram.json'
        if not p.exists(): return None
        j=json.loads(p.read_text(encoding='utf-8'))
        return {'n':0,'alphabet':j['alphabet'],'fallback':j['costs'],'rows':{},'states':1,'size':p.stat().st_size}
    if n == 3:
        p=ROOT/'models/top256_retrained/markov3_meta.json'
    else:
        p=ROOT/f'models/top256_markov{n}/markov{n}_meta.json'
    if not p.exists(): return None
    j=json.loads(p.read_text(encoding='utf-8'))
    idx_path=Path(j['index_file']); rows_path=Path(j['rows_file'])
    idx_size=8 if 'u64' in idx_path.name or n==5 else 4
    rows={}
    with idx_path.open('rb') as idxf, rows_path.open('rb') as rf:
        while True:
            b=idxf.read(idx_size)
            if not b: break
            st=int.from_bytes(b,'little')
            raw=rf.read(512)
            if len(raw)<512: break
            rows[st]=[int.from_bytes(raw[i:i+2],'little') for i in range(0,512,2)]
    return {'n':n,'alphabet':j['alphabet'],'fallback':j['fallback_costs'],'rows':rows,'states':j['observed_states'],'size':idx_path.stat().st_size+rows_path.stat().st_size+p.stat().st_size}

def state_of(seq, n):
    if n == 0: return 0
    s=0
    pad=[0]*max(0,n-len(seq)) + seq[-n:]
    for x in pad: s=(s<<8)|x
    return s

def greedy(m, length=160, seed=''):
    A=m['alphabet']; n=m['n']
    seq=[]
    cmap={c:i for i,c in enumerate(A)}
    for ch in seed:
        seq.append(cmap.get(ch,0))
    out=[]
    for _ in range(length):
        if n==0:
            row=m['fallback']
        else:
            row=m['rows'].get(state_of(seq,n), m['fallback'])
        b=min(range(256), key=lambda i:(row[i], i))
        seq.append(b); out.append(b)
    return ''.join(A[i] for i in out)

def beam(m, steps=80, width=20, branch=8, seed=''):
    A=m['alphabet']; n=m['n']; cmap={c:i for i,c in enumerate(A)}
    start=[cmap.get(ch,0) for ch in seed]
    beams=[(0,start,[])]
    for _ in range(steps):
        cand=[]
        for e,seq,out in beams:
            row=m['fallback'] if n==0 else m['rows'].get(state_of(seq,n), m['fallback'])
            for b in sorted(range(256), key=lambda i:(row[i],i))[:branch]:
                cand.append((e+row[b], seq+[b], out+[b]))
        cand.sort(key=lambda x:(x[0], x[2]))
        beams=cand[:width]
    return [(e,''.join(A[i] for i in out)) for e,seq,out in beams]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--models', default='0,1,2,3,5')
    ap.add_argument('--length', type=int, default=160)
    ap.add_argument('--beam-steps', type=int, default=60)
    ap.add_argument('--seed', default='')
    args=ap.parse_args()
    for n in [int(x) for x in args.models.split(',') if x.strip()]:
        m=load_model(n)
        if not m:
            print(f'\n== Markov-{n}: missing/not ready ==')
            continue
        print(f'\n== Markov-{n} states={m["states"]} disk_MB={m["size"]/1024/1024:.2f} ==')
        print('greedy:')
        print(repr(greedy(m,args.length,args.seed)))
        print('beam top:')
        for i,(e,s) in enumerate(beam(m,args.beam_steps,20,8,args.seed)[:8]):
            print(f'{i:02d} energy={e:6d} {s!r}')
if __name__=='__main__':
    main()
