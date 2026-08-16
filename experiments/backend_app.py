#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, os, random, math, unicodedata, sys
from flask import Flask, request, jsonify, send_from_directory
import regex as re
from functools import lru_cache
from cluster_counting_mvp import HierarchicalRawRanker, RawClusterRanker
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
EXACT_CLUSTER_MAX_LENGTH = 256
HIERARCHICAL_BLOCK_LENGTH = 256
HIERARCHICAL_MAX_LENGTH = 4096
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
ATLAS_RU_TITLES = (
    'Сад после дождя', 'Тихая станция', 'Архив ветра', 'Ночная мастерская',
    'Карта тёплого света', 'Письма издалека', 'Город у реки', 'Последний поезд',
)
ATLAS_EN_TITLES = (
    'The Garden After Rain', 'The Quiet Station', 'Archive of Wind', 'Night Workshop',
    'A Map of Warm Light', 'Letters from Afar', 'The City by the River', 'The Last Train',
)
ATLAS_RU_SENTENCES = (
    'Утром над городом прошёл тёплый дождь, и камни на площади стали темнее.',
    'В старой мастерской тихо работали часы, оставленные неизвестным мастером.',
    'За рекой медленно зажигались окна, а поезд уходил в сторону леса.',
    'На полке лежала карта с карандашной отметкой у самого края бумаги.',
    'Сад пах мятой, мокрой землёй и яблоками, спрятанными в высокой траве.',
    'Она записала эту мысль на полях, чтобы вернуться к ней следующим утром.',
    'Ветер перелистывал книгу, пока комната наполнялась мягким вечерним светом.',
    'Никто не знал автора письма, но каждое слово казалось удивительно знакомым.',
    'На пустой станции продавали кофе, газеты и горячий хлеб из маленькой печи.',
    'Когда гроза ушла за горизонт, над крышами появилась тонкая полоса золота.',
    'Библиотекарь открыл новую дверь, и за ней оказался ещё один бесконечный зал.',
    'Каждая книга здесь ждала читателя, который однажды назовёт её точный адрес.',
)
ATLAS_EN_SENTENCES = (
    'A warm rain crossed the city in the morning, darkening the stones in the square.',
    'The old workshop was quiet except for a clock left by an unknown maker.',
    'Across the river, windows slowly lit up while the train entered the forest.',
    'A folded map rested on the shelf with a pencil mark near the edge of the paper.',
    'The garden smelled of mint, wet soil, and apples hidden in the tall grass.',
    'She wrote the thought in the margin so she could find it again the next morning.',
    'The wind turned the pages while the room filled with a gentle evening light.',
    'No one knew who sent the letter, yet every word felt strangely familiar.',
    'At the empty station they sold coffee, newspapers, and bread from a small oven.',
    'When the storm moved beyond the horizon, a narrow band of gold appeared.',
    'The librarian opened another door and found one more room without an ending.',
    'Every book waited for the reader who would one day speak its exact address.',
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

@lru_cache(maxsize=16)
def hierarchical_ranker(length):
    length = int(length)
    if (
        length < HIERARCHICAL_BLOCK_LENGTH
        or length > HIERARCHICAL_MAX_LENGTH
        or length % HIERARCHICAL_BLOCK_LENGTH
    ):
        raise ValueError(
            f'exact_hierarchical_v1 supports multiples of {HIERARCHICAL_BLOCK_LENGTH} '
            f'up to {HIERARCHICAL_MAX_LENGTH}'
        )
    return HierarchicalRawRanker(length=length, block_length=HIERARCHICAL_BLOCK_LENGTH)

def parse_rank(value):
    value = str(value)
    return int(value, 16) if value.lower().startswith('0x') else int(value)

def exact_api_payload(result, mode, length, ranker):
    payload = {
        'mode':mode,
        'length':length,
        'rank':str(result['rank']),
        'rank_hex':hex(result['rank']),
        'energy':result['energy'],
        'page':result['page'],
    }
    if mode == 'exact_hierarchical_v1':
        payload.update({
            'block_length': ranker.block_length,
            'blocks': ranker.blocks,
            'block_energies': result['block_energies'],
            'rank_order': 'lexicographic_exact_block_ranks',
        })
    return payload

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

def atlas_page(q=0, r=0, book=0, page=0, language='mix'):
    q, r, book, page = int(q), int(r), int(book), int(page)
    if abs(q) > 10**12 or abs(r) > 10**12 or not 0 <= book < 6 or page < 0 or page > 10**15:
        raise ValueError('atlas coordinates, book or page are outside supported bounds')
    language = str(language).lower()
    if language not in {'ru', 'en', 'mix'}:
        raise ValueError('language must be ru, en or mix')
    seed_text = f'atlas-v1:{q}:{r}:{book}:{page}:{language}'
    rng = random.Random(int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16))
    ru_title = ATLAS_RU_TITLES[(abs(q * 7 + r * 11 + book * 3) + page) % len(ATLAS_RU_TITLES)]
    en_title = ATLAS_EN_TITLES[(abs(q * 7 + r * 11 + book * 3) + page) % len(ATLAS_EN_TITLES)]
    ru = rng.sample(ATLAS_RU_SENTENCES, 2)
    en = rng.sample(ATLAS_EN_SENTENCES, 2)
    shelf_mark = f'{q}:{r}:{book + 1}:{page + 1}'
    if language == 'ru':
        title, text = ru_title, f'Архивная метка {shelf_mark}. {" ".join(ru)}'
    elif language == 'en':
        title, text = en_title, f'Archive mark {shelf_mark}. {" ".join(en)}'
    else:
        title = f'{ru_title} / {en_title}'
        text = f'Archive mark / архивная метка {shelf_mark}. {ru[0]} {en[0]}'
    # The public reader is one exact 256-symbol block. Trim on a word boundary
    # so generated prose stays readable before exact padding is applied.
    if len(text) > EXACT_CLUSTER_MAX_LENGTH:
        text = text[:EXACT_CLUSTER_MAX_LENGTH - 1].rsplit(' ', 1)[0] + '…'
    result = exact_cluster_ranker(EXACT_CLUSTER_MAX_LENGTH).rank_text(text)
    return {
        'version':'babel_hex_atlas_v1',
        'q':q, 'r':r, 'book':book, 'page_index':page, 'language':language,
        'title':title,
        'text':text,
        'exact_length':EXACT_CLUSTER_MAX_LENGTH,
        'rank':str(result['rank']),
        'rank_hex':hex(result['rank']),
        'energy':result['energy'],
    }

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
    if body.get('mode') == 'exact_hierarchical_v1':
        try:
            length=int(body.get('length', HIERARCHICAL_MAX_LENGTH))
            ranker=hierarchical_ranker(length)
            result=ranker.rank_text(body.get('text',''))
            return jsonify(exact_api_payload(result, 'exact_hierarchical_v1', length, ranker))
        except (ValueError, TypeError) as exc:
            return jsonify({'error':str(exc),'mode':'exact_hierarchical_v1'}),400
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
    if body.get('mode') == 'exact_hierarchical_v1':
        try:
            length=int(body.get('length', HIERARCHICAL_MAX_LENGTH))
            ranker=hierarchical_ranker(length)
            result=ranker.unrank_page(parse_rank(val))
            return jsonify(exact_api_payload(result, 'exact_hierarchical_v1', length, ranker))
        except (ValueError, TypeError) as exc:
            return jsonify({'error':str(exc),'mode':'exact_hierarchical_v1'}),400
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
    proof = json.loads(COUNTING_PROOF_MODEL.read_text(encoding='utf-8'))
    proof.update({
        'interactive_exact_max_length': EXACT_CLUSTER_MAX_LENGTH,
        'hierarchical_exact_max_length': HIERARCHICAL_MAX_LENGTH,
        'hierarchical_block_length': HIERARCHICAL_BLOCK_LENGTH,
        'hierarchical_blocks': HIERARCHICAL_MAX_LENGTH // HIERARCHICAL_BLOCK_LENGTH,
        'hierarchical_space_size': str(256 ** HIERARCHICAL_MAX_LENGTH),
        'hierarchical_space_complete': True,
        'hierarchical_bijection': 'base-(256^256) positional composition of exact block ranks',
        'compact_suffix_types': len(exact_cluster_ranker(EXACT_CLUSTER_MAX_LENGTH).compact_transitions),
        'rank_order': 'cluster_energy_then_raw_lexicographic',
    })
    return jsonify(proof)
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
@app.get('/api/atlas-page')
def api_atlas_page():
    try:
        return jsonify(atlas_page(
            request.args.get('q', 0), request.args.get('r', 0),
            request.args.get('book', 0), request.args.get('page', 0),
            request.args.get('lang', 'mix'),
        ))
    except (ValueError, TypeError) as exc:
        return jsonify({'error':str(exc),'version':'babel_hex_atlas_v1'}),400

if __name__=='__main__':
    app.run(
        host=os.environ.get('BABEL_HOST', '127.0.0.1'),
        port=int(os.environ.get('BABEL_PORT', '8090')),
    )
