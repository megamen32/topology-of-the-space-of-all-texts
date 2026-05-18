#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, random, time, urllib.request, regex as re

ROOT=Path('/home/roomhacker/babel-experiments')
DATA=json.loads((ROOT/'site/data/eval_leaderboard_v2.json').read_text(encoding='utf-8'))
OUT=ROOT/'models/eval_harness_v2/llm_judge_qwen3_4b_v3.json'
API='https://llm.bezrabotnyi.com/v1/chat/completions'
MODEL='qwen3:4b-instruct'
rows=DATA.get('leaderboard',[])
random.seed(20260519)

bad_re=re.compile(r'[{}\[\]^_=|~<>]|[\p{Latin}\p{Cyrillic}]{1}\s+[\p{Latin}\p{Cyrillic}]{1}\s+[\p{Latin}\p{Cyrillic}]{1}|[0-9][a-zа-яё]|[a-zа-яё][0-9]', re.I)
tok_re=re.compile(r"[\p{L}\p{N}]+|\p{Emoji}+|[^\s]", re.U)

def cfg_name(r):
    c=r.get('cfg',{})
    return ' '.join(str(x) for x in [c.get('model'), 't='+str(c.get('temp')) if c.get('temp') is not None else '', 'b='+str(c.get('branch')) if c.get('branch') else ''] if x)

def gibberish_score(text:str)->float:
    ts=tok_re.findall(text or '')
    if not ts: return 999.0
    punct=sum(1 for t in ts if re.fullmatch(r'[^\p{L}\p{N}\s]+',t))/len(ts)
    short=sum(1 for t in ts if re.fullmatch(r'[\p{L}]',t))/len(ts)
    bad=len(bad_re.findall(text))/max(1,len(ts))
    uniq=len(set(ts))/len(ts)
    return punct*3 + short*4 + bad*8 + max(0,0.35-uniq)*4

def chat(prompt:str, timeout=45)->str:
    payload={
        'model':MODEL,
        'messages':[
            {'role':'system','content':'You are a strict evaluator. Reply with exactly one token: A, B, or TIE.'},
            {'role':'user','content':prompt},
        ],
        'stream':False,
        'temperature':0,
        'max_tokens':8,
    }
    req=urllib.request.Request(API,data=json.dumps(payload).encode('utf-8'),headers={'Content-Type':'application/json'})
    last=None
    for _ in range(3):
        try:
            with urllib.request.urlopen(req,timeout=timeout) as r:
                j=json.loads(r.read().decode('utf-8'))
                return j['choices'][0]['message']['content'].strip()
        except Exception as e:
            last=e; time.sleep(0.7)
    raise last

def judge_pair(sa,sb):
    ga,gb=gibberish_score(sa),gibberish_score(sb)
    if ga > gb + 1.2: return 'B', f'heuristic_gibberish A={ga:.2f} B={gb:.2f}'
    if gb > ga + 1.2: return 'A', f'heuristic_gibberish A={ga:.2f} B={gb:.2f}'
    prompt=f'''Which text is more likely written by a real human internet user?
Strongly penalize random character soup, broken mixed alphabets, isolated letters, weird symbols, and unreadable noise.
Reply exactly: A, B, or TIE.

A:
{sa}

B:
{sb}

Answer:'''
    ans=chat(prompt)
    up=ans.upper().strip()
    if up.startswith('A'): return 'A',ans
    if up.startswith('B'): return 'B',ans
    if up.startswith('TIE'): return 'TIE',ans
    return 'TIE',ans

idxs=list(range(len(rows)))
fsm_idxs=[i for i,r in enumerate(rows) if r.get('cfg',{}).get('model')=='fsm']
non_idxs=[i for i,r in enumerate(rows) if r.get('cfg',{}).get('model')!='fsm']
pairs=[]
for _ in range(40):
    if fsm_idxs and non_idxs:
        i=random.choice(fsm_idxs); j=random.choice(non_idxs)
        if random.random()<0.5: i,j=j,i
        pairs.append((i,j))
for _ in range(80):
    pairs.append(tuple(random.sample(idxs,2)))

votes=[]; scores={cfg_name(r):0 for r in rows}; wins={cfg_name(r):0 for r in rows}; losses={cfg_name(r):0 for r in rows}
start=time.time()
for n,(i,j) in enumerate(pairs,1):
    a,b=rows[i],rows[j]
    sa=random.choice(a.get('samples') or [''])[:360]
    sb=random.choice(b.get('samples') or [''])[:360]
    try: verdict,raw=judge_pair(sa,sb)
    except Exception as e: verdict,raw='ERROR',str(e)
    name_a,name_b=cfg_name(a),cfg_name(b)
    if verdict=='A': scores[name_a]+=1; scores[name_b]-=1; wins[name_a]+=1; losses[name_b]+=1
    elif verdict=='B': scores[name_b]+=1; scores[name_a]-=1; wins[name_b]+=1; losses[name_a]+=1
    votes.append({'pair':n,'a':name_a,'b':name_b,'auto_score_a':a['metrics']['final_score'],'auto_score_b':b['metrics']['final_score'],'gibberish_a':round(gibberish_score(sa),3),'gibberish_b':round(gibberish_score(sb),3),'verdict':verdict,'raw':raw,'sample_a':sa,'sample_b':sb})
    if n%10==0:
        print(f'judged {n}/{len(pairs)} verdict={verdict} raw={raw[:80]}',flush=True)
        OUT.write_text(json.dumps({'model':MODEL,'api':API,'version':'v3_chat_completions_gibberish_guard','updated_at':time.time(),'votes':votes,'scores':scores,'wins':wins,'losses':losses},ensure_ascii=False,indent=2),encoding='utf-8')
ranking=sorted(scores.items(), key=lambda x:-x[1])
result={'model':MODEL,'api':API,'version':'v3_chat_completions_gibberish_guard','elapsed_seconds':round(time.time()-start,2),'votes':votes,'scores':scores,'wins':wins,'losses':losses,'ranking':ranking}
OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'done':len(votes),'top':ranking[:10],'bottom':ranking[-5:],'elapsed_seconds':result['elapsed_seconds']},ensure_ascii=False,indent=2))
