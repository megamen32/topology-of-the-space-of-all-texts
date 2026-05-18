#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, math, unicodedata
import regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
PROC=ROOT/'datasets/processed'
ALPHA=json.loads((ROOT/'models/top256_alphabet_v2/alphabet_top256_v2.json').read_text(encoding='utf-8'))['alphabet']
OUT=ROOT/'models/student_fsm_v1'
OUT.mkdir(parents=True, exist_ok=True)
emoji_re=re.compile(r'\p{Emoji}')

def norm_char(ch):
    if ch in {'\ufeff','\u200b','\u200c','\u200d','\ufe0f','\ufe0e'}: return ''
    if unicodedata.category(ch).startswith('M'): return ''
    if ch in '\t\r\u00a0\u2800': return ' '
    if ch in {'“','”','„','‟'}: return '"'
    if ch in {'’','‘','‚','`','´'}: return "'"
    if ch in {'–','—','−'}: return '-'
    x=ch.lower(); return x if len(x)==1 else x[:1]

def cls(ch):
    if ch==' ': return 'SPACE'
    if ch=='\n': return 'NEWLINE'
    if emoji_re.fullmatch(ch): return 'EMOJI'
    if 'а'<=ch<='я' or ch=='ё': return 'RU'
    if 'a'<=ch<='z': return 'EN'
    if ch.isdigit(): return 'DIGIT'
    if ch in '.,!?;:-()[]{}"\'«»/@#%&*+=<>_': return 'PUNCT'
    return 'OTHER'

alpha_set=set(ALPHA); symbol_class={ch:cls(ch) for ch in ALPHA}
trans=defaultdict(Counter); emit=defaultdict(Counter); tri=defaultdict(Counter); unk=0; total=0
for p in sorted(PROC.glob('*.txt')):
    s=p.read_text(encoding='utf-8',errors='ignore')
    prev2=('START','START')
    prev='START'
    for raw in s:
        ch=norm_char(raw)
        if not ch: continue
        if ch not in alpha_set:
            ch=' '
            unk+=1
        c=symbol_class[ch]
        trans[prev][c]+=1
        tri[prev2][c]+=1
        emit[c][ch]+=1
        prev2=(prev2[1],c); prev=c; total+=1
# integer costs from counts with smoothing
classes=sorted(set(symbol_class.values())|{'START'})
def costs(counter, keys):
    vals={k:counter.get(k,0)+1 for k in keys}
    tot=sum(vals.values()); raw={k:round(-math.log2(v/tot)*256) for k,v in vals.items()}; mn=min(raw.values())
    return {k:int(v-mn+1) for k,v in raw.items()}
model={'version':'student_fsm_v1_normalized','alphabet':ALPHA,'classes':classes,'symbol_class':symbol_class,'transitions':{k:dict(v) for k,v in trans.items()},'trigram_class_transitions':{ '|'.join(k):dict(v) for k,v in tri.items()},'emissions':{k:dict(v) for k,v in emit.items()},'transition_costs':{k:costs(v,classes) for k,v in trans.items()},'emission_costs':{k:costs(v,[ch for ch in ALPHA if symbol_class[ch]==k]) for k,v in emit.items()},'stats':{'symbols':total,'unknown_mapped_to_space':unk}}
(OUT/'student_fsm_v1.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
print('wrote',OUT/'student_fsm_v1.json','symbols',total,'unknown',unk,'classes',classes)
for k,v in trans.items(): print(k, v.most_common(8))
