"""Read an anonymous page or reproduce the published continuation comparison."""
import argparse
import hashlib
import json
import math
import statistics
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'notes/experiments/continuation_study'
FLAGS = ('readable', 'through', 'restart')


def read_lines(path):
    with path.open(encoding='utf-8') as source:
        return [json.loads(line) for line in source]


def validate_reading(card, reading):
    """Each positive judgment must cite the original, unnormalized Unicode text."""
    first, second = card['first'], card['second']
    assert all(type(reading[flag]) is bool for flag in FLAGS)
    assert reading['reason'].strip()
    if reading['readable']:
        cite = reading['readable_quote']
        assert cite.strip() and (cite in first or cite in second), card['id']
    if reading['through'] or reading['restart']:
        for key, half in [('first_quote', first), ('second_quote', second)]:
            cite = reading[key]
            assert cite.strip() and cite in half, (card['id'], key)


def compare(arms, other):
    """Exact two-sided sign test conditional on the discordant matched seeds."""
    pairs = Counter((arms['v3'][seed]['through'], row['through']) for seed, row in arms[other].items())
    wins, losses = pairs[True, False], pairs[False, True]
    trials = wins + losses
    tail = sum(math.comb(trials, i) for i in range(min(wins, losses) + 1))
    return {
        'wins': wins,
        'losses': losses,
        'ties': sum(pairs.values()) - trials,
        'sign_test_p': min(1.0, 2 * tail / (2 ** trials)),
    }


def summarize(data=DATA):
    protocol = json.loads((data / 'protocol.json').read_text(encoding='utf-8'))
    samples = json.loads((data / 'key.json').read_text(encoding='utf-8'))
    pages = read_lines(data / 'pages.jsonl')
    cards = {card['id']: card for card in pages}
    assert len(cards) == len(pages) == len(samples)
    assert set(cards) == set(samples)
    ratings = {}
    for reading in read_lines(data / 'judgments.jsonl'):
        ident = reading['id']
        validate_reading(cards[ident], reading)
        index = (ident, reading['panel'])
        assert index not in ratings and reading['panel'] in ('a', 'b')
        ratings[index] = reading
    assert len(ratings) == 2 * len(cards)
    blinding = json.loads((data / 'blinding.json').read_text(encoding='utf-8'))
    for name, key in [('pages.jsonl', 'pages_sha256'), ('key.json', 'key_sha256')]:
        assert hashlib.sha256((data / name).read_bytes()).hexdigest() == blinding[key]
    assignment = {
        'items': {ident: {k: v for k, v in item.items() if k != 'sha256'}
                  for ident, item in samples.items()},
        'blocks': blinding['packets'],
    }
    encoded = json.dumps(assignment, ensure_ascii=False, sort_keys=True, indent=2) + '\n'
    assert hashlib.sha256(encoded.encode()).hexdigest() == blinding['allocation_sha256']
    assert set(blinding['packets']) == {panel + str(i) for panel in ('a', 'b') for i in range(1, 5)}
    for packet, ids in blinding['packets'].items():
        assert all(ratings[ident, packet[0]]['packet'] == packet for ident in ids)
        seeds = [samples[ident]['seed'] for ident in ids if 'seed' in samples[ident]]
        assert len(ids) == 13 and len(seeds) == len(set(seeds)) == 12

    by_arm = {arm: {} for arm in protocol['arms']}
    controls = {}
    qwen_openings = {}
    for ident, info in samples.items():
        first, second = cards[ident]['first'], cards[ident]['second']
        assert len(first) == len(second) == 2048
        assert hashlib.sha256((first + second).encode()).hexdigest() == info['sha256']
        a, b = ratings[ident, 'a'], ratings[ident, 'b']
        row = {flag: a[flag] and b[flag] for flag in FLAGS}
        row.update(panel_a=a['through'], panel_b=b['through'], disagree=a['through'] != b['through'])
        if info['arm'] == 'control':
            controls[info['control']] = row
        else:
            if info['arm'] in ('v2', 'v3'):
                qwen_openings[info['arm'], info['seed']] = first
            row['overlap'] = SequenceMatcher(None, first, second, autojunk=False).find_longest_match().size
            by_arm[info['arm']][info['seed']] = row
    assert set(controls) == {'ru_pos', 'ru_neg', 'en_pos', 'en_neg'}
    assert all(qwen_openings['v2', n] == qwen_openings['v3', n] for n in protocol['seeds'])
    scores = {}
    for arm, by_seed in by_arm.items():
        assert set(by_seed) == set(protocol['seeds'])
        rows = by_seed.values()
        scores[arm] = {
            key: sum(row[key] for row in rows)
            for key in (*FLAGS, 'panel_a', 'panel_b', 'disagree')
        }
        scores[arm].update(
            n=len(rows),
            median_overlap=statistics.median(row['overlap'] for row in rows),
            pages_with_overlap_80=sum(row['overlap'] >= 80 for row in rows),
        )
        if arm in ('v2', 'v3'):
            scores[arm]['through_by_language'] = {
                lang: sum(row['through'] for seed, row in by_seed.items() if seed % 2 == parity)
                for lang, parity in [('ru', 0), ('en', 1)]
            }
    pair_results = {arm: compare(by_arm, arm) for arm in by_arm if arm != 'v3'}
    old, new = scores['v2'], scores['v3']
    clears_threshold = (new['through'] >= old['through'] + 2
                        and new['median_overlap'] <= old['median_overlap'] / 2)
    return dict(scores=scores, paired=pair_results, controls=controls, clears_practical_threshold=clears_threshold)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--page', metavar='ID', help='вывести одну анонимную карточку целиком')
    args = parser.parse_args()
    if args.page:
        card = next((r for r in read_lines(DATA / 'pages.jsonl') if r['id'] == args.page), None)
        if card is None:
            parser.error('Неизвестная карточка')
        print(card['first'], '\n\n── Граница половин ──\n\n', card['second'], sep='')
    else:
        print(json.dumps(summarize(), ensure_ascii=False, indent=2))
