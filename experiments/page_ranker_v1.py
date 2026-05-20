#!/usr/bin/env python3
from pathlib import Path
import json, math, regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
M=json.loads((ROOT/'models/cluster_student_v2/model.json').read_text())
maptok=M['mapping']; trans=M['cluster_transitions']; K=M['clusters']
TOK=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]",re.U)
rows={k:sum(v.values()) for k,v in trans.items()}
def score(text):
 t=TOK.findall(text.lower()); cls=[maptok.get(x,0) for x in t]
 bits=0
 for a,b in zip(cls,cls[1:]):
   row=trans.get(str(a),{})
   p=(row.get(str(b),0)+1)/(rows.get(str(a),0)+K)
   bits += -math.log2(p)
 return {'tokens':len(t),'cost_bits':round(bits,2),'cost_per_token':round(bits/max(1,len(t)),3)}
examples=['я думаю что завтра будет дождь.','etsa? рин ?. í… 11 uoow #itliodp','привет как дела сегодня','я тебя люблю']
out={x:score(x) for x in examples}
(ROOT/'models/page_ranker_v1/examples.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(json.dumps(out,ensure_ascii=False,indent=2))
