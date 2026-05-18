#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, math, time, struct, array

ROOT=Path('/home/roomhacker/babel-experiments')
PROC=ROOT/'datasets/processed'
ALPHA=json.loads((ROOT/'models/top256_alphabet/alphabet_top256.json').read_text(encoding='utf-8'))
OUT=ROOT/'models/top256_retrained'
OUT.mkdir(parents=True, exist_ok=True)

alphabet=ALPHA['alphabet']
char_to_idx={c:i for i,c in enumerate(alphabet)}

texts=[]
for p in sorted(PROC.glob('*.txt')):
    try:
        texts.append(p.read_text(encoding='utf-8', errors='ignore'))
    except Exception:
        pass
corpus='\n'.join(texts)
print('corpus_chars', len(corpus), flush=True)

indices=[]
unk=0
for ch in corpus:
    idx=char_to_idx.get(ch)
    if idx is None:
        idx=0
        unk+=1
    indices.append(idx)
print('encoded_symbols', len(indices), 'unknown_mapped_to_zero', unk, flush=True)
(Path(OUT/'corpus.u8')).write_bytes(bytes(indices))

# Unigram
counts=[1]*256
for x in indices:
    counts[x]+=1
scale=256
total=sum(counts)
raw=[round(-math.log2(c/total)*scale) for c in counts]
mn=min(raw)
uc=[int(v-mn+1) for v in raw]
uni={
 'type':'top256_unigram','created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
 'symbols':len(indices),'unknown':unk,'alphabet':alphabet,'costs':uc,'counts':counts}
(OUT/'unigram.json').write_text(json.dumps(uni,ensure_ascii=False),encoding='utf-8')
print('unigram done', flush=True)
print('top symbols:')
for i,c in Counter(dict(enumerate(counts))).most_common(40):
    print(i, repr(alphabet[i]), c, 'cost', uc[i], flush=True)

# Markov-3
trans=defaultdict(Counter)
if len(indices)>=4:
    st=(indices[0]<<16)|(indices[1]<<8)|indices[2]
    for pos,x in enumerate(indices[3:], start=3):
        trans[st][x]+=1
        st=((st & 0xffff)<<8)|x
        if pos % 5_000_000 == 0:
            print('processed', pos, 'states', len(trans), flush=True)
print('observed_states', len(trans), flush=True)
rows_path=OUT/'markov3_rows_u16.bin'
idx_path=OUT/'markov3_index_u32.bin'
with rows_path.open('wb') as rf, idx_path.open('wb') as inf:
    for n,(st,cnt) in enumerate(sorted(trans.items())):
        inf.write(struct.pack('<I', st))
        denom=sum(cnt.values())+256
        row=[]
        for sym in range(256):
            p=(cnt.get(sym,0)+1)/denom
            row.append(max(1,int(round(-math.log2(p)*scale))))
        m=min(row)
        row=[v-m+1 for v in row]
        rf.write(array.array('H', row).tobytes())
        if n and n % 100000 == 0:
            print('emitted', n, flush=True)
meta={
 'type':'top256_markov3','created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z'),
 'symbols':len(indices),'unknown':unk,'alphabet':alphabet,
 'observed_states':len(trans),'state_space':256**3,
 'index_file':str(idx_path),'rows_file':str(rows_path),'fallback_costs':uc}
(OUT/'markov3_meta.json').write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
print('markov3 done rows', rows_path.stat().st_size, 'index', idx_path.stat().st_size, flush=True)
