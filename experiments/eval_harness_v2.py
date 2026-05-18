#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
from collections import Counter
import json, math, random, regex as re, statistics, time

ROOT=Path('/home/roomhacker/babel-experiments')
CACHE=ROOT/'datasets/cache_v1'
OUT=ROOT/'models/eval_harness_v2'
OUT.mkdir(parents=True, exist_ok=True)

WORD=json.loads((ROOT/'models/word_student_v1/word_student_v1.json').read_text(encoding='utf-8'))
SENT=json.loads((ROOT/'models/sentence_student_v1/sentence_student_v1.json').read_text(encoding='utf-8'))
PARA=json.loads((ROOT/'models/paragraph_student_v1/paragraph_student_v1.json').read_text(encoding='utf-8'))
FSM=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))

TOK_RE=re.compile(r"[\p{L}\p{N}]+(?:['-][\p{L}\p{N}]+)*|\p{Emoji}+|[^\s]", re.U)
SENT_RE=re.compile(r'(?<=[.!?…])\s+')

# Held-out stats for comparison.
held=[]
for fp in sorted(CACHE.glob('*.txt'))[-8:]:
    txt=fp.read_text(encoding='utf-8',errors='ignore')[:700000]
    held.extend([x.strip() for x in SENT_RE.split(txt) if x.strip()])
held=held[:10000]

def toks(s): return TOK_RE.findall(str(s).lower())
def safe_mean(xs, default=0.0): return statistics.mean(xs) if xs else default

def corpus_profile(sentences):
    token_lens=[]; sent_lens=[]; emoji_rates=[]; punct_rates=[]
    for s in sentences:
        ts=toks(s)
        if not ts: continue
        sent_lens.append(len(ts))
        token_lens.extend([len(t) for t in ts])
        emoji_rates.append(sum(1 for t in ts if re.search(r'\p{Emoji}',t))/len(ts))
        punct_rates.append(sum(1 for t in ts if re.fullmatch(r'[^\w\s]+',t))/len(ts))
    return {
        'sentence_len_mean':safe_mean(sent_lens),
        'token_len_mean':safe_mean(token_lens),
        'emoji_rate':safe_mean(emoji_rates),
        'punct_rate':safe_mean(punct_rates),
    }
HELD_PROFILE=corpus_profile(held)

# Shared generation helpers.
def weighted(counter,rng,temp=0.75, filt=None):
    items=list((counter or {}).items())
    if filt:
        items=[x for x in items if filt(x[0])]
    if not items:
        return None
    weights=[max(1,int(v))**temp for _,v in items]
    return rng.choices([k for k,_ in items], weights=weights, k=1)[0]

def weighted_rows(rows,rng,temp=0.75):
    if not rows: return None
    weights=[max(1,int(r.get('count',1)))**temp for r in rows]
    return rng.choices(rows,weights=weights,k=1)[0]

def realize(tok,rng):
    arr=WORD.get('abstract_emissions',{}).get(tok)
    if arr: return rng.choice(arr)
    return tok.replace('<','').replace('>','')

def detok(tokens):
    out=''
    for t in tokens:
        if not t or t=='</s>': continue
        if not out: out=t
        elif re.fullmatch(r'[.,!?;:)]',t): out+=t
        else: out+=' '+t
    return out

def type_ok(typ,k):
    if k is None: return False
    if typ=='R': return k=='<ru>' or bool(re.fullmatch(r'[а-яё]+',k))
    if typ=='L': return k=='<en>' or bool(re.fullmatch(r'[a-z]+',k))
    if typ=='N': return k=='<num>' or bool(re.fullmatch(r'[0-9]+',k))
    if typ=='E': return k=='<emoji>' or bool(re.search(r'\p{Emoji}',k))
    if typ=='T': return k in ['.','!','?','</s>']
    if typ=='P': return k in [',',';',':']
    return True

def gen_sentence_from_template(tpl,rng,branch=32,temp=0.62):
    prev='<s>'; out=[]
    for typ in tpl.split():
        trans=WORD.get('transitions',{}).get(prev) or WORD.get('transitions',{}).get('<s>') or {}
        cand={k:v for k,v in trans.items() if type_ok(typ,k)}
        if cand:
            # keep top branch
            top=dict(sorted(cand.items(), key=lambda x:-x[1])[:branch])
            tok=weighted(top,rng,temp)
        else:
            tok='.' if typ=='T' else '<ru>'
        if tok=='</s>': tok='.'
        tok=realize(tok,rng)
        out.append(tok)
        prev=tok
    s=detok(out)
    if not re.search(r'[.!?…]$',s): s+='.'
    return s

def gen_word(seed,length,temp=0.68):
    rng=random.Random(seed); prev='<s>'; out=[]
    while len(' '.join(out))<length and len(out)<1000:
        trans=WORD.get('transitions',{}).get(prev) or WORD.get('transitions',{}).get('<s>') or {}
        tok=weighted(trans,rng,temp,lambda k:k!='</s>') or '<ru>'
        tok=realize(tok,rng)
        out.append(tok)
        prev=tok
        if len(out)%18==0:
            out.append(rng.choice(['.','!','?'])); prev='<s>'
    return detok(out)[:length]

