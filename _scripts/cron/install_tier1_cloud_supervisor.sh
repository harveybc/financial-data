#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/home/harveybc/Documents/GitHub/financial-data}"
MODEL="${PROJECT3_TIER1_HERMES_MODEL:-deepseek-v4-flash:cloud}"
FALLBACK_MODELS="${PROJECT3_TIER1_HERMES_FALLBACK_MODELS:-gemma4:31b-cloud}"
EXPERIMENT_UNTIL="${PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL:-2026-05-03T23:59:59Z}"
MODEL_TIMEOUT_SECONDS="${PROJECT3_TIER1_MODEL_TIMEOUT_SECONDS:-75}"
CRON_LOG="$PROJECT_ROOT/_logs/supervisor_reports/tier1_cron.log"
WRAPPER="$PROJECT_ROOT/_scripts/cron/run_tier1_supervisor.sh"

source "$HOME/.bashrc" >/dev/null 2>&1 || true
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
  conda activate tensorflow >/dev/null 2>&1 || true
fi

mkdir -p "$(dirname "$CRON_LOG")"

pull_model() {
  local model="$1"
  model="${model#"${model%%[![:space:]]*}"}"
  model="${model%"${model##*[![:space:]]}"}"
  [ -n "$model" ] || return 0
  if ! ollama pull "$model" >/dev/null 2>&1; then
    echo "Unable to pull $model. Run 'ollama signin' on this machine and approve the device in ollama.com first." >&2
    exit 1
  fi
}

pull_model "$MODEL"
IFS=',' read -r -a fallback_parts <<< "$FALLBACK_MODELS"
for fallback_model in "${fallback_parts[@]}"; do
  pull_model "$fallback_model"
done

tmp="$(mktemp)"
crontab -l 2>/dev/null \
  | grep -v 'project3-tier1' \
  | grep -v '^PROJECT3_TIER1_HERMES_MODEL=' \
  | grep -v '^PROJECT3_TIER1_HERMES_FALLBACK_MODELS=' \
  | grep -v '^PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL=' \
  | grep -v '^PROJECT3_TIER1_MODEL_TIMEOUT_SECONDS=' > "$tmp" || true
{
  cat "$tmp"
  echo "PROJECT3_TIER1_HERMES_MODEL=$MODEL"
  echo "PROJECT3_TIER1_HERMES_FALLBACK_MODELS=$FALLBACK_MODELS"
  echo "PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL=$EXPERIMENT_UNTIL"
  echo "PROJECT3_TIER1_MODEL_TIMEOUT_SECONDS=$MODEL_TIMEOUT_SECONDS"
  echo "*/5 * * * * $WRAPPER >> $CRON_LOG 2>&1 # project3-tier1"
} | crontab -
rm -f "$tmp"

ollama stop gemma4:31b >/dev/null 2>&1 || true

echo "Installed Project 3 Tier 1 cloud supervisor using $MODEL with fallbacks $FALLBACK_MODELS until $EXPERIMENT_UNTIL and per-model timeout ${MODEL_TIMEOUT_SECONDS}s"
