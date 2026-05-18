#!/usr/bin/env python3
from pathlib import Path
import json, math, time, array, struct
ROOT=Path('/home/roomhacker/babel-experiments')
DATA=ROOT/'datasets/processed/sample_ru_en_dialogue_books.txt'
MODEL_DIR=ROOT/'models/markov3_sample'
MODEL_DIR.mkdir(parents=True, exist_ok=True)
COUNTS=MODEL_DIR/'counts_u32.bin'
COSTS=MODEL_DIR/'costs_u16.bin'
META=MODEL_DIR/'meta.json'
S=256**3
A=256
print('reading', DATA, flush=True)
b=DATA.read_bytes()
print('bytes', len(b), 'states', S, 'matrix entries', S*A, flush=True)
# Dense u32 counts: 16,777,216 * 256 * 4 ~= 16 GiB. Server has RAM, but write progressively.
# For MVP start with sparse dict then emit compact observed transitions + default costs, not dense 16GB.
from collections import defaultdict, Counter
trans=defaultdict(Counter)
if len(b) >= 4:
    st=(b[0]<<16)|(b[1]<<8)|b[2]
    for i,x in enumerate(b[3:], start=3):
        trans[st][x]+=1
        st=((st & 0xffff)<<8)|x
        if i % 2_000_000 == 0:
            print('processed', i, 'observed_states', len(trans), flush=True)
print('observed_states', len(trans), flush=True)
scale=256
smoothing=1
# Store sparse rows: state uint32, then 256 uint16 costs per observed state.
# Missing state will use global unigram costs fallback.
# This remains finite and deterministic for rank experiments, while avoiding 8GB+ output.
# For proof experiments, loader treats missing state as fallback row.
counts=[1]*256
for x in b: counts[x]+=1
total=sum(counts)
raw=[round(-math.log2(c/total)*scale) for c in counts]
m=min(raw)
fallback=[int(x-m+1) for x in raw]
rows_path=MODEL_DIR/'rows_u16.bin'
index_path=MODEL_DIR/'index_u32.bin'
with rows_path.open('wb') as rows, index_path.open('wb') as idx:
    for n,(st,cnt) in enumerate(sorted(trans.items())):
        idx.write(struct.pack('<I', st))
        row=[]
        denom=sum(cnt.values())+smoothing*256
        for byte in range(256):
            p=(cnt.get(byte,0)+smoothing)/denom
            row.append(max(1, int(round(-math.log2(p)*scale))))
        mn=min(row)
        row=[x-mn+1 for x in row]
        rows.write(array.array('H', row).tobytes())
        if n and n % 100000 == 0:
            print('emitted rows', n, flush=True)
meta={'type':'markov3_sparse','dataset':str(DATA),'bytes':len(b),'context_bytes':3,'observed_states':len(trans),'state_space':S,'alphabet':256,'scale':scale,'smoothing':smoothing,'fallback_costs':fallback,'index_file':str(index_path),'rows_file':str(rows_path),'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
META.write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
print('wrote', META, flush=True)
print('rows_size', rows_path.stat().st_size, 'index_size', index_path.stat().st_size, flush=True)
