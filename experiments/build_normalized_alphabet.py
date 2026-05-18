#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import json, unicodedata
import regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
PROC=ROOT/'datasets/processed'
OUT=ROOT/'models/top256_alphabet_v2'
OUT.mkdir(parents=True, exist_ok=True)
emoji_re=re.compile(r'\p{Emoji}')

def norm_char(ch:str)->str:
    # remove zero-width / BOM / variation selectors / combining marks that caused fake alphabet slots
    if ch in {'\ufeff','\u200b','\u200c','\u200d','\ufe0f','\ufe0e'}:
        return ''
    cat=unicodedata.category(ch)
    if cat.startswith('M'):
        return ''
    if ch in '\t\r\u00a0\u2800':
        return ' '
    if ch in {'“','”','„','‟'}:
        return '"'
    if ch in {'’','‘','‚','`','´'}:
        return "'"
    if ch in {'–','—','−'}:
        return '-'
    # case-insensitive for RU/EN and most latin/cyrillic letters
    return ch.lower()

counter=Counter(); raw_unique=Counter(); files=[]
for p in sorted(PROC.glob('*.txt')):
    s=p.read_text(encoding='utf-8', errors='ignore')
    files.append({'path':str(p),'bytes':p.stat().st_size,'chars':len(s)})
    for ch in s:
        raw_unique[ch]+=1
        n=norm_char(ch)
        if n:
            counter[n]+=1

# Essentials after normalization
essential=list(' абвгдеёжзийклмнопрстуфхцчшщъыьэюяabcdefghijklmnopqrstuvwxyz0123456789\n.,!?;:-()[]{}"\'«»/@#%&*+=<>_')
# Build: first top frequent, then essentials, then top again, no invisible/empty.
alphabet=[]; seen=set()
def add(ch):
    if not ch or ch in seen: return
    if len(ch)!=1 or unicodedata.category(ch) in {'Cf','Mn','Mc','Me'}: return
    if len(alphabet)<256:
        alphabet.append(ch); seen.add(ch)
for ch,_ in counter.most_common():
    add(ch)
    if len(alphabet)>=210: break
for ch in essential: add(ch)
for ch,_ in counter.most_common(): add(ch)
while len(alphabet)<256:
    add(chr(0xE000+len(alphabet)))
covered=sum(v for ch,v in counter.items() if ch in seen)
total=sum(counter.values())
emoji_counts=sorted([(ch,v) for ch,v in counter.items() if emoji_re.fullmatch(ch)], key=lambda x:(-x[1],x[0]))
not_in=sorted([(ch,v) for ch,v in counter.items() if ch not in seen], key=lambda x:(-x[1],x[0]))
report={'version':'v2_normalized_casefold_no_invisible','alphabet_len':len(alphabet),'alphabet':alphabet,'files':files,'total_chars':total,'unique_chars':len(counter),'raw_unique_chars':len(raw_unique),'covered_chars':covered,'coverage':covered/total if total else 0,'top_chars':counter.most_common(400),'emoji_total':sum(v for _,v in emoji_counts),'emoji_unique':len(emoji_counts),'emoji_top':emoji_counts[:120],'unknown_top_if_top256':not_in[:120]}
(OUT/'alphabet_top256_v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'alphabet_top256_v2.txt').write_text(''.join(alphabet),encoding='utf-8')
print('alphabet_len',len(alphabet),'coverage',report['coverage'],'unique',len(counter),'raw_unique',len(raw_unique),'emoji_unique',len(emoji_counts))
print('alphabet', ''.join(alphabet))
print('not_in_top30', [(c,v,unicodedata.name(c,'?')) for c,v in not_in[:30]])
