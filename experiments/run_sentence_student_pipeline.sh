#!/usr/bin/env bash
set -euo pipefail
ROOT=${BABEL_ROOT:-/home/roomhacker/babel-experiments}
EXP="$ROOT/experiments"
SITE="$ROOT/site"
log(){ echo "[sentence-pipeline] $(date -Is) $*"; }
# Ensure lower layers exist.
if [ ! -s "$ROOT/models/word_student_v1/word_student_v1.json" ]; then
  log 'word student missing, running word pipeline'
  bash "$EXP/run_word_student_pipeline.sh"
fi
log 'START sentence student'
python3 "$EXP/build_sentence_student_v1.py"
log 'DONE sentence student'
python3 - <<'PY'
from pathlib import Path
import json
ROOT=Path('/home/roomhacker/babel-experiments')
SITE=ROOT/'site/data'; SITE.mkdir(parents=True,exist_ok=True)
model=json.loads((ROOT/'models/sentence_student_v1/sentence_student_v1.json').read_text(encoding='utf-8'))
(SITE/'sentence_student.json').write_text(json.dumps(model,ensure_ascii=False),encoding='utf-8')
print('exported', SITE/'sentence_student.json', (SITE/'sentence_student.json').stat().st_size)
PY
log 'DONE export sentence student'
