#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, random, time, urllib.request, urllib.error

ROOT=Path('/home/roomhacker/babel-experiments')
DATA=json.loads((ROOT/'site/data/eval_leaderboard_v2.json').read_text(encoding='utf-8'))
OUT=ROOT/'models/eval_harness_v2/llm_judge_qwen35.json'
API='https://llm.bezrabotnyi.com/v1/chat/completions'
MODEL='qwen3.5'

rows=DATA.get('leaderboard',[])
random.seed(20260519)

def cfg_name(r):
    c=r.get('cfg',{})
    return ' '.join(str(x) for x in [c.get('model'), 't='+str(c.get('temp')) if c.get('temp') is not None else '', 'b='+str(c.get('branch')) if c.get('branch') else ''] if x)

def call_ollama(prompt:str, timeout=120):
    payload=json.dumps({'model': MODEL, 'messages': [{'role': 'user', 'content': prompt}], 'stream': False, 'temperature': 0.0, 'max_tokens': 64}).encode('utf-8')
    req=urllib.request.Request(API, data=payload, headers={'Content-Type':'application/json', 'Authorization':'Bearer sk-305630'})
    last=None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                data=json.loads(r.read().decode('utf-8')); return data.get('choices',[{}])[0].get('message',{}).get('content','').strip()
        except Exception as e:
            last=e
            timeout=max(20, timeout//2)
    raise last

def judge_pair(a,b,sa,sb):
    prompt=f'''You are judging which text looks more like a real human-written internet post/comment.
Which text feels more human-written? Reply only: A, B or TIE.

Text A:
{sa}

Text B:
{sb}

Answer:'''
    ans=call_ollama(prompt)
    up=ans.upper()
    if 'A' in up[:20] and 'B' not in up[:20]: return 'A',ans
    if 'B' in up[:20] and 'A' not in up[:20]: return 'B',ans
    if 'TIE' in up[:50]: return 'TIE',ans
    # fallback first char
    if up.startswith('A'): return 'A',ans
    if up.startswith('B'): return 'B',ans
    return 'TIE',ans

pairs=[]
# Bias toward comparing top/mid/bottom configs.
idxs=list(range(len(rows)))
for _ in range(80):
    i,j=random.sample(idxs,2)
    a,b=rows[i],rows[j]
    sa=random.choice(a.get('samples') or [''])[:320]
    sb=random.choice(b.get('samples') or [''])[:320]
    pairs.append((i,j,a,b,sa,sb))

votes=[]; scores={cfg_name(r):0 for r in rows}; wins={cfg_name(r):0 for r in rows}; losses={cfg_name(r):0 for r in rows}
start=time.time()
for n,(i,j,a,b,sa,sb) in enumerate(pairs,1):
    try:
        verdict,raw=judge_pair(a,b,sa,sb)
    except Exception as e:
        verdict,raw='ERROR',str(e)
    name_a,name_b=cfg_name(a),cfg_name(b)
    if verdict=='A': scores[name_a]+=1; scores[name_b]-=1; wins[name_a]+=1; losses[name_b]+=1
    elif verdict=='B': scores[name_b]+=1; scores[name_a]-=1; wins[name_b]+=1; losses[name_a]+=1
    votes.append({'pair':n,'a':name_a,'b':name_b,'auto_score_a':a['metrics']['final_score'],'auto_score_b':b['metrics']['final_score'],'verdict':verdict,'raw':raw,'sample_a':sa,'sample_b':sb})
    if n%5==0:
        print(f'judged {n}/{len(pairs)} verdict={verdict}',flush=True)
        OUT.write_text(json.dumps({'model':MODEL,'api':API,'updated_at':time.time(),'votes':votes,'scores':scores,'wins':wins,'losses':losses},ensure_ascii=False,indent=2),encoding='utf-8')

ranking=sorted(scores.items(), key=lambda x:-x[1])
result={'model':MODEL,'api':API,'elapsed_seconds':round(time.time()-start,2),'votes':votes,'scores':scores,'wins':wins,'losses':losses,'ranking':ranking}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'done':len(votes),'top':ranking[:5],'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False,indent=2))
