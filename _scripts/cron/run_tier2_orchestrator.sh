#!/usr/bin/env bash
set -u

PROJECT_ROOT="${PROJECT_ROOT:-/home/harveybc/Documents/GitHub/financial-data}"
LOG_DIR="$PROJECT_ROOT/_logs/supervisor_reports"
GLOBAL_STATUS="$LOG_DIR/global_status.md"
QUEUE="$LOG_DIR/escalation_queue.json"
CONTEXT_PACKET="$LOG_DIR/tier2_context_packet.md"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
SSH_PREFIX="bash -lc 'source ~/.bashrc >/dev/null 2>&1; source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow >/dev/null 2>&1;"
HERMES_BIN="${HERMES_BIN:-$HOME/.local/bin/hermes}"
PROJECT3_HERMES_SKILLS="${PROJECT3_HERMES_SKILLS:-project3-autonomous-supervisor,project3-deliverable-validator,systematic-debugging,subagent-driven-development,hermes-agent-skill-authoring}"

mkdir -p "$LOG_DIR/tier4_handoffs"

source "$HOME/.bashrc" >/dev/null 2>&1 || true
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
  conda activate tensorflow >/dev/null 2>&1 || true
fi

if [ ! -f "$QUEUE" ]; then
  printf '{\n  "queue": []\n}\n' > "$QUEUE"
fi

cat > "$CONTEXT_PACKET" <<EOF
# Project 3 Tier 2 Context Packet

generated_at: ${NOW}
project_root: ${PROJECT_ROOT}
active_stage: Stage 1.3 Free Data Acquisition
agent_role: Omega Tier 2 OpenCode/Hermes supervisor coordinating Omega, Dragon, and Gamma.
relevant_docs: work_plan/00_PROJECT_3_MASTER_PLAN.md; work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md; work_plan/16_STAGE_1_6_VALIDATION_AND_DOCUMENTATION.md
current_machine_tasks:
- Omega: yfinance, HistData from /home/harveybc/Downloads/histdata, CFTC, calendars, metadata aggregation, documentation backfill, deliverable validation against work-plan specs, validation inventory, dispatch context refresh.
- Dragon: Binance top 50 spot, top 10 perpetuals, funding rates.
- Gamma: FRED, CoinMetrics attempts, Blockchain.com, mempool.space, SEC metadata, DeFiLlama, BLS/Treasury, Etherscan/OECD/FINRA/BEA follow-up, Binance perpetual/funding acceleration.
expected_deliverables: market_data, macro_economic, alternative_data, reference_data, _metadata/acquisition_log.csv, provenance docs, validation inventory.
relevant_logs: _logs/supervisor_reports/global_status.md; _logs/supervisor_reports/autonomous_dispatch_report.md; _logs/omega; remote _logs/dragon; remote _logs/gamma.
constraints: use existing private repo runtime credentials; respect GPU locks; avoid destructive cleanup; sync remote outputs to Omega; escalate only real blockers.
honesty: report evidence, confidence, assumptions, and stale context corrections. Never mark a deliverable complete from memory or guesswork.
anomaly_detection: stale PIDs, silent logs, failed APIs, missing provenance, abnormal file counts, empty data files, duplicate timestamps, timezone/frequency drift, stale locks, VRAM not released.
improvement_suggestion: every tick should preserve one useful reusable-skill or validation-check suggestion when evidence supports it.
recursive_context_rule: every agent communication must include project_root, active_stage, current_task, expected_deliverable, relevant_docs, relevant_logs, constraints, evidence, anomalies, confidence, and context_to_pass_forward.
deliverable_validation_rule: before declaring task completion, read the exact work-plan task spec and inspect produced deliverables, provenance/docs, acquisition log, and worker logs. If confidence is below 0.8 or the requirement is ambiguous, write a Tier 4/Codex escalation instead of guessing.
EOF

probe_machine() {
  local host="$1"
  local ip="$2"
  ssh -o BatchMode=yes -o ConnectTimeout=5 -p 22022 "harveybc@$ip" \
    "${SSH_PREFIX} echo HOST=\$(hostname); echo CONDA=\$CONDA_DEFAULT_ENV; hermes status | sed -n '1,35p'; if test -f /tmp/gpu_busy.lock; then echo GPU_LOCK_PRESENT; cat /tmp/gpu_busy.lock; else echo NO_GPU_LOCK; fi; nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader 2>/dev/null || true;'" \
    2>&1 | sed "s/^/[${host}] /"
}

probe_curator() {
  local host="$1"
  local ip="$2"
  ssh -o BatchMode=yes -o ConnectTimeout=5 -p 22022 "harveybc@$ip" \
    "${SSH_PREFIX} hermes curator status | sed -n '1,16p'; test -f /home/harveybc/.hermes/skills/data-science/project3-autonomous-supervisor/SKILL.md && echo PROJECT3_SKILL_INSTALLED;'" \
    2>&1 | sed "s/^/[${host}] /"
}

