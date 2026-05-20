#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import json,regex as re,random,math
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
OUT=ROOT/'models/cluster_student_v2'; OUT.mkdir(parents=True,exist_ok=True)
TOK=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]",re.U)
N=5000; FEATURES=512; K=64; CTX=3; ITERS=12
freq=Counter(); texts=[]
for fp in sorted(CACHE.glob('*.txt'))[:28]:
    t=fp.read_text(encoding='utf-8',errors='ignore').lower()[:600000]
    texts.append(t); freq.update(TOK.findall(t))
vocab=[t for t,_ in freq.most_common(N)]; idx={t:i for i,t in enumerate(vocab)}; vs=set(vocab)
def hfeat(tok,side): return (hash(side+'|'+tok) % FEATURES)
vec=[[0.0]*FEATURES for _ in vocab]
for t in texts:
    toks=[x for x in TOK.findall(t) if x in vs]
    for i,tok in enumerate(toks):
        v=vec[idx[tok]]
        for j in range(max(0,i-CTX),i): v[hfeat(toks[j],'L')]+=1.0/(i-j)
        for j in range(i+1,min(len(toks),i+1+CTX)): v[hfeat(toks[j],'R')]+=1.0/(j-i)
# tf/log normalize + l2
for v in vec:
    norm=0.0
    for i,x in enumerate(v):
        if x: v[i]=math.log1p(x); norm+=v[i]*v[i]
    norm=math.sqrt(norm) or 1.0
    for i,x in enumerate(v): v[i]=x/norm
random.seed(42)
cent=[vec[i][:] for i in random.sample(range(len(vec)),K)]
assign=[0]*len(vec)
for it in range(ITERS):
    changed=0
    for n,v in enumerate(vec):
        best=0; bests=-9
        for c,cv in enumerate(cent):
            s=sum(a*b for a,b in zip(v,cv))
            if s>bests: bests=s; best=c
        if assign[n]!=best: changed+=1; assign[n]=best
    sums=[[0.0]*FEATURES for _ in range(K)]; counts=[0]*K
    for a,v in zip(assign,vec):
        counts[a]+=1
        sv=sums[a]
        for i,x in enumerate(v): sv[i]+=x
    for c in range(K):
        if counts[c]:
            norm=0.0
            for i,x in enumerate(sums[c]):
                sums[c][i]=x/counts[c]; norm+=sums[c][i]*sums[c][i]
            norm=math.sqrt(norm) or 1.0
            cent[c]=[x/norm for x in sums[c]]
    print(json.dumps({'iter':it+1,'changed':changed,'nonempty':sum(1 for x in counts if x)},ensure_ascii=False),flush=True)
maptok={tok:assign[i] for tok,i in idx.items()}
trans=defaultdict(Counter)
for t in texts:
    toks=[x for x in TOK.findall(t) if x in vs]
    cls=[maptok[x] for x in toks]
    for a,b in zip(cls,cls[1:]): trans[str(a)][str(b)]+=1
clusters=[]
for c in range(K):
    members=[tok for tok,a in maptok.items() if a==c]
    members.sort(key=lambda x:freq[x], reverse=True)
    clusters.append({'id':c,'size':len(members),'top':members[:50]})
out={'version':'cluster_student_v2_kmeans','vocab':len(vocab),'clusters':K,'features':FEATURES,'context_window':CTX,'iters':ITERS,'mapping':maptok,'cluster_transitions':{k:dict(v) for k,v in trans.items()},'cluster_summaries':clusters}
(OUT/'model.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'vocab':len(vocab),'clusters':K,'states':len(trans),'out':str(OUT/'model.json')},ensure_ascii=False,indent=2))
