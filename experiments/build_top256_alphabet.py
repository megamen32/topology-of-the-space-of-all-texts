#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json, unicodedata
try:
    import regex as re
except ImportError:
    re=None
ROOT=Path('/home/roomhacker/babel-experiments')
PROC=ROOT/'datasets/processed'
OUT=ROOT/'models/top256_alphabet'
OUT.mkdir(parents=True, exist_ok=True)
emoji_re=re.compile(r'\p{Emoji}') if re else None
counter=Counter(); files=[]
for p in sorted(PROC.glob('*.txt')):
    if not p.is_file(): continue
    s=p.read_text(encoding='utf-8', errors='ignore')
    # normalize typography a little but keep case/emojis as observed
    s=s.replace('\r\n','\n').replace('\r','\n').replace('\t',' ')
    counter.update(s)
    files.append({'path':str(p),'bytes':p.stat().st_size,'chars':len(s)})
# force essential symbols to remain even if social corpus shifts
essential=list(' абвгдеёжзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz0123456789\n.,!?;:-—–()[]{}"\'«»/@#%&*+=<>_')
# pick top by frequency, then add essentials, then fill by top
alphabet=[]
seen=set()
def add(ch):
    if ch not in seen and len(alphabet)<256:
        alphabet.append(ch); seen.add(ch)
for ch,_ in counter.most_common():
    add(ch)
    if len(alphabet)>=200: break
for ch in essential:
    add(ch)
for ch,_ in counter.most_common():
    add(ch)
while len(alphabet)<256:
    # private-use placeholders
    add(chr(0xE000+len(alphabet)))
# Coverage
covered=sum(v for ch,v in counter.items() if ch in seen)
total=sum(counter.values())
emoji_counts=[]
if emoji_re:
    for ch,v in counter.items():
        if emoji_re.fullmatch(ch): emoji_counts.append((ch,v))
emoji_counts=sorted(emoji_counts, key=lambda x:(-x[1], x[0]))
report={
    'alphabet_len':len(alphabet),'alphabet':alphabet,'files':files,
    'total_chars':total,'unique_chars':len(counter),'covered_chars':covered,
    'coverage': covered/total if total else 0,
    'top_chars': counter.most_common(300),
    'emoji_total': sum(v for _,v in emoji_counts),
    'emoji_unique': len(emoji_counts),'emoji_top': emoji_counts[:100],
    'unknown_top_if_top256': [(ch,v) for ch,v in counter.most_common() if ch not in seen][:100]
}
(OUT/'alphabet_top256.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'alphabet_top256.txt').write_text(''.join(alphabet),encoding='utf-8')
print('wrote', OUT/'alphabet_top256.json')
print('total_chars',total,'unique',len(counter),'coverage',report['coverage'])
print('emoji_total',report['emoji_total'],'emoji_unique',report['emoji_unique'],'emoji_top',emoji_counts[:30])
print('alphabet:', ''.join(alphabet[:256]))
