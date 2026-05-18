#!/usr/bin/env python3
from pathlib import Path
import csv, json, os, sys

ROOT=Path('/home/roomhacker/babel-experiments')
RAW=ROOT/'datasets/raw'
PROC=ROOT/'datasets/processed'
RAW.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)

from datasets import load_dataset


def write_texts(path: Path, iterable, limit=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    n=0
    with path.open('w', encoding='utf-8') as f:
        for text in iterable:
            if text is None:
                continue
            text=str(text).replace('\n',' ').strip()
            if not text:
                continue
            f.write(text+'\n')
            n+=1
            if limit and n>=limit:
                break
    print('wrote', path, 'lines', n, 'size', path.stat().st_size, flush=True)
    return n

# 1. TatarNLPWorld/sovet_kinesh-vk
try:
    outdir=RAW/'sovet_kinesh_vk'
    outdir.mkdir(exist_ok=True)
    print('loading TatarNLPWorld/sovet_kinesh-vk posts', flush=True)
    posts=load_dataset('TatarNLPWorld/sovet_kinesh-vk','posts', split='full')
    posts.to_pandas().to_csv(outdir/'posts.csv', index=False)
    print('loading TatarNLPWorld/sovet_kinesh-vk comments', flush=True)
    comments=load_dataset('TatarNLPWorld/sovet_kinesh-vk','comments', split='full')
    comments.to_pandas().to_csv(outdir/'comments.csv', index=False)
    # best-effort text extraction
    def rows_to_text(ds):
        for row in ds:
            for key in ('text','content','body','message'):
                if key in row and row[key]:
                    yield row[key]
                    break
    write_texts(PROC/'sovet_kinesh_vk_texts.txt', list(rows_to_text(posts))+list(rows_to_text(comments)))
except Exception as e:
    print('ERROR sovet_kinesh_vk', repr(e), flush=True)

# 2. Pikabu streaming subset
try:
    print('loading IlyaGusev/pikabu streaming subset', flush=True)
    ds=load_dataset('IlyaGusev/pikabu', split='train', streaming=True)
    def gen_pikabu(max_rows=200000):
        for i,row in enumerate(ds):
            text=row.get('text_markdown') or row.get('text') or ''
            if text:
                yield text
            comments=row.get('comments') or {}
            if isinstance(comments, dict):
                vals=comments.get('text', []) or comments.get('texts', []) or []
                for c in vals:
                    if c:
                        yield c
            if i>=max_rows:
                break
    write_texts(PROC/'pikabu_texts_200k.txt', gen_pikabu())
except Exception as e:
    print('ERROR pikabu', repr(e), flush=True)

# 3. Toxic Russian Comments
try:
    print('loading AlexSham/Toxic_Russian_Comments', flush=True)
    ds=load_dataset('AlexSham/Toxic_Russian_Comments', split='train')
    outdir=RAW/'toxic_russian_comments'
    outdir.mkdir(exist_ok=True)
    ds.to_pandas().to_csv(outdir/'toxic_russian_comments.csv', index=False)
    def gen_toxic():
        for row in ds:
            for key in ('comment','text','message','content'):
                if key in row and row[key]:
                    yield row[key]
                    break
    write_texts(PROC/'toxic_russian_comments.txt', gen_toxic())
except Exception as e:
    print('ERROR toxic', repr(e), flush=True)

# 4. TweetEval emoji
try:
    print('loading cardiffnlp/tweet_eval emoji', flush=True)
    dsdict=load_dataset('cardiffnlp/tweet_eval','emoji')
    outdir=RAW/'tweet_eval_emoji'
    outdir.mkdir(exist_ok=True)
    alltexts=[]
    for split,ds in dsdict.items():
        ds.to_pandas().to_csv(outdir/f'{split}.csv', index=False)
        for row in ds:
            if row.get('text'):
                alltexts.append(row['text'])
    write_texts(PROC/'tweet_eval_emoji_texts.txt', alltexts)
except Exception as e:
    print('ERROR tweet_eval_emoji', repr(e), flush=True)
