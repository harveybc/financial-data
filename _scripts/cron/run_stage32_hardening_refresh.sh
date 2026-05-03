#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/harveybc/Documents/GitHub/financial-data}"
LOCK_FILE="/tmp/project3_stage32_hardening_refresh.lock"

source "$HOME/.bashrc" >/dev/null 2>&1 || true
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/anaconda3/etc/profile.d/conda.sh" >/dev/null 2>&1 || true
  conda activate tensorflow >/dev/null 2>&1 || true
fi

cd "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/_logs/supervisor_reports"

(
  flock -n 9 || {
    date --iso-8601=seconds
    echo "stage32_hardening_refresh: skipped; previous refresh still running"
    exit 0
  }

  date --iso-8601=seconds
  echo "stage32_hardening_refresh: combining ledger"
  PYTHONDONTWRITEBYTECODE=1 nice -n 5 python -u _scripts/workers/stage31_combine_ledger_worker.py
  echo "stage32_hardening_refresh: rebuilding Stage A synthesis"
  PYTHONDONTWRITEBYTECODE=1 nice -n 5 python -u _scripts/workers/stage32_stage_a_synthesis_worker.py
  echo "stage32_hardening_refresh: done"
) 9>"$LOCK_FILE"
