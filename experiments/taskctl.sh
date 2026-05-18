#!/usr/bin/env bash
set -euo pipefail
ROOT=${BABEL_ROOT:-/home/roomhacker/babel-experiments}
TASKS="$ROOT/tasks"
LOGS="$TASKS/logs"
STATE="$TASKS/state"
mkdir -p "$LOGS" "$STATE"

usage(){
  cat <<EOF
Usage:
  $0 start <name> -- <command...>
  $0 status [name]
  $0 list
  $0 tail <name> [lines]
  $0 log <name>
  $0 stop <name>
EOF
}

is_running(){ local pid="$1"; [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; }

write_status(){
  local name="$1" status="$2" f="$STATE/$name.env" tmp="$STATE/$name.env.tmp"
  { [[ -f "$f" ]] && grep -vE '^(STATUS|UPDATED_AT)=' "$f" || true; echo "STATUS=$status"; echo "UPDATED_AT=$(date -Is)"; } > "$tmp"
  mv "$tmp" "$f"
}

shell_quote_cmd(){ printf '%q ' "$@"; }

cmd=${1:-}
case "$cmd" in
  start)
    name=${2:-}; [[ -n "$name" ]] || { usage; exit 2; }
    shift 2; [[ ${1:-} == "--" ]] || { usage; exit 2; }; shift
    [[ $# -gt 0 ]] || { usage; exit 2; }
    f="$STATE/$name.env"
    if [[ -f "$f" ]]; then
      # shellcheck disable=SC1090
      source "$f" || true
      if [[ ${PID:-} =~ ^[0-9]+$ ]] && is_running "$PID"; then echo "task already running: $name pid=$PID"; exit 1; fi
    fi
    log="$LOGS/$name.log"
    wrapper="$TASKS/$name.wrapper.sh"
    qcmd=$(shell_quote_cmd "$@")
    cat > "$wrapper" <<EOF
#!/usr/bin/env bash
set -o pipefail
cd "$ROOT"
echo "STARTED_AT=\$(date -Is)"
echo "CMD=$qcmd"
$qcmd
rc=\$?
echo "EXIT_CODE=\$rc"
echo "FINISHED_AT=\$(date -Is)"
exit \$rc
EOF
    chmod +x "$wrapper"
    nohup bash "$wrapper" > "$log" 2>&1 &
    pid=$!
    cat > "$f" <<EOF
NAME=$name
PID=$pid
STATUS=running
STARTED_AT=$(date -Is)
LOG=$log
CMD_B64=$(printf '%s' "$qcmd" | base64 -w0)
EOF
    echo "started $name pid=$pid log=$log"
    ;;
  status)
    if [[ $# -ge 2 ]]; then names=("$2"); else mapfile -t names < <(find "$STATE" -maxdepth 1 -name '*.env' -printf '%f\n' | sed 's/\.env$//' | sort); fi
    for name in "${names[@]}"; do
      f="$STATE/$name.env"; [[ -f "$f" ]] || { echo "$name: no such task"; continue; }
      # shellcheck disable=SC1090
      source "$f" || true
      if [[ ${PID:-} =~ ^[0-9]+$ ]] && is_running "$PID"; then status=running; else
        status=finished
        if [[ -f "${LOG:-}" ]]; then
          if grep -q '^EXIT_CODE=0$' "$LOG"; then status=done; elif grep -q '^EXIT_CODE=' "$LOG"; then status=failed; fi
        fi
      fi
      write_status "$name" "$status"
      echo "$name: status=$status pid=${PID:-?} log=${LOG:-?}"
      [[ -f "${LOG:-}" ]] && tail -n 8 "$LOG" | sed 's/^/  | /'
    done
    ;;
  list) "$0" status ;;
  wait)
    name=${2:-}; timeout_s=${3:-10}
    [[ -n "$name" ]] || { usage; exit 2; }
    f="$STATE/$name.env"; [[ -f "$f" ]] || { echo "no such task: $name"; exit 1; }
    start_ts=$(date +%s)
    while true; do
      # shellcheck disable=SC1090
      source "$f" || true
      if [[ ${PID:-} =~ ^[0-9]+$ ]] && is_running "$PID"; then
        now=$(date +%s)
        if (( now - start_ts >= timeout_s )); then
          echo "$name: still running pid=${PID:-?}"
          [[ -f "${LOG:-}" ]] && tail -n 12 "$LOG" | sed 's/^/  | /'
          exit 0
        fi
        sleep 1
      else
        "$0" status "$name"
        exit 0
      fi
    done
    ;;
  tail)
    name=${2:-}; lines=${3:-80}; [[ -n "$name" ]] || { usage; exit 2; }
    f="$STATE/$name.env"; [[ -f "$f" ]] || { echo "no such task: $name"; exit 1; }
    # shellcheck disable=SC1090
    source "$f"; tail -n "$lines" "$LOG" ;;
  log)
    name=${2:-}; [[ -n "$name" ]] || { usage; exit 2; }
    f="$STATE/$name.env"; [[ -f "$f" ]] || { echo "no such task: $name"; exit 1; }
    # shellcheck disable=SC1090
    source "$f"; echo "$LOG" ;;
  stop)
    name=${2:-}; [[ -n "$name" ]] || { usage; exit 2; }
    f="$STATE/$name.env"; [[ -f "$f" ]] || { echo "no such task: $name"; exit 1; }
    # shellcheck disable=SC1090
    source "$f"
    if [[ ${PID:-} =~ ^[0-9]+$ ]] && is_running "$PID"; then kill "$PID"; write_status "$name" stopped; echo "stopped $name pid=$PID"; else echo "$name is not running"; fi ;;
  *) usage; exit 2;;
esac
