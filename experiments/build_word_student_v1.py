#!/usr/bin/env python3
from pathlib import Path
from collections import Counter,defaultdict
import json, math, regex as re, random
ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
STATS=ROOT/'models/text_stats_v1/stats.json'
OUT=ROOT/'models/word_student_v1'
OUT.mkdir(parents=True, exist_ok=True)
stats=json.loads(STATS.read_text(encoding='utf-8'))
# token vocabulary: top words/punct/emoji, but keep compact for browser
vocab=[w for w,c in stats['top_words'][:2500] if len(w)<=32]
# ensure common punctuation
for t in list('.,!?;:')+['😂','❤️','👍','🙏','🔥','🤣','😭']:
    if t not in vocab: vocab.append(t)
vset=set(vocab)
# build transitions using cached sentences but only vocab tokens, unknown class collapsed by first char groups
sentences=(CACHE/'sentences.txt').read_text(encoding='utf-8').splitlines()
tok_re=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", re.U)
trans=defaultdict(Counter); start=Counter(); end=Counter(); emit=Counter()
def map_tok(t):
    if t in vset: return t
    if re.fullmatch(r'\p{Emoji}+',t): return '<emoji>'
    if re.fullmatch(r'[а-яё]+',t): return '<ru>'
    if re.fullmatch(r'[a-z]+',t): return '<en>'
    if re.fullmatch(r'[0-9]+',t): return '<num>'
    return '<other>'
for s in sentences:
    toks=[map_tok(t) for t in tok_re.findall(s) if t.strip()]
    if not toks: continue
    start[toks[0]]+=1; end[toks[-1]]+=1
    prev='<s>'
    for t in toks:
        trans[prev][t]+=1; emit[t]+=1; prev=t
    trans[prev]['</s>']+=1
# candidate emissions for abstract tokens from real frequent words
classes={
 '<ru>':[w for w,c in stats['top_words'] if re.fullmatch(r'[а-яё]+',w)][:500],
 '<en>':[w for w,c in stats['top_words'] if re.fullmatch(r'[a-z]+',w)][:300],
 '<num>':[w for w,c in stats['top_words'] if re.fullmatch(r'[0-9]+',w)][:100] or ['1','2','2024'],
 '<emoji>':[x[0] for x in stats.get('top_chars',[]) if len(x[0])==1 and re.fullmatch(r'\p{Emoji}',x[0])][:80],
 '<other>':['-','/','@','#']
}
model={'version':'word_student_v1','vocab':vocab,'transitions':{k:dict(v) for k,v in trans.items()},'emissions':dict(emit),'abstract_emissions':classes,'stats_summary':{k:stats[k] for k in ['chars_total','chars_unique','words_total','words_unique','sentences','paragraphs']}}
(OUT/'word_student_v1.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
print('vocab',len(vocab),'states',len(trans),'sentences',len(sentences))
for k in ['<s>','привет','я','и','😂','<ru>','<emoji>']:
    if k in trans: print(k, trans[k].most_common(15))
