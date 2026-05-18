#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
ALPHA=json.loads((ROOT/'models/top256_alphabet/alphabet_top256.json').read_text(encoding='utf-8'))['alphabet']
PROC=ROOT/'datasets/processed'
OUT=ROOT/'models/student_fsm_v0'
OUT.mkdir(parents=True, exist_ok=True)
emoji_re=re.compile(r'\p{Emoji}')

def cls(ch:str)->str:
    if ch==' ': return 'SPACE'
    if ch=='\n': return 'NEWLINE'
    if emoji_re.fullmatch(ch): return 'EMOJI'
    o=ord(ch)
    if 'а'<=ch.lower()<='я' or ch in 'ёЁ': return 'RU'
    if 'a'<=ch.lower()<='z': return 'EN'
    if ch.isdigit(): return 'DIGIT'
    if ch in '.,!?;:-—–()[]{}"\'«»/@#%&*+=<>_': return 'PUNCT'
    return 'OTHER'

symbol_class={ch:cls(ch) for ch in ALPHA}
trans=defaultdict(Counter)
emit=defaultdict(Counter)
for p in sorted(PROC.glob('*.txt')):
    s=p.read_text(encoding='utf-8', errors='ignore')
    prev='START'
    for ch in s:
        c=symbol_class.get(ch,'OTHER')
        trans[prev][c]+=1
        emit[c][ch]+=1
        prev=c
model={'classes':sorted(set(symbol_class.values())|{'START'}),'symbol_class':symbol_class,'transitions':{k:dict(v) for k,v in trans.items()},'emissions':{k:dict(v) for k,v in emit.items()}}
(OUT/'student_fsm_v0.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
print('states/classes',len(model['classes']))
print('transition_states',len(trans))
for st,cnt in list(trans.items())[:20]:
    print(st,cnt.most_common(10))
