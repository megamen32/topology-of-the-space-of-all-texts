#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json, math, time
ROOT=Path('/home/roomhacker/babel-experiments')
DATA=ROOT/'datasets/processed/sample_ru_en_dialogue_books.txt'
OUT=ROOT/'models/unigram_sample.json'
print('reading', DATA, flush=True)
b=DATA.read_bytes()
print('bytes', len(b), flush=True)
counts=[1]*256
for x in b: counts[x]+=1
total=sum(counts)
scale=256
raw=[round(-math.log2(c/total)*scale) for c in counts]
m=min(raw)
costs=[int(x-m+1) for x in raw]
model={'type':'unigram','dataset':str(DATA),'bytes':len(b),'smoothing':1,'scale':scale,'counts':counts,'costs':costs,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
OUT.write_text(json.dumps(model, ensure_ascii=False), encoding='utf-8')
print('wrote', OUT, 'min_cost', min(costs), 'max_cost', max(costs), flush=True)
print('top bytes:')
for byte,c in Counter(dict(enumerate(counts))).most_common(30):
    ch=chr(byte) if 32 <= byte <= 126 else f'\\x{byte:02x}'
    print(byte, repr(ch), c, 'cost', costs[byte], flush=True)
