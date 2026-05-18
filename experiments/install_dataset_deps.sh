#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/roomhacker/babel-experiments
source "$ROOT/venvs/datasets/bin/activate"
python -m pip install --upgrade pip
python -m pip install datasets pandas pyarrow zstandard jsonlines pysimdjson regex huggingface_hub
