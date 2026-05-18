#!/usr/bin/env python3
from pathlib import Path
from collections import Counter
import regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
PROC=ROOT/'datasets/processed'
emoji_re=re.compile(r'\p{Emoji}')
for p in sorted(PROC.glob('*.txt')):
    try:
        s=p.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        continue
    em=emoji_re.findall(s)
    c=Counter(em)
    print(p.name, 'bytes', p.stat().st_size, 'emoji_total', len(em), 'emoji_unique', len(c), 'top', c.most_common(20))
