#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from collections import Counter, defaultdict
import json, regex as re, math
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
SENT=ROOT/'models/sentence_student_v1/sentence_student_v1.json'
OUT=ROOT/'models/paragraph_student_v1'
OUT.mkdir(parents=True, exist_ok=True)

sent_re=re.compile(r'(?<=[.!?…])\s+')
tok_re=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", re.U)

def tok_type(t):
    if re.fullmatch(r'\p{Emoji}+',t): return 'E'
    if re.fullmatch(r'[а-яё]+',t): return 'R'
    if re.fullmatch(r'[a-z]+',t): return 'L'
    if re.fullmatch(r'[0-9]+',t): return 'N'
    if t in '.!?…': return 'T'
    if t in ',;:': return 'P'
    return 'O'

def sent_template(s):
    toks=[t for t in tok_re.findall(s) if t.strip()]
    return ' '.join(tok_type(t) for t in toks[:48]) or 'EMPTY'

paragraphs=(CACHE/'paragraphs.txt').read_text(encoding='utf-8',errors='ignore').splitlines()
para_len=Counter(); para_templates=Counter(); para_trans=defaultdict(Counter); samples=[]
for p in paragraphs:
    ss=[x.strip() for x in sent_re.split(p) if x.strip()]
    if not ss: continue
    para_len[min(len(ss),40)] += 1
    sts=[sent_template(s) for s in ss[:16]]
    shape=' | '.join(sts)
    para_templates[shape]+=1
    prev='<p>'
    for st in sts:
        para_trans[prev][st]+=1
        prev=st
    para_trans[prev]['</p>']+=1
    if len(samples)<50 and 1 <= len(ss) <= 6:
        samples.append(p[:500])

# Compact export: top paragraph shapes + transition rows for top sentence templates.
top_shapes=[{'shape':k,'count':v} for k,v in para_templates.most_common(800)]
# Keep only top transitions per state to avoid huge browser payload.
trans={k:dict(v.most_common(80)) for k,v in para_trans.items() if sum(v.values())>=2}
model={
 'version':'paragraph_student_v1',
 'paragraph_lengths':dict(para_len),
 'top_paragraph_shapes':top_shapes,
 'paragraph_transitions':trans,
 'samples':samples,
 'stats':{'paragraphs':len(paragraphs),'unique_shapes':len(para_templates),'transition_states':len(para_trans)}
}
(OUT/'paragraph_student_v1.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
print(json.dumps(model['stats'],ensure_ascii=False,indent=2))
print('top lengths', para_len.most_common(20))
print('top shapes', top_shapes[:5])
