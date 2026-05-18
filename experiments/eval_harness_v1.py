#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from collections import Counter,defaultdict
import json, math, random, regex as re, statistics, itertools, time

ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
OUT=ROOT/'models/eval_harness_v1'
OUT.mkdir(parents=True, exist_ok=True)

TOK_RE=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", re.U)
SENT_RE=re.compile(r'(?<=[.!?…])\s+')

# small heldout corpus
held=[]
for fp in sorted(CACHE.glob('*.txt'))[-8:]:
    try:
        txt=fp.read_text(encoding='utf-8',errors='ignore')[:800000]
    except: continue
    held.extend([x.strip() for x in SENT_RE.split(txt) if x.strip()])
held=held[:12000]

configs=[]
for clusters in [64,128]:
  for ctx in [2,3,5]:
    for mem in [1,2]:
      configs.append({'clusters':clusters,'context':ctx,'memory':mem})

random.shuffle(configs)


def tokenize(s):
    return TOK_RE.findall(s.lower())

# cheap pseudo clustering by hashed contexts

def build_clusterer(context_window:int, n_clusters:int):
    ctx=defaultdict(Counter)
    for sent in held[:6000]:
        toks=tokenize(sent)
        for i,t in enumerate(toks):
            left=toks[max(0,i-context_window):i]
            right=toks[i+1:i+1+context_window]
            sig=' '.join(left+['|']+right)
            ctx[t][hash(sig)%2048]+=1
    mapping={}
    for tok,c in ctx.items():
        # deterministic pseudo centroid
        h=sum(k*v for k,v in c.items())
        mapping[tok]=h % n_clusters
    return mapping


def build_model(cfg):
    mapping=build_clusterer(cfg['context'], cfg['clusters'])
    trans=defaultdict(Counter)
    cluster_trans=defaultdict(Counter)
    sent_templates=Counter()

    for sent in held[:8000]:
        toks=tokenize(sent)
        if not toks: continue
        prev='<s>'
        active=[]
        tpl=[]
        for t in toks:
            cl=mapping.get(t,0)
            tpl.append(f'C{cl}')
            state=(prev, tuple(active[-cfg['memory']:]))
            trans[state][t]+=1
            cluster_trans[tuple(active[-cfg['memory']:])][cl]+=1
            active.append(cl)
            prev=t
        sent_templates[' '.join(tpl[:48])] += 1

    return {
      'cfg':cfg,
      'mapping_size':len(mapping),
      'transitions':trans,
      'cluster_transitions':cluster_trans,
      'templates':sent_templates,
    }


def sentence_energy(model,sent):
    toks=tokenize(sent)
    if not toks: return 0
    trans=model['transitions']
    mem=model['cfg']['memory']
    prev='<s>'
    active=[]
    e=0.0
    for t in toks:
        state=(prev, tuple(active[-mem:]))
        row=trans.get(state)
        if not row:
            e += 25.0
        else:
            total=sum(row.values())
            p=(row.get(t,0)+1)/(total+len(row))
            e += -math.log2(p)
        cl=hash(t)%model['cfg']['clusters']
        active.append(cl)
        prev=t
    return e/max(1,len(toks))


def frontier_sample(model,k=40):
    tpl=model['templates'].most_common(k)
    out=[]
    for t,c in tpl:
        toks=t.split()[:12]
        # realize clusters as placeholders only for collapse metrics
        text=' '.join(toks)
        out.append(text)
    return out


def collapse_score(samples):
    if not samples: return 1e9
    rep=[]
    uniq=[]
    for s in samples:
        toks=s.split()
        if not toks: continue
        uniq.append(len(set(toks))/len(toks))
        runs=max((len(list(g)) for _,g in itertools.groupby(toks)), default=1)
        rep.append(runs)
    return statistics.mean(rep) - statistics.mean(uniq)

leader=[]
started=time.time()
for i,cfg in enumerate(configs,1):
    print(f'[{i}/{len(configs)}] cfg={cfg}', flush=True)
    model=build_model(cfg)
    energies=[sentence_energy(model,s) for s in held[:2500]]
    avg_e=statistics.mean(energies)
    samples=frontier_sample(model)
    collapse=collapse_score(samples)
    size=(len(model['transitions'])+len(model['templates']))
    score=avg_e + collapse*2 + math.log2(size+1)/20
    row={
      'cfg':cfg,
      'avg_energy':round(avg_e,4),
      'collapse_score':round(collapse,4),
      'model_size_proxy':size,
      'final_score':round(score,4),
      'frontier_preview':samples[:5],
    }
    leader.append(row)
    leader.sort(key=lambda x:x['final_score'])
    (OUT/'leaderboard.json').write_text(json.dumps({'updated_at':time.time(),'leaderboard':leader},ensure_ascii=False,indent=2),encoding='utf-8')

best=leader[0]
summary={
 'configs_tested':len(leader),
 'best':best,
 'elapsed_seconds':round(time.time()-started,3)
}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
