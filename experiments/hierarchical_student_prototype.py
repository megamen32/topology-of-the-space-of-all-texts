#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from collections import Counter
import json, re
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
OUT=ROOT/'models/hierarchical_proto_v1'
OUT.mkdir(parents=True, exist_ok=True)

def split_sentences(text:str):
    return re.split(r'(?<=[.!?…])\s+', text)

def split_words(text:str):
    return re.findall(r'\w+|[^\w\s]', text, flags=re.U)

para_count=Counter(); sent_templates=Counter(); token_trans=Counter()
files=list(CACHE.glob('*.txt'))[:16]
for fp in files:
    try: txt=fp.read_text(encoding='utf-8',errors='ignore')
    except: continue
    paras=[p.strip() for p in txt.split('\n\n') if p.strip()]
    for p in paras:
        sents=[s.strip() for s in split_sentences(p) if s.strip()]
        para_count[len(sents)] += 1
        for s in sents:
            toks=split_words(s.lower())
            shape=' '.join('W' if re.match(r'\w+$',t) else t for t in toks[:64])
            sent_templates[shape]+=1
            for a,b in zip(['<s>']+toks,toks+['</s>']): token_trans[(a,b)] += 1
summary={
  'paragraph_count_patterns':para_count.most_common(20),
  'sentence_templates':sent_templates.most_common(50),
  'token_transitions':token_trans.most_common(50),
}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'status':'ok','summary_file':str(OUT/'summary.json'),'templates':len(sent_templates)},ensure_ascii=False,indent=2))
