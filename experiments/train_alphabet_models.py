#!/usr/bin/env python3
from pathlib import Path
import re, ast, json, math, time, struct, array
from collections import defaultdict, Counter

ROOT=Path('/home/roomhacker/babel-experiments')
REPO=ROOT/'repos/babel-ru-github-pages'
DATA=ROOT/'datasets/processed/sample_ru_en_dialogue_books.txt'
OUT=ROOT/'models/alphabet_sample'
OUT.mkdir(parents=True, exist_ok=True)

# Extract JS const ALPHABET = [...] from worker.js.
js=(REPO/'js/worker.js').read_text(encoding='utf-8')
m=re.search(r'const\s+ALPHABET\s*=\s*(\[[\s\S]*?\]);', js)
if not m:
    raise SystemExit('ALPHABET not found')
arr_src=m.group(1)
# remove JS comments inside array
arr_src=re.sub(r'/\*.*?\*/', '', arr_src, flags=re.S)
arr_src=re.sub(r'//.*', '', arr_src)
alphabet=ast.literal_eval(arr_src)
if len(alphabet)!=256:
    raise SystemExit(f'alphabet len={len(alphabet)} expected 256')
char_to_idx={ch:i for i,ch in enumerate(alphabet)}

raw=DATA.read_text(encoding='utf-8', errors='ignore')
indices=[]
unknown=Counter()
for ch in raw:
    idx=char_to_idx.get(ch)
    if idx is None:
        # normalize common whitespace to space/newline if present
        if ch in '\t\r\u00a0':
            idx=char_to_idx.get(' ')
        else:
            unknown[ch]+=1
            idx=char_to_idx.get(' ',0)
    indices.append(idx)

print('alphabet_len', len(alphabet), flush=True)
print('raw_chars', len(raw), 'indices', len(indices), 'unknown_total', sum(unknown.values()), 'unknown_unique', len(unknown), flush=True)
print('unknown_top', [(repr(k),v) for k,v in unknown.most_common(30)], flush=True)

# Save encoded corpus as uint8.
encoded=OUT/'corpus_indices.u8'
encoded.write_bytes(bytes(indices))

# Unigram costs.
counts=[1]*256
for x in indices: counts[x]+=1
total=sum(counts)
scale=256
rawcost=[round(-math.log2(c/total)*scale) for c in counts]
mn=min(rawcost)
ucosts=[int(c-mn+1) for c in rawcost]
uni={'type':'alphabet_unigram','alphabet':alphabet,'dataset':str(DATA),'encoded':str(encoded),'symbols':len(indices),'unknown_total':sum(unknown.values()),'unknown_top':[(k,v) for k,v in unknown.most_common(100)],'scale':scale,'smoothing':1,'counts':counts,'costs':ucosts,'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
(OUT/'unigram.json').write_text(json.dumps(uni, ensure_ascii=False), encoding='utf-8')
print('unigram wrote', OUT/'unigram.json', 'min', min(ucosts), 'max', max(ucosts), flush=True)
print('top symbols unigram')
for i,c in Counter(dict(enumerate(counts))).most_common(40):
    print(i, repr(alphabet[i]), c, 'cost', ucosts[i], flush=True)

# Markov-3 over alphabet symbols.
trans=defaultdict(Counter)
if len(indices)>=4:
    st=(indices[0]<<16)|(indices[1]<<8)|indices[2]
    for pos,x in enumerate(indices[3:], start=3):
        trans[st][x]+=1
        st=((st & 0xffff)<<8)|x
        if pos % 2_000_000 == 0:
            print('markov processed', pos, 'observed_states', len(trans), flush=True)
print('markov observed_states', len(trans), flush=True)

rows_path=OUT/'markov3_rows_u16.bin'
index_path=OUT/'markov3_index_u32.bin'
with rows_path.open('wb') as rows, index_path.open('wb') as idxf:
    for n,(st,cnt) in enumerate(sorted(trans.items())):
        idxf.write(struct.pack('<I', st))
        denom=sum(cnt.values())+256
        row=[]
        for sym in range(256):
            p=(cnt.get(sym,0)+1)/denom
            row.append(max(1, int(round(-math.log2(p)*scale))))
        mn=min(row)
        row=[x-mn+1 for x in row]
        rows.write(array.array('H', row).tobytes())
        if n and n%100000==0:
            print('markov emitted rows', n, flush=True)
meta={'type':'alphabet_markov3_sparse','alphabet':alphabet,'dataset':str(DATA),'encoded':str(encoded),'symbols':len(indices),'context_symbols':3,'state_space':256**3,'observed_states':len(trans),'scale':scale,'smoothing':1,'fallback_costs':ucosts,'index_file':str(index_path),'rows_file':str(rows_path),'created_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
(OUT/'markov3_meta.json').write_text(json.dumps(meta, ensure_ascii=False), encoding='utf-8')
print('markov wrote', OUT/'markov3_meta.json', 'rows_size', rows_path.stat().st_size, 'index_size', index_path.stat().st_size, flush=True)
