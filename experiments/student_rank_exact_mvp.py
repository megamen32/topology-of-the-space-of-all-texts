#!/usr/bin/env python3
"""
Exact energy-ordered rank/unrank MVP.

This is the real Library core shape:
  address = rank in order (student_energy(page), raw_lexicographic_tiebreaker)

For now this is intentionally small-length so the proof/counting layer is inspectable.
The algorithm is the same layer we need to scale/optimize for 4096 pages.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import json, argparse

ROOT=Path('/home/roomhacker/babel-experiments')
MODEL=json.loads((ROOT/'models/student_fsm_v1/student_fsm_v1.json').read_text(encoding='utf-8'))
ALPHABET=MODEL['alphabet']
A=len(ALPHABET)
IDX={c:i for i,c in enumerate(ALPHABET)}

# Use finite student costs. For MVP exactness, collapse state to previous class.
TRANS=MODEL['transition_costs']
EMIT=MODEL['emission_costs']
SYM_CLASS=MODEL['symbol_class']
CLASSES=MODEL['classes']
START='START'

# Cost table per previous class and symbol index.
def cost(prev: str, sym_i: int) -> int:
    ch=ALPHABET[sym_i]
    c=SYM_CLASS[ch]
    return int(TRANS.get(prev,{}).get(c,1500)) + int(EMIT.get(c,{}).get(ch,1500))

def next_state(sym_i:int)->str:
    return SYM_CLASS[ALPHABET[sym_i]]

# Precompute costs for speed.
COSTS={st:[cost(st,i) for i in range(A)] for st in set(CLASSES)|{START}}
NEXT=[next_state(i) for i in range(A)]

class ExactStudentRanker:
    def __init__(self, length:int, max_energy:int|None=None):
        self.length=length
        self.min_c=min(min(v) for v in COSTS.values())
        self.max_c=max(max(v) for v in COSTS.values())
        self.max_energy=max_energy or self.max_c*length

    def page_cost(self, page:str)->tuple[int,list[int]]:
        page=(page + ' '*self.length)[:self.length]
        ids=[IDX.get(ch,IDX.get(' ',0)) for ch in page]
        st=START; e=0
        for i in ids:
            e += COSTS[st][i]
            st=NEXT[i]
        return e, ids

    @lru_cache(maxsize=None)
    def count_exact(self, pos:int, st:str, energy:int)->int:
        if energy < 0: return 0
        if pos == self.length: return 1 if energy == 0 else 0
        left=self.length-pos
        if energy < left*self.min_c or energy > left*self.max_c: return 0
        total=0
        row=COSTS[st]
        for i,c in enumerate(row):
            total += self.count_exact(pos+1, NEXT[i], energy-c)
        return total

    @lru_cache(maxsize=None)
    def count_leq(self, pos:int, st:str, energy:int)->int:
        if energy < 0: return 0
        if pos == self.length: return 1
        left=self.length-pos
        if energy < left*self.min_c: return 0
        if energy >= left*self.max_c: return A**left
        return sum(self.count_exact(pos,st,e) for e in range(left*self.min_c, energy+1))

    def count_below_energy(self, energy:int)->int:
        return self.count_leq(0,START,energy-1)

    def rank(self,page:str)->dict:
        energy, ids = self.page_cost(page)
        rank=self.count_below_energy(energy)
        st=START; remaining=energy
        # lexicographic tie-breaker inside same energy
        for pos,sym in enumerate(ids):
            row=COSTS[st]
            for smaller in range(sym):
                c=row[smaller]
                rank += self.count_exact(pos+1, NEXT[smaller], remaining-c)
            remaining -= row[sym]
            st=NEXT[sym]
        return {'rank':rank,'energy':energy,'page':''.join(ALPHABET[i] for i in ids)}

    def unrank(self,rank:int)->dict:
        # Find energy bucket by binary-ish scan over feasible range.
        lo=self.length*self.min_c; hi=self.length*self.max_c
        # monotone count_leq over energy
        while lo<hi:
            mid=(lo+hi)//2
            if self.count_leq(0,START,mid)>rank: hi=mid
            else: lo=mid+1
        energy=lo
        before=self.count_below_energy(energy)
        offset=rank-before
        ids=[]; st=START; remaining=energy
        for pos in range(self.length):
            row=COSTS[st]
            for sym in range(A):
                c=row[sym]
                cnt=self.count_exact(pos+1,NEXT[sym],remaining-c)
                if offset >= cnt:
                    offset -= cnt
                else:
                    ids.append(sym); remaining -= c; st=NEXT[sym]; break
            else:
                raise RuntimeError('unrank failed')
        page=''.join(ALPHABET[i] for i in ids)
        return {'rank':rank,'energy':energy,'page':page}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--length',type=int,default=16)
    ap.add_argument('--rank-text')
    ap.add_argument('--unrank',type=int)
    ap.add_argument('--stats',action='store_true')
    args=ap.parse_args()
    r=ExactStudentRanker(args.length)
    if args.stats:
        print(json.dumps({'length':args.length,'alphabet':A,'min_symbol_cost':r.min_c,'max_symbol_cost':r.max_c,'space_size':str(A**args.length)},ensure_ascii=False,indent=2))
    if args.rank_text is not None:
        print(json.dumps(r.rank(args.rank_text),ensure_ascii=False,indent=2,default=str))
    if args.unrank is not None:
        print(json.dumps(r.unrank(args.unrank),ensure_ascii=False,indent=2,default=str))
if __name__=='__main__': main()
