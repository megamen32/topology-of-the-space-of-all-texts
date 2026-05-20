#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import json,regex as re,hashlib
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
TOK=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]",re.U)
N=5000;CLUSTERS=64;CTX=3
freq=Counter(); texts=[]
for fp in sorted(CACHE.glob('*.txt'))[:20]:
 t=fp.read_text(encoding='utf-8',errors='ignore').lower()[:400000]
 texts.append(t)
 freq.update(TOK.findall(t))
vocab=[t for t,_ in freq.most_common(N)]
vs=set(vocab)
ctxCount=defaultdict(Counter)
for t in texts:
 toks=[x for x in TOK.findall(t) if x in vs]
 for i,tok in enumerate(toks):
   ctx='|'.join(toks[max(0,i-CTX):i]+toks[i+1:i+1+CTX])
   ctxCount[tok][ctx]+=1
mapping={}
for tok in vocab:
 h=hashlib.sha256((' '.join(k for k,_ in ctxCount[tok].most_common(8))).encode()).hexdigest()
 mapping[tok]=int(h[:8],16)%CLUSTERS
trans=defaultdict(Counter)
for t in texts:
 toks=[x for x in TOK.findall(t) if x in vs]
 cls=[mapping[x] for x in toks]
 for a,b in zip(cls,cls[1:]): trans[str(a)][str(b)]+=1
out={'version':'cluster_student_v1','vocab':len(vocab),'clusters':CLUSTERS,'context_window':CTX,'mapping':mapping,'cluster_transitions':{k:dict(v) for k,v in trans.items()}}
(Path(ROOT/'models/cluster_student_v1/model.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'vocab':len(vocab),'clusters':CLUSTERS,'states':len(trans)},indent=2))
