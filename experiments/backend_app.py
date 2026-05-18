#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, random, math, unicodedata
from flask import Flask, request, jsonify, send_from_directory
import regex as re
ROOT=Path('/home/roomhacker/babel-experiments')
SITE=ROOT/'site'
MODEL=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))
ALPHA=MODEL['alphabet']; ASET=set(ALPHA); IDX={c:i for i,c in enumerate(ALPHA)}
emoji_re=re.compile(r'\p{Emoji}')
app=Flask(__name__, static_folder=str(SITE), static_url_path='')

def norm_char(ch):
    if ch in {'\ufeff','\u200b','\u200c','\u200d','\ufe0f','\ufe0e'}: return ''
    if unicodedata.category(ch).startswith('M'): return ''
    if ch in '\t\r\u00a0\u2800': return ' '
    if ch in {'“','”','„','‟'}: return '"'
    if ch in {'’','‘','‚','`','´'}: return "'"
    if ch in {'–','—','−'}: return '-'
    return ch.lower()

def cls(ch): return MODEL['symbol_class'].get(ch,'OTHER')
def normalize_text(s):
    out=[]; unknown=0
    for raw in s:
        ch=norm_char(raw)
        if not ch: continue
        if ch not in ASET:
            ch=' '; unknown+=1
        out.append(ch)
    return ''.join(out), unknown

def score_text(s):
    text,unk=normalize_text(s)
    energy=0; prev='START'; reps=0; last=''
    for ch in text:
        c=cls(ch)
        energy += MODEL['transition_costs'].get(prev,{}).get(c,1500)
        energy += MODEL['emission_costs'].get(c,{}).get(ch,1500)
        if ch==last: reps += 1
        else: reps=0
        if reps>4: energy += 200*(reps-3)
        prev=c; last=ch
    return {'normalized':text,'length':len(text),'unknown':unk,'energy':energy,'energy_per_symbol':energy/max(1,len(text))}

def rank_text(s):
    # MVP rank: fixed base-256 value of normalized alphabet indices. This is a real bijection for fixed-length pages after padding/truncation.
    text,_=normalize_text(s)
    page=(text + ' ' * 4096)[:4096]
    n=0
    for ch in page:
        n=(n<<8)|IDX.get(ch,0)
    return n, page

def unrank_int(n):
    xs=[]
    for _ in range(4096):
        xs.append(ALPHA[n & 255]); n >>= 8
    return ''.join(reversed(xs))

def gen(seed='42', length=512):
    rng=random.Random(int(hashlib.sha256(str(seed).encode()).hexdigest()[:16],16))
    out=[]; prev='START'; last=''; rep=0
    for _ in range(min(4096,max(1,int(length)))):
        trans=MODEL['transitions'].get(prev) or MODEL['transitions'].get('START') or {}
        items=list(trans.items())
        # anti-collapse: remove SPACE after SPACE and long same chars/classes
        if prev=='SPACE': items=[x for x in items if x[0]!='SPACE'] or items
        total=sum(v**0.62 for _,v in items); x=rng.random()*total; c=items[-1][0]
        for k,v in items:
            x-=v**0.62
            if x<=0: c=k; break
        em=MODEL['emissions'].get(c) or {' ':1}; eitems=list(em.items())
        if rep>3: eitems=[x for x in eitems if x[0]!=last] or eitems
        et=sum(v**0.72 for _,v in eitems); y=rng.random()*et; ch=eitems[-1][0]
        for k,v in eitems:
            y-=v**0.72
            if y<=0: ch=k; break
        out.append(ch); rep=rep+1 if ch==last else 0; last=ch; prev=c
    return ''.join(out)

@app.get('/')
def index(): return send_from_directory(SITE,'index.html')
@app.get('/<path:path>')
def static_proxy(path): return send_from_directory(SITE,path)
@app.post('/api/score')
def api_score(): return jsonify(score_text((request.json or {}).get('text','')))
@app.post('/api/rank')
def api_rank():
    n,page=rank_text((request.json or {}).get('text',''))
    return jsonify({'rank_hex':hex(n),'rank_dec':str(n),'page_preview':page[:512]})
@app.post('/api/unrank')
def api_unrank():
    body=request.json or {}; val=str(body.get('rank','0'))
    n=int(val,16) if val.startswith('0x') else int(val)
    page=unrank_int(n)
    return jsonify({'text':page,'preview':page[:512]})
@app.post('/api/search')
def api_search():
    body=request.json or {}; q=body.get('q',''); length=int(body.get('length',512))
    n,page=rank_text(q)
    return jsonify({'query_score':score_text(q),'rank_hex':hex(n),'exact_page_preview':page[:length]})
@app.post('/api/generate')
def api_generate():
    body=request.json or {}; text=gen(body.get('seed','42'), int(body.get('length',512)))
    return jsonify({'text':text,'score':score_text(text)})

if __name__=='__main__': app.run(host='0.0.0.0',port=8090)
