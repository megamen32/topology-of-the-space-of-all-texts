#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
OUT=ROOT/'models/text_stats_v1'
OUT.mkdir(parents=True, exist_ok=True)
text=(CACHE/'normalized.txt').read_text(encoding='utf-8')
chars=Counter(text)
words=Counter((CACHE/'words.txt').read_text(encoding='utf-8').splitlines())
sents=(CACHE/'sentences.txt').read_text(encoding='utf-8').splitlines()
paras=(CACHE/'paragraphs.txt').read_text(encoding='utf-8').splitlines()
# word bigrams and sentence starters
bigrams=Counter(); starters=Counter(); endings=Counter()
for s in sents:
    toks=[t for t in re.findall(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", s) if t.strip()]
    if toks:
        starters[toks[0]]+=1; endings[toks[-1]]+=1
    for a,b in zip(toks,toks[1:]): bigrams[(a,b)]+=1
# char bigrams/trigrams for score support
cb=Counter(zip(text,text[1:])); ct=Counter(zip(text,text[1:],text[2:]))
report={
 'chars_total':sum(chars.values()), 'chars_unique':len(chars),
 'words_total':sum(words.values()), 'words_unique':len(words),
 'sentences':len(sents),'paragraphs':len(paras),
 'top_chars':chars.most_common(512),
 'top_words':words.most_common(5000),
 'top_starters':starters.most_common(1000),
 'top_endings':endings.most_common(1000),
 'top_word_bigrams':[(list(k),v) for k,v in bigrams.most_common(10000)],
 'top_char_bigrams':[( ''.join(k),v) for k,v in cb.most_common(5000)],
 'top_char_trigrams':[( ''.join(k),v) for k,v in ct.most_common(5000)],
}
(OUT/'stats.json').write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')
print('chars',report['chars_total'],report['chars_unique'],'words',report['words_total'],report['words_unique'],'sentences',len(sents),'paragraphs',len(paras))
print('top chars', chars.most_common(20))
print('top words', words.most_common(30))
