#!/usr/bin/env python3
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json

ROOT = Path('/home/roomhacker/babel-experiments')
SITE = ROOT / 'site/data'

WORD = json.loads((SITE/'word_student.json').read_text())
SENT = json.loads((SITE/'sentence_student.json').read_text())
PARA = json.loads((SITE/'paragraph_student.json').read_text())

MAX_PAGE_LEN = 4096

@dataclass(frozen=True)
class SentenceTemplate:
    template: str
    count: int

@dataclass(frozen=True)
class ParagraphShape:
    shape: str
    count: int

class HierarchicalEnumeratorV1:
    """
    Foundational exact hierarchy layer.

    NOT yet a production counter.

    Purpose:
      - freeze hierarchy semantics
      - define deterministic ordering
      - define fallback reachability
      - provide future counting hooks
    """

    def __init__(self):
        self.templates = [
            SentenceTemplate(
                t['template'],
                int(t['count'])
            )
            for t in SENT['templates']
        ]

        self.paragraph_shapes = [
            ParagraphShape(
                p['shape'],
                int(p['count'])
            )
            for p in PARA['top_paragraph_shapes']
            if isinstance(p, dict) and 'shape' in p
        ]

        self.vocab = WORD['vocab']
        self.vocab_index = {
            tok:i for i,tok in enumerate(self.vocab)
        }

    # -------------------------------------------------
    # hierarchy semantics
    # -------------------------------------------------

    def hierarchy(self):
        return {
            'page': [
                'paragraphs'
            ],
            'paragraph': [
                'sentence_templates'
            ],
            'sentence_template': [
                'tokens'
            ],
            'token': [
                'raw_bytes_fallback'
            ]
        }

    # -------------------------------------------------
    # deterministic ordering
    # -------------------------------------------------

    def sentence_energy(self, template: str) -> int:
        for t in self.templates:
            if t.template == template:
                return max(1, 1_000_000 // max(1, t.count))
        return 10**9

    def token_energy(self, token: str) -> int:
        idx = self.vocab_index.get(token)
        if idx is None:
            return 1_000_000
        return idx + 1

    def fallback_energy(self, raw: bytes) -> int:
        return 10**7 + len(raw)

    # -------------------------------------------------
    # completeness guarantee
    # -------------------------------------------------

    def encode_raw_fallback(self, text: str):
        raw = text.encode('utf-8', errors='replace')
        return {
            'mode': 'fallback',
            'bytes': list(raw),
            'energy': self.fallback_energy(raw)
        }

    def page_reachable(self, text: str) -> bool:
        raw = text.encode('utf-8', errors='replace')
        return len(raw) <= MAX_PAGE_LEN

    # -------------------------------------------------
    # future counting hooks
    # -------------------------------------------------

    def _class_size(self, symbol: str) -> int:
        symbol = symbol.strip()

        if symbol == 'R':
            return len(WORD['abstract_emissions'].get('<ru>', []))

        if symbol == 'L':
            return len(WORD['abstract_emissions'].get('<en>', []))

        if symbol == 'E':
            return len(WORD['abstract_emissions'].get('<num>', []))

        if symbol == 'T':
            punct = ['.', '!', '?', '…']
            return len(punct)

        return 256

    def count_sentence(self, template: str, energy_budget: int):
        symbols = [s for s in template.split() if s.strip()]

        exact_count = 1
        min_energy = 0

        for sym in symbols:
            sz = self._class_size(sym)
            exact_count *= max(1, sz)
            min_energy += max(1, sz)

        reachable = min_energy <= energy_budget

        return {
            'template': template,
            'symbols': symbols,
            'exact_count': exact_count,
            'min_energy': min_energy,
            'energy_budget': energy_budget,
            'reachable_under_budget': reachable,
            'ordering': [
                'energy',
                'template',
                'lexicographic'
            ]
        }

    def count_paragraph(self, shape: str, energy_budget: int):
        return {
            'status': 'stub',
            'shape': shape,
            'energy_budget': energy_budget
        }

    def count_page(self, energy_budget: int):
        return {
            'status': 'stub',
            'energy_budget': energy_budget
        }


def demo():
    h = HierarchicalEnumeratorV1()

    print(json.dumps({
        'hierarchy': h.hierarchy(),
        'template_count': len(h.templates),
        'paragraph_shapes': len(h.paragraph_shapes),
        'vocab_size': len(h.vocab),
        'reachable': h.page_reachable('привет world 😂'),
        'fallback_demo': h.encode_raw_fallback('привет world 😂')
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    demo()
