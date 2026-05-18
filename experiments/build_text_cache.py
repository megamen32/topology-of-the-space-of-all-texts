#!/usr/bin/env python3
from pathlib import Path
import unicodedata, regex as re, json
ROOT=Path('/home/roomhacker/babel-experiments')
PROC=ROOT/'datasets/processed'
CACHE=ROOT/'datasets/cache_v1'
CACHE.mkdir(parents=True, exist_ok=True)

sent_re=re.compile(r'(?<=[.!?…])\s+')
word_re=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", re.U)

def norm_text(s:str)->str:
    s=unicodedata.normalize('NFKC',s)
    out=[]
    for ch in s:
        if ch in {'\ufeff','\u200b','\u200c','\u200d','\ufe0f','\ufe0e'}: continue
        if unicodedata.category(ch).startswith('M'): continue
        if ch in '\t\r\u00a0\u2800': ch=' '
        elif ch in {'“','”','„','‟'}: ch='"'
        elif ch in {'’','‘','‚','`','´'}: ch="'"
        elif ch in {'–','—','−'}: ch='-'
        out.append(ch.lower())
    s=''.join(out)
    s=re.sub(r'[ \f\v]+',' ',s)
    s=re.sub(r' *\n+ *','\n',s)
    return s.strip()

texts=[]
for p in sorted(PROC.glob('*.txt')):
    s=p.read_text(encoding='utf-8',errors='ignore')
    ns=norm_text(s)
    if ns:
        texts.append(ns)
full='\n\n'.join(texts)
(CACHE/'normalized.txt').write_text(full,encoding='utf-8')
paragraphs=[p.strip() for p in re.split(r'\n\s*\n+', full) if len(p.strip())>0]
(CACHE/'paragraphs.txt').write_text('\n'.join(paragraphs),encoding='utf-8')
sentences=[]
for para in paragraphs:
    for s in sent_re.split(para):
        s=s.strip()
        if len(s)>=2: sentences.append(s)
(CACHE/'sentences.txt').write_text('\n'.join(sentences),encoding='utf-8')
with (CACHE/'words.txt').open('w',encoding='utf-8') as f:
    n=0
    for s in sentences:
        toks=word_re.findall(s)
        for t in toks:
            f.write(t+'\n'); n+=1
meta={'source_files':[str(p) for p in sorted(PROC.glob('*.txt'))], 'chars':len(full), 'paragraphs':len(paragraphs), 'sentences':len(sentences), 'tokens':n}
(CACHE/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
