#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/harveybc/Documents/GitHub/financial-data}"
LOCK_FILE="/tmp/project3_stage32_hardening_refresh.lock"
STATE_FILE="$PROJECT_ROOT/_metadata/stage32_hardening_refresh_state.env"
INDEX_FILE="$PROJECT_ROOT/experiments/stage_a_screening/index.csv"
SUMMARY_FILE="$PROJECT_ROOT/experiments/stage_a_screening/stage_a_summary.md"

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

  ledger_hash="$(sha256sum "$PROJECT_ROOT/artifacts/run_ledger.jsonl" | awk '{print $1}')"
  previous_hash=""
  if [ -f "$STATE_FILE" ]; then
    previous_hash="$(grep '^ledger_hash=' "$STATE_FILE" | tail -1 | cut -d= -f2- || true)"
  fi
  if [ "$ledger_hash" = "$previous_hash" ] && [ -s "$INDEX_FILE" ] && [ -s "$SUMMARY_FILE" ]; then
    echo "stage32_hardening_refresh: skipped synthesis; ledger hash unchanged ($ledger_hash)"
    exit 0
  fi

  echo "stage32_hardening_refresh: rebuilding Stage A synthesis"
  PYTHONDONTWRITEBYTECODE=1 nice -n 5 python -u _scripts/workers/stage32_stage_a_synthesis_worker.py
  mkdir -p "$(dirname "$STATE_FILE")"
  {
    echo "ledger_hash=$ledger_hash"
    echo "updated_at=$(date --iso-8601=seconds)"
  } > "$STATE_FILE"
  echo "stage32_hardening_refresh: done"
) 9>"$LOCK_FILE"
