#!/usr/bin/env bash
set -euo pipefail
ROOT=${BABEL_ROOT:-/home/roomhacker/babel-experiments}
EXP="$ROOT/experiments"
SITE="$ROOT/site/data"
log(){ echo "[hier-students] $(date -Is) $*"; }
log 'START text cache + word student pipeline'
bash "$EXP/run_word_student_pipeline.sh"
log 'DONE word student pipeline'
log 'START sentence student pipeline'
bash "$EXP/run_sentence_student_pipeline.sh"
log 'DONE sentence student pipeline'
log 'START paragraph student'
python3 "$EXP/build_paragraph_student_v1.py"
log 'DONE paragraph student'
python3 - <<'PY'
from pathlib import Path
import json
ROOT=Path('/home/roomhacker/babel-experiments')
SITE=ROOT/'site/data'; SITE.mkdir(parents=True,exist_ok=True)
exports=[
 ('models/word_student_v1/word_student_v1.json','word_student.json'),
 ('models/sentence_student_v1/sentence_student_v1.json','sentence_student.json'),
 ('models/paragraph_student_v1/paragraph_student_v1.json','paragraph_student.json'),
]
for src,dst in exports:
    data=json.loads((ROOT/src).read_text(encoding='utf-8'))
    (SITE/dst).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    print('exported', dst, (SITE/dst).stat().st_size)
PY
log 'DONE export site data'
