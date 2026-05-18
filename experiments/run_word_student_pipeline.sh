#!/usr/bin/env bash
set -euo pipefail
ROOT=${BABEL_ROOT:-/home/roomhacker/babel-experiments}
EXP="$ROOT/experiments"
log(){ echo "[word-pipeline] $(date -Is) $*"; }
log 'START cache'; python3 "$EXP/build_text_cache.py"; log 'DONE cache'
log 'START stats'; python3 "$EXP/count_cache_stats.py"; log 'DONE stats'
log 'START word student'; python3 "$EXP/build_word_student_v1.py"; log 'DONE word student'
python3 - <<'PY'
from pathlib import Path
import json
ROOT=Path('/home/roomhacker/babel-experiments')
site=ROOT/'site/data'
site.mkdir(parents=True,exist_ok=True)
word=json.loads((ROOT/'models/word_student_v1/word_student_v1.json').read_text(encoding='utf-8'))
stats=json.loads((ROOT/'models/text_stats_v1/stats.json').read_text(encoding='utf-8'))
(site/'word_student.json').write_text(json.dumps(word,ensure_ascii=False),encoding='utf-8')
(site/'freq_stats.json').write_text(json.dumps({'top_chars':stats['top_chars'][:256],'summary':{k:stats[k] for k in ['chars_total','chars_unique','words_total','words_unique','sentences','paragraphs']}},ensure_ascii=False),encoding='utf-8')
print('exported word_student', (site/'word_student.json').stat().st_size, 'freq_stats', (site/'freq_stats.json').stat().st_size)
PY
log 'DONE export site word data'
