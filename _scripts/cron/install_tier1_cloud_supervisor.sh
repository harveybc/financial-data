#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/harveybc/Documents/GitHub/financial-data}"
MODEL="${PROJECT3_TIER1_HERMES_MODEL:-gemma4:31b-cloud}"
CRON_LOG="$PROJECT_ROOT/_logs/supervisor_reports/tier1_cron.log"
WRAPPER="$PROJECT_ROOT/_scripts/cron/run_tier1_supervisor.sh"

source "$HOME/.bashrc" >/dev/null 2>&1 || true
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
  conda activate tensorflow >/dev/null 2>&1 || true
fi

mkdir -p "$(dirname "$CRON_LOG")"

if ! ollama pull "$MODEL" >/dev/null 2>&1; then
  echo "Unable to pull $MODEL. Run 'ollama signin' on this machine and approve the device in ollama.com first." >&2
  exit 1
fi

tmp="$(mktemp)"
crontab -l 2>/dev/null | grep -v 'project3-tier1' | grep -v '^PROJECT3_TIER1_HERMES_MODEL=' > "$tmp" || true
{
  cat "$tmp"
  echo "PROJECT3_TIER1_HERMES_MODEL=$MODEL"
  echo "*/5 * * * * $WRAPPER >> $CRON_LOG 2>&1 # project3-tier1"
} | crontab -
rm -f "$tmp"

ollama stop gemma4:31b >/dev/null 2>&1 || true

echo "Installed Project 3 Tier 1 cloud supervisor using $MODEL"
