"""Recompute the blinded story comparison from the published records."""
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def consensus(rows):
    counts = dict(full=0, reader_a_full=0, reader_b_full=0, links=0, language_and_length=0)
    coherence = 0
    for row in rows:
        a, b = row['reader_a'], row['reader_b']
        links = sum(x and y for x, y in zip(a['criteria'], b['criteria'], strict=True))
        counts['full'] += links == 3
        counts['reader_a_full'] += all(a['criteria'])
        counts['reader_b_full'] += all(b['criteria'])
        counts['links'] += links
        good_length = 150 <= row['measurement']['words'] <= 220
        counts['language_and_length'] += good_length and a['language_ok'] and b['language_ok']
        coherence += (a['coherence'] + b['coherence']) / 2
    chars = sum(len(row['text']) for row in rows)
    decode = sum(row['measurement']['decode_s'] for row in rows)
    wall = sum(row['measurement']['wall_s'] for row in rows)
    return {**counts, 'coherence': coherence, 'chars_per_decode_s': round(chars/decode, 1),
            'chars_per_wall_s': round(chars/wall, 1)}


def main():
    design = json.loads((ROOT / 'design.json').read_text())
    environment = json.loads((ROOT / 'environment.json').read_text())
    responses = [json.loads(line) for line in (ROOT / 'responses.jsonl').read_text().splitlines()]
    expected = {(model['tag'], task) for model in environment['models'] for task in design['tasks']}
    assert {(row['model'], row['task']) for row in responses} == expected
    assert len(responses) == len(expected) == len({row['id'] for row in responses})
    for row in responses:
        assert hashlib.sha256(row['text'].encode()).hexdigest() == row['sha256']
        assert len(row['text']) == row['measurement']['chars']
    output = []
    for model in sorted(environment['models'], key=lambda m: m['tag_size_bytes']):
        group = [row for row in responses if row['model'] == model['tag']]
        for lang in ['all', 'ru', 'en']:
            rows = group if lang == 'all' else [r for r in group if r['task'].endswith('_' + lang)]
            output.append({'model': model['tag'], 'language': lang, 'stories': len(rows), **consensus(rows)})
    writer = csv.DictWriter(sys.stdout, fieldnames=list(output[0]), lineterminator='\n')
    writer.writeheader()
    writer.writerows(output)


if __name__ == '__main__':
    main()
