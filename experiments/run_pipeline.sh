#!/usr/bin/env bash
set -euo pipefail

ROOT=${BABEL_ROOT:-/home/roomhacker/babel-experiments}
EXP="$ROOT/experiments"
SITE="$ROOT/site"
LOG_PREFIX="[pipeline]"

log(){ echo "$LOG_PREFIX $(date -Is) $*"; }
fail(){ echo "$LOG_PREFIX ERROR: $*" >&2; exit 1; }
need_file(){ [[ -s "$1" ]] || fail "missing or empty file: $1"; }

run_step(){
  local name="$1"; shift
  log "START $name"
  "$@"
  log "DONE  $name"
}

export_site_model(){
python3 - <<'PY'
from pathlib import Path
import json
ROOT=Path('/home/roomhacker/babel-experiments')
SITE=ROOT/'site'; (SITE/'data').mkdir(parents=True, exist_ok=True)
alpha_path=ROOT/'models/top256_alphabet_v2/alphabet_top256_v2.json'
fsm_path=ROOT/'models/student_fsm_v1/student_fsm_v1.json'
alpha=json.loads(alpha_path.read_text(encoding='utf-8'))
fsm=json.loads(fsm_path.read_text(encoding='utf-8'))
payload={
 'version':'v2-pure-js',
 'alphabet':alpha['alphabet'],
 'coverage':alpha['coverage'],
 'total_chars':alpha['total_chars'],
 'unique_chars':alpha['unique_chars'],
 'raw_unique_chars':alpha.get('raw_unique_chars'),
 'emoji_top':alpha['emoji_top'][:50],
 'unknown_top':alpha['unknown_top_if_top256'][:40],
 'symbol_class':fsm['symbol_class'],
 'transitions':fsm['transitions'],
 'emissions':fsm['emissions'],
 'transition_costs':fsm['transition_costs'],
 'emission_costs':fsm['emission_costs'],
 'stats':fsm['stats'],
}
out=SITE/'data/model.json'
out.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
print('exported', out, out.stat().st_size)
print('coverage', alpha['coverage'], 'alphabet_len', len(alpha['alphabet']), 'student_symbols', fsm['stats']['symbols'])
PY
}

smoke_test(){
python3 - <<'PY'
from pathlib import Path
import json
ROOT=Path('/home/roomhacker/babel-experiments')
j=json.loads((ROOT/'site/data/model.json').read_text(encoding='utf-8'))
assert j['version']=='v2-pure-js'
assert len(j['alphabet'])==256
assert j['coverage'] > 0.99
assert 'transition_costs' in j and 'emission_costs' in j
print('OK model.json', 'coverage=', j['coverage'], 'alphabet=', len(j['alphabet']))
PY
curl -fsS http://127.0.0.1:8088/ >/dev/null || echo "WARN: local static server not responding on :8088"
}

main(){
  log "root=$ROOT"
  run_step "build alphabet v2" python3 "$EXP/build_normalized_alphabet.py"
  need_file "$ROOT/models/top256_alphabet_v2/alphabet_top256_v2.json"

  run_step "train student v1" python3 "$EXP/retrain_student_v2.py"
  need_file "$ROOT/models/student_fsm_v1/student_fsm_v1.json"

  run_step "export site model" export_site_model
  need_file "$SITE/data/model.json"

  run_step "smoke test" smoke_test

  log "pipeline complete"
}

main "$@"
