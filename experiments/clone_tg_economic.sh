#!/usr/bin/env bash
set -euo pipefail
ROOT=/home/roomhacker/babel-experiments
RAW="$ROOT/datasets/raw"
mkdir -p "$RAW"
if [ ! -d "$RAW/TGEconomicDataset/.git" ]; then
  git clone https://github.com/pavel805/TGEconomicDataset.git "$RAW/TGEconomicDataset"
else
  git -C "$RAW/TGEconomicDataset" pull --ff-only
fi
du -sh "$RAW/TGEconomicDataset" || true
find "$RAW/TGEconomicDataset" -maxdepth 3 -type f | sed -n '1,120p'
