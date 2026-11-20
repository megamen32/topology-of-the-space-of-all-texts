#!/bin/bash
# PID 1 owns both children. A signal or the exit of either child stops the pair.
set -u
children=()
stop_children() {
    trap '' TERM INT
    if (( ${#children[@]} )); then
        kill -TERM "${children[@]}" 2>/dev/null || true
        wait "${children[@]}" 2>/dev/null || true
    fi
}
trap stop_children EXIT
trap 'exit 0' TERM INT

"$@" &
children+=("$!")
python3 /opt/babel/experiments/qwen_reference.py serve \
    --host 0.0.0.0 --port 8081 --endpoint http://127.0.0.1:8080 &
children+=("$!")
wait -n