def gen_sentence(seed,length,temp=0.72,branch=32):
    rng=random.Random(seed); rows=SENT.get('templates',[])[:1200]; out=[]
    while len('\n'.join(out))<length and len(out)<200:
        row=weighted_rows(rows,rng,temp) or {'template':'R R R T'}
        out.append(gen_sentence_from_template(row['template'],rng,branch=branch))
        if len(out)%rng.randint(2,5)==0: out.append('\n')
    return ' '.join(out).replace('\n ','\n')[:length]

def gen_paragraph(seed,length,temp=0.70,branch=32):
    rng=random.Random(seed); rows=PARA.get('top_paragraph_shapes',[])[:1000]; paras=[]
    while len('\n\n'.join(paras))<length and len(paras)<80:
        row=weighted_rows(rows,rng,temp) or {'shape':'R R R T'}
        sents=[]
        for tpl in row['shape'].split(' | ')[:8]:
            sents.append(gen_sentence_from_template(tpl,rng,branch=branch))
        paras.append(' '.join(sents))
    return '\n\n'.join(paras)[:length]

def gen_fsm(seed,length,temp=0.70):
    rng=random.Random(seed); out=''; prev='START'; last=''; rep=0
    for _ in range(length):
        trans=FSM.get('transitions',{}).get(prev) or FSM.get('transitions',{}).get('START') or {}
        cls=weighted(trans,rng,0.58) or 'SPACE'
        em=FSM.get('emissions',{}).get(cls) or {' ':1}
        ch=weighted(em,rng,temp,lambda k:not(rep>3 and k==last)) or ' '
        out+=ch; rep=rep+1 if ch==last else 0; last=ch; prev=cls
    return out

def metrics(samples):
    sent_lens=[]; uniq_ratios=[]; max_runs=[]; emoji=[]; punct=[]; alpha=[]
    all_text='\n'.join(samples)
    for s in samples:
        ts=toks(s)
        if not ts: continue
        sent_lens.append(len(ts))
        uniq_ratios.append(len(set(ts))/len(ts))
        max_runs.append(max((len(list(g)) for _,g in __import__('itertools').groupby(ts)), default=1))
        emoji.append(sum(1 for t in ts if re.search(r'\p{Emoji}',t))/len(ts))
        punct.append(sum(1 for t in ts if re.fullmatch(r'[^\w\s]+',t))/len(ts))
        alpha.append(sum(1 for t in ts if re.search(r'[\p{L}\p{N}]',t))/len(ts))
    profile=corpus_profile(samples)
    dist_penalty=sum(abs(profile[k]-HELD_PROFILE[k]) for k in profile)
    repetition=safe_mean(max_runs)
    diversity=safe_mean(uniq_ratios)
    length_ok=abs(safe_mean(sent_lens)-HELD_PROFILE['sentence_len_mean'])/max(1,HELD_PROFILE['sentence_len_mean'])
    collapse_penalty=max(0,repetition-3)*2 + max(0,0.35-diversity)*5
    final=dist_penalty + collapse_penalty + length_ok
    return {
        'final_score':round(final,4),
        'distribution_penalty':round(dist_penalty,4),
        'collapse_penalty':round(collapse_penalty,4),
        'sentence_len_mean':round(safe_mean(sent_lens),3),
        'unique_token_ratio':round(diversity,3),
        'max_run_mean':round(repetition,3),
        'emoji_rate':round(safe_mean(emoji),4),
        'punct_rate':round(safe_mean(punct),4),
        'alpha_rate':round(safe_mean(alpha),4),
        'chars':len(all_text),
    }

configs=[]
for model in ['word','sentence','paragraph','fsm']:
    if model=='fsm':
        for temp in [0.62,0.72,0.86]: configs.append({'model':model,'temp':temp})
    elif model=='word':
        for temp in [0.55,0.68,0.85]: configs.append({'model':model,'temp':temp})
    else:
        for temp in [0.62,0.72,0.85]:
            for branch in [16,32,64]: configs.append({'model':model,'temp':temp,'branch':branch})

def generate(cfg,seed,length):
    m=cfg['model']
    if m=='word': return gen_word(seed,length,cfg['temp'])
    if m=='sentence': return gen_sentence(seed,length,cfg['temp'],cfg.get('branch',32))
    if m=='paragraph': return gen_paragraph(seed,length,cfg['temp'],cfg.get('branch',32))
    return gen_fsm(seed,length,cfg['temp'])

def main():
    started=time.time(); leaderboard=[]
    for i,cfg in enumerate(configs,1):
        print(f'[{i}/{len(configs)}] {cfg}',flush=True)
        samples=[generate(cfg,1000+i*100+s,512) for s in range(40)]
        m=metrics(samples)
        row={'cfg':cfg,'metrics':m,'samples':samples[:8]}
        leaderboard.append(row)
        leaderboard.sort(key=lambda x:x['metrics']['final_score'])
        (OUT/'leaderboard.json').write_text(json.dumps({'updated_at':time.time(),'heldout_profile':HELD_PROFILE,'leaderboard':leaderboard},ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'version':'eval_harness_v2','configs_tested':len(configs),'best':leaderboard[0],'elapsed_seconds':round(time.time()-started,3)}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'configs_tested':len(configs),'best_cfg':leaderboard[0]['cfg'],'best_metrics':leaderboard[0]['metrics'],'elapsed_seconds':summary['elapsed_seconds']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()
