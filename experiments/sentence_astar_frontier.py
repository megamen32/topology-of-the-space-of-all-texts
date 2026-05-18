#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from heapq import heappush, heappop
import json, argparse, random, time, regex as re

ROOT=Path('/home/roomhacker/babel-experiments')
OUT=ROOT/'models/astar_sentence_frontier_v1'
OUT.mkdir(parents=True, exist_ok=True)
SENT=json.loads((ROOT/'models/sentence_student_v1/sentence_student_v1.json').read_text(encoding='utf-8'))
WORD=json.loads((ROOT/'models/word_student_v1/word_student_v1.json').read_text(encoding='utf-8'))
PARA=json.loads((ROOT/'models/paragraph_student_v1/paragraph_student_v1.json').read_text(encoding='utf-8'))
word_trans=WORD['transitions']
abstract=WORD.get('abstract_emissions',{})

def template_energy(count:int)->int:
    return max(1, int(100000/(max(1,count)**0.5)))

TEMPLATES=[]
for row in SENT['templates'][:3000]:
    TEMPLATES.append((template_energy(row.get('count',1)), row['template'], row.get('samples',[])[:2], row.get('count',1)))
TEMPLATES.sort(key=lambda x:(x[0], x[1]))

PARA_SHAPES=[]
for row in PARA.get('top_paragraph_shapes',[])[:1600]:
    PARA_SHAPES.append((template_energy(row.get('count',1)), row['shape'], row.get('count',1)))
PARA_SHAPES.sort(key=lambda x:(x[0], x[1]))

def realize(tok,rng):
    arr=abstract.get(tok)
    if arr:
        return rng.choice(arr)
    return tok.replace('<','').replace('>','')

def detok(tokens):
    out=''
    for t in tokens:
        if not t or t=='</s>':
            continue
        if not out:
            out=t
        elif re.fullmatch(r'[.,!?;:)]', t):
            out+=t
        else:
            out+=' '+t
    return out

def type_ok(typ,k):
    if k is None: return False
    if typ=='R': return k=='<ru>' or bool(re.fullmatch(r'[а-яё]+',k))
    if typ=='L': return k=='<en>' or bool(re.fullmatch(r'[a-z]+',k))
    if typ=='N': return k=='<num>' or bool(re.fullmatch(r'[0-9]+',k))
    if typ=='E': return k=='<emoji>' or bool(re.search(r'\p{Emoji}',k))
    if typ=='T': return k in ['.','!','?','</s>']
    if typ=='P': return k in [',',';',':']
    return True

def generate_sentence(template,rng,branch=32):
    toks=[]
    prev='<s>'
    e=0
    for typ in template.split():
        trans=word_trans.get(prev) or word_trans.get('<s>') or {}
        cand=[(v,k) for k,v in trans.items() if type_ok(typ,k)]
        if not cand:
            tok='.' if typ=='T' else '<ru>'
            freq=1
        else:
            cand.sort(reverse=True)
            cand=cand[:branch]
            values=[v for v,k in cand]
            keys=[k for v,k in cand]
            tok=rng.choices(keys, weights=values, k=1)[0]
            freq=dict((k,v) for v,k in cand).get(tok,1)
        e += max(1,int(10000/(max(1,freq)**0.5)))
        if tok=='</s>': tok='.'
        tok=realize(tok,rng)
        toks.append(tok)
        prev=tok
    s=detok(toks).replace(' .','.').replace(' !','!').replace(' ?','?')
    if not re.search(r'[.!?…]$',s):
        s+='.'
    return s,e

def sentence_frontier(topk:int,seed:int):
    rng=random.Random(seed)
    q=[]
    for e,tpl,samples,cnt in TEMPLATES[:256]:
        heappush(q,(e,tpl,samples,cnt))
    out=[]
    seen=set()
    while q and len(out)<topk:
        e,tpl,samples,cnt=heappop(q)
        if tpl in seen: continue
        seen.add(tpl)
        txt,e2=generate_sentence(tpl,rng)
        out.append({'rank':len(out),'energy':e+e2,'template_energy':e,'template_count':cnt,'template':tpl,'text':txt,'corpus_samples':samples})
    return out

def paragraph_frontier(topk:int,seed:int):
    rng=random.Random(seed)
    q=[]
    for e,shape,cnt in PARA_SHAPES[:256]:
        heappush(q,(e,shape,cnt))
    out=[]
    seen=set()
    while q and len(out)<topk:
        e,shape,cnt=heappop(q)
        if shape in seen: continue
        seen.add(shape)
        total=e
        parts=[]
        for tpl in shape.split(' | ')[:10]:
            s,e2=generate_sentence(tpl,rng)
            parts.append(s)
            total+=e2
        out.append({'rank':len(out),'energy':total,'shape_energy':e,'shape_count':cnt,'shape':shape,'text':' '.join(parts)[:1500]})
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--topk',type=int,default=200)
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--mode',choices=['sentence','paragraph','both'],default='both')
    args=ap.parse_args()
    t=time.time()
    result={'version':'B2_sentence_paragraph_frontier','topk':args.topk,'seed':args.seed,'mode':args.mode,'started_at':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    if args.mode in ['sentence','both']:
        result['sentences']=sentence_frontier(args.topk,args.seed)
    if args.mode in ['paragraph','both']:
        result['paragraphs']=paragraph_frontier(args.topk,args.seed+1)
    result['elapsed_seconds']=round(time.time()-t,3)
    out=OUT/f'frontier_{args.mode}_top{args.topk}_seed{args.seed}.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'wrote':str(out),'elapsed_seconds':result['elapsed_seconds'],'sentence_count':len(result.get('sentences',[])),'paragraph_count':len(result.get('paragraphs',[]))},ensure_ascii=False,indent=2),flush=True)
    for p in result.get('paragraphs',[])[:10]:
        print(f"#{p['rank']} E={p['energy']} {p['text']}",flush=True)
if __name__=='__main__':
    main()
