#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, os, random, math, unicodedata, sys
from flask import Flask, request, jsonify, send_from_directory
import regex as re
from functools import lru_cache
from cluster_counting_mvp import RawClusterRanker
ROOT=Path(os.environ.get('BABEL_ROOT', Path(__file__).resolve().parents[1]))
# A 4096-byte page has ~9,865 decimal digits. The API historically exposed
# rank_dec, so allow that intentional conversion instead of failing at Python's
# defensive 4,300-digit default.
if hasattr(sys, 'set_int_max_str_digits'):
    sys.set_int_max_str_digits(0)
SITE=ROOT/'site'
MODEL=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))
ALPHA=MODEL['alphabet']; ASET=set(ALPHA); IDX={c:i for i,c in enumerate(ALPHA)}
emoji_re=re.compile(r'\p{Emoji}')
app=Flask(__name__, static_folder=str(SITE), static_url_path='')
EXACT_CLUSTER_MAX_LENGTH = 64
RUSSIAN_WALK_TEXTS = (
    ('Тихое утро', 'утром над городом пошёл тёплый дождь, и улицы стали тихими.'),
    ('Карта', 'на полке нашлась старая карта с пометкой карандашом на полях.'),
    ('Прогулка', 'сегодня мы закончили работу раньше и долго гуляли у реки.'),
    ('Кухня', 'на кухне пахло яблоками, чаем и свежим хлебом из духовки.'),
    ('Поезд', 'маленький поезд ушёл за лес, оставив в окне полоску света.'),
    ('Мысль', 'я записал новую мысль, чтобы вернуться к ней завтра утром.'),
    ('Площадь', 'на площади играла музыка, дети смеялись и кормили голубей.'),
    ('Вечер', 'вечером ветер стих, а в окнах домов зажглись жёлтые огни.'),
    ('Мастерская', 'после обеда в мастерской зазвенел старый телефон.'),
    ('Снег', 'снег медленно ложился на крыши и пустые скамейки.'),
    ('Корабль', 'в тетради остался рисунок синего корабля у берега.'),
    ('Письмо', 'письмо пришло без подписи, но почерк был знакомым.'),
    ('Станция', 'на станции продавали кофе, газеты и горячие пироги.'),
    ('Сад', 'старый сад пах землёй, мятой и мокрыми листьями.'),
    ('Гроза', 'ночью за окном прошла гроза, потом стало совсем тихо.'),
    ('Проект', 'в понедельник команда начала новый проект без спешки.'),
)
RUSSIAN_WALK_MODEL = ROOT / 'models/russian_walk_v1.json'
COUNTING_PROOF_MODEL = ROOT / 'models/cluster_chunk_counts_v1/len256_block16.json'

@lru_cache(maxsize=8)
def exact_cluster_ranker(length):
    length = int(length)
    if length < 1 or length > EXACT_CLUSTER_MAX_LENGTH:
        raise ValueError(f'exact_cluster_mvp supports length 1..{EXACT_CLUSTER_MAX_LENGTH} for now')
    return RawClusterRanker(length=length)

def exact_cluster_rank(text, length):
    return exact_cluster_ranker(int(length)).rank_text(text)

def exact_cluster_unrank(value, length):
    return exact_cluster_ranker(int(length)).unrank_page(int(value, 16) if str(value).lower().startswith('0x') else int(value))

