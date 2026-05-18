#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path('/home/roomhacker/babel-experiments')
RAW = ROOT / 'datasets' / 'raw'
OUT = ROOT / 'datasets' / 'processed'
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / 'sample_ru_en_dialogue_books.txt'

parts = []

def add_file(p: Path, max_bytes: int | None = None):
    try:
        data = p.read_bytes()
    except Exception:
        return
    if b'\x00' in data[:4096]:
        return
    if max_bytes:
        data = data[:max_bytes]
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = data.decode('cp1251')
        except UnicodeDecodeError:
            text = data.decode('utf-8', errors='ignore')
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > 200:
        parts.append(text)

# Russian literature: cap to keep MVP small
ruslit = RAW / 'ruslit'
if ruslit.exists():
    for p in sorted(ruslit.rglob('*.txt'))[:200]:
        add_file(p, max_bytes=512_000)

# Gutenberg books
for p in sorted((RAW / 'gutenberg').glob('*.txt')):
    add_file(p, max_bytes=2_000_000)

# OpenSubtitles dev/test text-like files
opensub = RAW / 'opensubtitles-devtest'
if opensub.exists():
    for p in sorted(opensub.rglob('*')):
        if p.is_file() and p.suffix.lower() in {'.txt', '.ru', '.en', '.xml'}:
            add_file(p, max_bytes=256_000)

TARGET.write_text('\n\n'.join(parts), encoding='utf-8')
print(f'wrote {TARGET}')
print(f'parts={len(parts)} chars={TARGET.stat().st_size}')
