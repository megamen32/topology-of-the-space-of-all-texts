#!/usr/bin/env python3
from pathlib import Path
import json
from collections import defaultdict

ROOT=Path('/home/roomhacker/babel-experiments')
UNI=json.loads((ROOT/'models/unigram_sample.json').read_text())
M3=json.loads((ROOT/'models/markov3_sample/meta.json').read_text())

ucosts=UNI['costs']
fallback=M3['fallback_costs']

# Load sparse rows.
index=[]
with open(M3['index_file'],'rb') as f:
    data=f.read()
    for i in range(0,len(data),4):
        index.append(int.from_bytes(data[i:i+4],'little'))

rows={}
with open(M3['rows_file'],'rb') as f:
    for st in index:
        raw=f.read(256*2)
        row=[int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]
        rows[st]=row

print('loaded rows', len(rows))

def byte_repr(b:int)->str:
    if b == 32:
        return '␠'
    if b == 10:
        return '\\n'
    if 32 <= b <= 126:
        return chr(b)
    return f'{b:02x}'

# Best unigram bytes.
ubest=sorted(range(256), key=lambda b:(ucosts[b], b))[:32]
print('\n== best unigram bytes ==')
for b in ubest:
    print(f'{b:3d} {byte_repr(b):>4} cost={ucosts[b]}')

# Greedy Markov-3 generation.
# Start state: three spaces.
state=(32<<16)|(32<<8)|32
out=[]
for _ in range(128):
    row=rows.get(state)
    if row is None:
        row=fallback
    b=min(range(256), key=lambda x:(row[x], x))
    out.append(b)
    state=((state & 0xffff)<<8)|b

print('\n== greedy Markov-3 first 128 bytes ==')
print(bytes(out))
try:
    print(bytes(out).decode('utf-8'))
except Exception as e:
    print('decode error', e)

# Beam search small strings.
beam=[(0, b'   ')]
for step in range(24):
    new=[]
    for energy,prefix in beam:
        st=(prefix[-3]<<16)|(prefix[-2]<<8)|prefix[-1]
        row=rows.get(st)
        if row is None:
            row=fallback
        best=sorted(range(256), key=lambda b:(row[b], b))[:8]
        for b in best:
            new.append((energy+row[b], prefix+bytes([b])))
    new.sort(key=lambda x:(x[0], x[1]))
    beam=new[:32]

print('\n== best Markov-3 continuations ==')
for i,(e,p) in enumerate(beam[:16]):
    tail=p[3:]
    try:
        txt=tail.decode('utf-8')
    except:
        txt=repr(tail)
    print(f'{i:02d} energy={e:5d} text={txt!r}')