dragon_status="$(probe_machine dragon 192.0.2.13)"
gamma_status="$(probe_machine gamma 192.0.2.15)"
omega_status="$("$HERMES_BIN" status 2>&1 | sed -n '1,35p')"
omega_curator="$("$HERMES_BIN" curator status 2>&1 | sed -n '1,16p'; test -f /home/harveybc/.hermes/skills/data-science/project3-autonomous-supervisor/SKILL.md && echo PROJECT3_SKILL_INSTALLED)"
dragon_curator="$(probe_curator dragon 192.0.2.13)"
gamma_curator="$(probe_curator gamma 192.0.2.15)"
dispatch_output="$(PYTHONDONTWRITEBYTECODE=1 python "$PROJECT_ROOT/_scripts/workers/stage13_autonomous_orchestrator.py" 2>&1)"
dispatch_rc=$?

{
  echo "# Project 3 Global Status"
  echo
  echo "Generated: ${NOW}"
  echo
  echo "## Dispatch Decision"
  echo
  echo "Acquisition dispatch is enabled. Runtime credentials are loaded from ${PROJECT_ROOT}/_metadata/.env, generated from the existing private companion file per user direction."
  echo
  echo "Tier 2 should assign work to idle machines as follows:"
  echo
  echo "- Dragon: Binance top 50 spot OHLCV, then skip any perpetual/funding outputs already synced from Gamma."
  echo "- Gamma: FRED, CoinMetrics, Blockchain.com, mempool.space, SEC EDGAR metadata, FINRA, DeFiLlama, OECD/BLS/BEA/Treasury, plus Binance perpetual/funding acceleration while idle."
  echo "- Omega: yfinance, HistData processing from /home/harveybc/Downloads/histdata, CFTC, calendars, metadata aggregation, documentation backfill, deliverable validation against the work plan, inventory, and dispatch context refresh."
  echo "- Sync: Gamma crypto acceleration syncs to Dragon first, then all completed remote outputs sync back to Omega as canonical root."
  echo
  echo "Tier 2 must avoid GPU-heavy dispatch when /tmp/gpu_busy.lock exists or VRAM is already occupied."
  echo
  echo "## Recursive Context Communication"
  echo
  echo "Every Project 3 agent communication must include a compact context packet with stage, task, deliverable, relevant docs/logs, constraints, evidence, anomalies, confidence, improvement suggestion, and context_to_pass_forward."
  echo
  echo "Deliverable validation rule: read the exact work-plan task spec and inspect the produced artifact before marking complete. If the supervisor is not at least 0.8 confident, escalate to Tier 4/Codex instead of guessing."
  echo
  sed -n '1,120p' "$CONTEXT_PACKET"
  echo
  echo "## Hermes Auto-Improvement"
  echo
  echo "Project-specific skill preload: ${PROJECT3_HERMES_SKILLS}"
  echo
  echo "### Omega"
  echo '```'
  echo "$omega_curator"
  echo '```'
  echo
  echo "### Dragon"
  echo '```'
  echo "$dragon_curator"
  echo '```'
  echo
  echo "### Gamma"
  echo '```'
  echo "$gamma_curator"
  echo '```'
  echo
  echo "## Autonomous Dispatch"
  echo
  echo "Policy: detect idle machines every Tier 2 cron tick, keep active workers running, start pending safe and non-overlapping Stage 1.3 workers without human intervention, use Omega housekeeping for docs/inventory/deliverable validation, and sync completed remote outputs back to Omega."
  echo
  if [ "$dispatch_rc" -eq 0 ]; then
    if [ -f "$LOG_DIR/autonomous_dispatch_report.md" ]; then
      sed -n '1,120p' "$LOG_DIR/autonomous_dispatch_report.md"
    else
      echo "Dispatcher completed but did not write a markdown report."
    fi
  else
    echo "Dispatcher failed; stderr/stdout follows:"
    echo '```'
    echo "$dispatch_output"
    echo '```'
  fi
  echo
  echo "## Omega"
  echo '```'
  echo "$omega_status"
  echo '```'
  echo
  echo "## Dragon"
  echo '```'
  echo "$dragon_status"
  echo '```'
  echo
  echo "## Gamma"
  echo '```'
  echo "$gamma_status"
  echo '```'
} > "$GLOBAL_STATUS"

summary_prompt="Project 3 Tier 2 tick.
Context packet path: ${CONTEXT_PACKET}
Use that packet as the compact source of stage/task/deliverable/log/context truth and preserve context_to_pass_forward in future agent communications.
Machines are reachable, credentials are available from the private repo runtime environment, and Stage 1.3 acquisition is active. Do not ask the human to rotate keys.
Be honest and autocritical: mention stale context or uncertainty if present.
Reply with one concise next-action sentence for the human coordinator focused on autonomous dispatch, idle capacity, anomaly detection, sync, or reusable improvement."
{
  echo
  echo "## Hermes Tier 2 Note"
  if timeout 60 "$HERMES_BIN" --skills "$PROJECT3_HERMES_SKILLS" -z "$summary_prompt"; then
    true
  else
    echo "Hermes note timed out or failed; deterministic status above remains authoritative."
  fi
} >> "$GLOBAL_STATUS"
