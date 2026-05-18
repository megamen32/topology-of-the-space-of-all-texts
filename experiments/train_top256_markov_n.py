#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import argparse, json, math, time, struct, array
ROOT=Path('/home/roomhacker/babel-experiments')
ap=argparse.ArgumentParser()
ap.add_argument('--n', type=int, required=True, choices=[1,2,3,4,5])
args=ap.parse_args()
ctx=args.n
IN=ROOT/'models/top256_retrained/corpus.u8'
UNI=json.loads((ROOT/'models/top256_retrained/unigram.json').read_text(encoding='utf-8'))
OUT=ROOT/f'models/top256_markov{ctx}'
OUT.mkdir(parents=True, exist_ok=True)
indices=IN.read_bytes()
print('context',ctx,'symbols',len(indices),flush=True)
scale=256
trans=defaultdict(Counter)
if len(indices)>ctx:
    st=0
    for x in indices[:ctx]: st=(st<<8)|x
    mask=(1<<(8*(ctx-1)))-1 if ctx>1 else 0
    for pos,x in enumerate(indices[ctx:], start=ctx):
        trans[st][x]+=1
        if ctx==1:
            st=x
        else:
            st=((st & mask)<<8)|x
        if pos % 5_000_000 == 0:
            print('processed',pos,'states',len(trans),flush=True)
print('observed_states',len(trans),flush=True)
rows_path=OUT/f'markov{ctx}_rows_u16.bin'
idx_path=OUT/f'markov{ctx}_index_u64.bin'
with rows_path.open('wb') as rf, idx_path.open('wb') as inf:
    for n,(st,cnt) in enumerate(sorted(trans.items())):
        inf.write(struct.pack('<Q', st))
        denom=sum(cnt.values())+256
        row=[]
        for sym in range(256):
            p=(cnt.get(sym,0)+1)/denom
            row.append(max(1,int(round(-math.log2(p)*scale))))
        m=min(row)
        row=[v-m+1 for v in row]
        rf.write(array.array('H', row).tobytes())
        if n and n%100000==0:
            print('emitted',n,flush=True)
meta={
 'type':f'top256_markov{ctx}','created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
 'symbols':len(indices),'context_symbols':ctx,'alphabet':UNI['alphabet'],
 'observed_states':len(trans),'state_space':f'256^{ctx}',
 'index_file':str(idx_path),'rows_file':str(rows_path),'fallback_costs':UNI['costs']}
(OUT/f'markov{ctx}_meta.json').write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
print(f'markov{ctx} done rows',rows_path.stat().st_size,'index',idx_path.stat().st_size,flush=True)