@lru_cache(maxsize=1)
def russian_walk_pages():
    """Curated human-shaped checkpoints in the exact 64-symbol space.

    These are semantic waypoints, not consecutive integer ranks. The API also
    exposes literal +/-1 neighbours so the UI can distinguish the two notions.
    """
    if not RUSSIAN_WALK_MODEL.exists():
        raise RuntimeError(f'missing cached walk model: {RUSSIAN_WALK_MODEL}')
    cached = json.loads(RUSSIAN_WALK_MODEL.read_text(encoding='utf-8'))
    if cached.get('version') != 'russian_walk_v1' or cached.get('length') != 64:
        raise RuntimeError('russian walk model has an unsupported version')
    return tuple(cached['pages'])

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
    body=request.json or {}
    if body.get('mode') == 'exact_cluster_mvp':
        try:
            length=int(body.get('length', 8))
            result=exact_cluster_rank(body.get('text',''), length)
            # JSON numbers lose precision in JavaScript for realistic page
            # addresses. Exact ranks are transport values, so expose decimal
            # and hex as strings while keeping the internal integer exact.
            return jsonify({
                'mode':'exact_cluster_mvp',
                'length':length,
                'rank':str(result['rank']),
                'rank_hex':hex(result['rank']),
                'energy':result['energy'],
                'page':result['page'],
            })
        except (ValueError, TypeError) as exc:
            return jsonify({'error':str(exc),'mode':'exact_cluster_mvp'}),400
    n,page=rank_text(body.get('text',''))
    return jsonify({'rank_hex':hex(n),'rank_dec':str(n),'page_preview':page[:512]})
@app.post('/api/unrank')
def api_unrank():
    body=request.json or {}; val=str(body.get('rank','0'))
    if body.get('mode') == 'exact_cluster_mvp':
        try:
            length=int(body.get('length', 8))
            result=exact_cluster_unrank(val, length)
            return jsonify({
                'mode':'exact_cluster_mvp',
                'length':length,
                'rank':str(result['rank']),
                'rank_hex':hex(result['rank']),
                'energy':result['energy'],
                'page':result['page'],
            })
        except (ValueError, TypeError) as exc:
            return jsonify({'error':str(exc),'mode':'exact_cluster_mvp'}),400
    n=int(val,16) if val.startswith('0x') else int(val)
    page=unrank_int(n)
    return jsonify({'text':page,'preview':page[:512]})
@app.get('/api/russian-walk')
def api_russian_walk():
    return jsonify({'mode':'semantic_waypoints','length':64,'pages':russian_walk_pages()})
@app.get('/api/counting-proof')
def api_counting_proof():
    if not COUNTING_PROOF_MODEL.exists():
        return jsonify({'error':'counting proof artifact is unavailable'}), 503
    return jsonify(json.loads(COUNTING_PROOF_MODEL.read_text(encoding='utf-8')))
@app.post('/api/exact-neighbor')
def api_exact_neighbor():
    body = request.json or {}
    try:
        length = int(body.get('length', 64))
        delta = int(body.get('delta', 1))
        if delta not in (-1, 1):
            raise ValueError('delta must be -1 or 1')
        ranker = exact_cluster_ranker(length)
        rank = int(str(body.get('rank', '0')), 16) if str(body.get('rank', '')).lower().startswith('0x') else int(body.get('rank', 0))
        result = ranker.unrank_page((rank + delta) % ranker.space_size)
        return jsonify({
            'mode':'exact_integer_neighbor',
            'length':length,
            'rank':str(result['rank']),
            'rank_hex':hex(result['rank']),
            'energy':result['energy'],
            'page':result['page'],
        })
    except (ValueError, TypeError) as exc:
        return jsonify({'error':str(exc),'mode':'exact_integer_neighbor'}),400
@app.post('/api/search')
def api_search():
    body=request.json or {}; q=body.get('q',''); length=int(body.get('length',512))
    n,page=rank_text(q)
    return jsonify({'query_score':score_text(q),'rank_hex':hex(n),'exact_page_preview':page[:length]})
@app.post('/api/generate')
def api_generate():
    body=request.json or {}; text=gen(body.get('seed','42'), int(body.get('length',512)))
    return jsonify({'text':text,'score':score_text(text)})

if __name__=='__main__':
    app.run(
        host=os.environ.get('BABEL_HOST', '127.0.0.1'),
        port=int(os.environ.get('BABEL_PORT', '8090')),
    )
