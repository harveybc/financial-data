#!/usr/bin/env bash
set -u

PROJECT_ROOT="${PROJECT_ROOT:-/home/harveybc/Documents/GitHub/financial-data}"
LOG_DIR="$PROJECT_ROOT/_logs/supervisor_reports"
LOCKFILE="/tmp/gpu_busy.lock"
HERMES_BIN="${HERMES_BIN:-$HOME/.local/bin/hermes}"
PROJECT3_HERMES_SKILLS="${PROJECT3_HERMES_SKILLS:-project3-autonomous-supervisor,project3-deliverable-validator,systematic-debugging,hermes-agent-skill-authoring}"
HOST="$(hostname)"
STATUS_FILE="$LOG_DIR/${HOST}_status.json"
CONTEXT_PACKET="$LOG_DIR/${HOST}_context_packet.md"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$LOG_DIR"

source "$HOME/.bashrc" >/dev/null 2>&1 || true
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
  conda activate tensorflow >/dev/null 2>&1 || true
fi

"$HERMES_BIN" curator resume >/dev/null 2>&1 || true

write_status() {
  local status="$1"
  local detail="$2"
  local confidence="${3:-0.8}"
  python - "$STATUS_FILE" "$HOST" "$NOW" "$status" "$detail" "$confidence" <<'PY'
import json
import sys

path, host, now, status, detail, confidence = sys.argv[1:]
payload = {
    "machine": host,
    "tier": "tier1_local_supervisor",
    "generated_at": now,
    "status": status,
    "detail": detail,
    "confidence": float(confidence),
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2)
    f.write("\n")
PY
}

lock_state="$(python - "$LOCKFILE" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = sys.argv[1]
if not os.path.exists(path):
    print("none")
    raise SystemExit

try:
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    acquired = datetime.fromisoformat(payload["acquired_at"].replace("Z", "+00:00"))
    expected = float(payload.get("expected_duration_minutes", 5))
    age_minutes = (datetime.now(timezone.utc) - acquired).total_seconds() / 60
    print("stale" if age_minutes > expected * 2 else "fresh")
except Exception:
    print("unreadable")
PY
)"

if [ "$lock_state" = "fresh" ]; then
  owner="$(python - "$LOCKFILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    p = json.load(f)
print(f"gpu busy by PID {p.get('owner_pid')} ({p.get('owner_command')}, stage {p.get('stage')})")
PY
)"
  write_status "skipped_gpu_busy" "$owner" "0.95"
  exit 0
fi

if [ "$lock_state" = "stale" ] || [ "$lock_state" = "unreadable" ]; then
  rm -f "$LOCKFILE"
  stale_note="removed $lock_state GPU lock before supervisor run"
else
  stale_note=""
fi

python - "$LOCKFILE" "$$" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, pid = sys.argv[1:]
payload = {
    "owner_pid": int(pid),
    "owner_command": "project3_tier1_hermes_supervisor",
    "acquired_at": datetime.now(timezone.utc).isoformat(),
    "expected_duration_minutes": 5,
    "stage": "1.3",
}
with open(path, "w", encoding="utf-8") as f:
    json.dump(payload, f)
PY
trap 'rm -f "$LOCKFILE"' EXIT

gpu_summary="$(nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader 2>/dev/null || echo "nvidia-smi unavailable")"
case "$HOST" in
  dragon)
    stage_context="Stage 1.3 Free Data Acquisition, Task 1.3.F Binance crypto comprehensive"
    expected_deliverable="market_data/crypto/spot_top50, market_data/crypto/perpetuals, market_data/crypto/funding_rates"
    relevant_logs="_logs/dragon/stage13_crypto_worker.log; _logs/dragon/stage13_crypto_python.out; _logs/supervisor_reports/dragon_status.json"
    relevant_docs="work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md"
    ;;
  gamma)
    stage_context="Stage 1.3 Free Data Acquisition, Gamma macro/on-chain/supplemental public sources"
    expected_deliverable="macro_economic/fred, macro_economic/bls, macro_economic/yield_curves, alternative_data/onchain_btc, alternative_data/defi_metrics, alternative_data/sec_filings"
    relevant_logs="_logs/gamma/stage13_macro_onchain_worker.log; _logs/gamma/stage13_supplemental_worker.log; _logs/gamma/stage13_gamma_validation.md; _logs/supervisor_reports/gamma_status.json"
    relevant_docs="work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md"
    ;;
  *)
    stage_context="Stage 1.3 Free Data Acquisition"
    expected_deliverable="machine-specific Stage 1.3 outputs"
    relevant_logs="_logs/${HOST}; _logs/supervisor_reports/${HOST}_status.json"
    relevant_docs="work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md"
    ;;
esac

cat > "$CONTEXT_PACKET" <<EOF
# Project 3 Tier 1 Context Packet

generated_at: ${NOW}
project_root: ${PROJECT_ROOT}
host: ${HOST}
active_stage: ${stage_context}
agent_role: Hermes/Gemma local Tier 1 supervisor; observe logs/status, detect anomalies, suggest safe next action.
expected_deliverable: ${expected_deliverable}
relevant_docs: ${relevant_docs}
relevant_logs: ${relevant_logs}
constraints: respect /tmp/gpu_busy.lock; do not modify files or dispatch work; do not ask routine questions; report uncertainty.
honesty: tie claims to PID/log/file/GPU evidence; include confidence and assumptions. Never declare a deliverable complete by guessing.
anomaly_detection: stale PID, silent log, no file-count growth, empty outputs, missing provenance, repeated API failures, stale GPU lock, VRAM not released.
deliverable_validation_rule: validation requires the exact work-plan task spec plus deliverable files/provenance/log evidence. If confidence is below 0.8, recommend escalation to Tier 4/Codex instead of guessing.
improvement_suggestion: if a pattern repeats, include a precise skill_candidate for a reusable Hermes skill or validation check.
context_to_pass_forward: preserve active_stage, current_task, deliverable, evidence, anomaly state, confidence, and next recommended action.
EOF

prompt="Project 3 Tier 1 supervisor tick for ${HOST}.
Role: observe logs/status only. Do not modify files or dispatch work.
Context packet path: ${CONTEXT_PACKET}
Read or use that packet as the compact source of stage/task/deliverable/log/context truth. Preserve it in context_to_pass_forward.
GPU summary: ${gpu_summary}
Lock note: ${stale_note:-none}
Auto-improvement: if the same anomaly pattern appears repeatedly, include a skill_candidate field naming the reusable workflow that Tier 2/Tier 3 should turn into a Hermes skill.
Recursive communication rule: include context_to_pass_forward so the next agent receives the exact stage, task, deliverable, evidence, uncertainty, anomaly state, and improvement suggestion.
Deliverable validation rule: never assume; if unsure after reading the work plan and artifacts, set recommended_next_action to escalate_to_codex with the exact question.
Expected output: one concise JSON object with keys status, anomalies, idle_capacity, recommended_next_action, skill_candidate, context_to_pass_forward, confidence."

report="$(timeout 240 "$HERMES_BIN" --skills "$PROJECT3_HERMES_SKILLS" -z "$prompt" 2>&1)"
rc=$?

if [ "$rc" -eq 0 ]; then
  write_status "ok" "$report" "0.85"
else
  write_status "supervisor_error" "$report" "0.35"
fi

ollama stop gemma4:31b >/dev/null 2>&1 || true
