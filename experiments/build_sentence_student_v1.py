#!/usr/bin/env python3
from pathlib import Path
from collections import Counter, defaultdict
import json, regex as re, random
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
STATS=ROOT/'models/text_stats_v1/stats.json'
WORD=ROOT/'models/word_student_v1/word_student_v1.json'
OUT=ROOT/'models/sentence_student_v1'
OUT.mkdir(parents=True, exist_ok=True)

stats=json.loads(STATS.read_text(encoding='utf-8'))
word=json.loads(WORD.read_text(encoding='utf-8'))
sentences=(CACHE/'sentences.txt').read_text(encoding='utf-8').splitlines()
paragraphs=(CACHE/'paragraphs.txt').read_text(encoding='utf-8').splitlines()
tok_re=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", re.U)

def tok_type(t):
    if re.fullmatch(r'\p{Emoji}+',t): return 'E'
    if re.fullmatch(r'[а-яё]+',t): return 'R'
    if re.fullmatch(r'[a-z]+',t): return 'L'
    if re.fullmatch(r'[0-9]+',t): return 'N'
    if t in '.!?': return 'T'
    if t in ',;:': return 'P'
    return 'O'

def template(tokens, max_len=32):
    return ' '.join(tok_type(t) for t in tokens[:max_len])

templates=Counter(); lens=Counter(); para_lens=Counter(); samples_by_template=defaultdict(list)
for s in sentences:
    toks=[t for t in tok_re.findall(s) if t.strip()]
    if not toks: continue
    tp=template(toks)
    templates[tp]+=1
    lens[min(len(toks),80)]+=1
    if len(samples_by_template[tp])<8:
        samples_by_template[tp].append(s[:240])
for p in paragraphs:
    ss=[x for x in re.split(r'(?<=[.!?…])\s+', p) if x.strip()]
    if ss: para_lens[min(len(ss),30)]+=1

# Keep compact top templates.
top_templates=[]
for tp,c in templates.most_common(1200):
    top_templates.append({'template':tp,'count':c,'samples':samples_by_template[tp][:3]})
model={
 'version':'sentence_student_v1',
 'summary':{k:stats[k] for k in ['chars_total','words_total','sentences','paragraphs']},
 'sentence_lengths':dict(lens),
 'paragraph_sentence_lengths':dict(para_lens),
 'templates':top_templates,
 'word_student':word,
}
(OUT/'sentence_student_v1.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
print('templates',len(top_templates),'unique_templates',len(templates),'sentences',len(sentences),'paragraphs',len(paragraphs))
print('top templates')
for x in top_templates[:20]: print(x['count'], x['template'], '::', x['samples'][0][:120])
