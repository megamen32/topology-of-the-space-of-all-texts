#!/usr/bin/env bash
set -euo pipefail

# Model selection is explicit and the API key remains in the environment.
# Do not put credentials in this repository.
export GRAPHIFY_OPENAI_MODEL="gpt-5.4-mini"

exec graphify extract "${1:-.}" \
  --backend openai \
  --model "$GRAPHIFY_OPENAI_MODEL" \
  --max-concurrency "${GRAPHIFY_MAX_CONCURRENCY:-4}" \
  --out "${2:-.}"
