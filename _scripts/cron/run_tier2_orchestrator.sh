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
PROJECT3_HERMES_SKILLS="${PROJECT3_HERMES_SKILLS:-project3-autonomous-supervisor,project3-stage31-autonomous-worker,project3-realtime-telegram-orchestration,project3-deliverable-validator,systematic-debugging,subagent-driven-development,hermes-agent-skill-authoring}"
PROJECT3_ENABLE_LEGACY_STAGE1_CRON="${PROJECT3_ENABLE_LEGACY_STAGE1_CRON:-0}"
PROJECT3_TIER2_HERMES_MODEL="${PROJECT3_TIER2_HERMES_MODEL:-}"
PROJECT3_TIER2_HERMES_FALLBACK_MODELS="${PROJECT3_TIER2_HERMES_FALLBACK_MODELS:-}"
PROJECT3_TIER2_MODEL_TIMEOUT_SECONDS="${PROJECT3_TIER2_MODEL_TIMEOUT_SECONDS:-240}"
PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL="${PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL:-}"
RUN_LOCK="$LOG_DIR/tier2_orchestrator.lock"
MODEL_CANDIDATES=()

model_allowed_now() {
  local model="$1"
  local now_s until_s
  case "$model" in
    *deepseek-v4-pro*) ;;
    *) return 0 ;;
  esac
  [ -n "$PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL" ] || return 0
  now_s="$(date -u +%s)"
  until_s="$(date -u -d "$PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL" +%s 2>/dev/null || echo "")"
  [ -z "$until_s" ] && return 0
  [ "$now_s" -le "$until_s" ]
}

add_model_candidate() {
  local model="$1"
  local existing
  model="${model#"${model%%[![:space:]]*}"}"
  model="${model%"${model##*[![:space:]]}"}"
  [ -n "$model" ] || return 0
  model_allowed_now "$model" || return 0
  for existing in "${MODEL_CANDIDATES[@]}"; do
    [ "$existing" = "$model" ] && return 0
  done
  MODEL_CANDIDATES+=("$model")
}

add_model_list() {
  local raw="$1"
  local part
  IFS=',' read -r -a parts <<< "$raw"
  for part in "${parts[@]}"; do
    add_model_candidate "$part"
  done
}

add_model_list "$PROJECT3_TIER2_HERMES_MODEL"
add_model_list "$PROJECT3_TIER2_HERMES_FALLBACK_MODELS"

if [ "${#MODEL_CANDIDATES[@]}" -gt 0 ]; then
  MODEL_POLICY="$(IFS=','; echo "${MODEL_CANDIDATES[*]}")"
else
  MODEL_POLICY="default Hermes/OpenCode provider"
fi

mkdir -p "$LOG_DIR/tier4_handoffs"

if ! mkdir "$RUN_LOCK" 2>/dev/null; then
  if find "$RUN_LOCK" -mmin +20 -print -quit 2>/dev/null | grep -q .; then
    rm -rf "$RUN_LOCK"
    mkdir "$RUN_LOCK" 2>/dev/null || {
      echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) tier2_orchestrator skipped: previous lock still active"
      exit 0
    }
  else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) tier2_orchestrator skipped: previous tick still running"
    exit 0
  fi
fi
trap 'rm -rf "$RUN_LOCK"' EXIT

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
active_stage: Stage 3.1 Stage A screening active; Stage 3.2 Stage A synthesis allowed on Omega CPU when Stage 3.1 local queue is complete; Stage 2 SOTA low-cost enrichment and governance additions are active validation context.
agent_role: Omega Tier 2 OpenCode/Hermes supervisor coordinating Omega, Dragon, Gamma, and the Project 3 event daemon.
supervisor_model_policy: ${MODEL_POLICY}
experiment_until: ${PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL:-none}
tier2_model_timeout_seconds: ${PROJECT3_TIER2_MODEL_TIMEOUT_SECONDS}
relevant_docs: work_plan/00_PROJECT_3_MASTER_PLAN.md; work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/20_PHASE_2_OVERVIEW.md; work_plan/24_STAGE_2_4_LEARNED_REPRESENTATIONS.md; work_plan/30_PHASE_3_OVERVIEW.md; work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md; work_plan/SOTA_IMPROVEMENT_SUGGESTIONS.md; work_plan/SOTA_INTEGRATION_DECISIONS.md; work_plan/STAGE_1_3_AGENT_NOTIFICATION_AND_VOICE.md
current_machine_tasks:
- Omega: Stage 3.1 watchdog/service owner, run ledger aggregation, Stage 3.2 Stage A synthesis on CPU when local Stage 3.1 queue is complete, remote output sync, and SOTA governance integration.
- Dragon: Stage 3.1 GPU Stage A screening jobs from experiments/stage_a_screening/queues/dragon.json; sync summaries and ledger events back to Omega; report blockers/anomalies via Telegram and event logs.
- Gamma: Stage 3.1 GPU Stage A screening jobs from experiments/stage_a_screening/queues/gamma.json; sync summaries and ledger events back to Omega; report blockers/anomalies via Telegram and event logs.
expected_deliverables: experiments/stage_a_screening/runs/<machine>/*/summary.json, experiments/stage_a_screening/index.csv, experiments/stage_a_screening/stage_a_summary.md, artifacts/run_ledger.parquet, artifacts/run_ledger_summary.json, _logs/supervisor_reports/stage31_watchdog.md, _logs/supervisor_reports/stage31_worker_context_packet.md.
relevant_logs: _logs/supervisor_reports/stage31_watchdog.md; _logs/supervisor_reports/stage31_worker_context_packet.md; _logs/supervisor_reports/stage31_supervisor_tick.md; _logs/supervisor_reports/stage31_worker_<machine>.md; _logs/supervisor_reports/global_status.md; _logs/supervisor_reports/project3_event_daemon_events.jsonl.
constraints: use existing private repo runtime credentials; respect GPU locks; avoid destructive cleanup; sync remote outputs to Omega; escalate only real blockers.
honesty: report evidence, confidence, assumptions, and stale context corrections. Never mark a deliverable complete from memory or guesswork.
anomaly_detection: stale PIDs, silent logs, failed APIs, missing provenance, abnormal file counts, empty data files, duplicate timestamps, timezone/frequency drift, stale locks, VRAM not released.
improvement_suggestion: every tick should preserve one useful reusable-skill or validation-check suggestion when evidence supports it.
recursive_context_rule: every agent communication must include project_root, active_stage, current_task, expected_deliverable, relevant_docs, relevant_logs, constraints, evidence, anomalies, confidence, and context_to_pass_forward.
telegram_event_bus_rule: Telegram is for concise task events only: start, finish, blocker, validation anomaly, idle-with-reason, escalation question, human action needed. Never paste long logs; include deliverable paths and evidence. Omega owns the only bidirectional gateway; remote workers use outbound notification only. Agents must not chatter, debate, or stream routine logs in the group.
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
gamma_status="$(probe_machine gamma 192.0.2.16)"
omega_status="$("$HERMES_BIN" status 2>&1 | sed -n '1,35p')"
omega_curator="$("$HERMES_BIN" curator status 2>&1 | sed -n '1,16p'; test -f /home/harveybc/.hermes/skills/data-science/project3-autonomous-supervisor/SKILL.md && echo PROJECT3_SKILL_INSTALLED)"
dragon_curator="$(probe_curator dragon 192.0.2.13)"
gamma_curator="$(probe_curator gamma 192.0.2.16)"
if [ "$PROJECT3_ENABLE_LEGACY_STAGE1_CRON" = "1" ]; then
  dispatch_output="$(PYTHONDONTWRITEBYTECODE=1 python "$PROJECT_ROOT/_scripts/workers/stage13_autonomous_orchestrator.py" 2>&1)"
  dispatch_rc=$?
  stage16_dispatch_output="$(PYTHONDONTWRITEBYTECODE=1 python "$PROJECT_ROOT/_scripts/workers/stage16_preflight_orchestrator.py" 2>&1)"
  stage16_dispatch_rc=$?
else
  dispatch_output="Legacy Stage 1.3 autonomous dispatch is disabled by default. Project 3 event daemon owns active Stage 2.4 low-latency dispatch; set PROJECT3_ENABLE_LEGACY_STAGE1_CRON=1 only for an explicit Stage 1 repair pass."
  dispatch_rc=0
  stage16_dispatch_output="Legacy Stage 1.6 preflight dispatch is disabled by default while Stage 2.4/Phase 3.1 are active. Existing Stage 1.6 reports remain available for audit."
  stage16_dispatch_rc=0
fi

{
  echo "# Project 3 Global Status"
  echo
  echo "Generated: ${NOW}"
  echo
  echo "## Dispatch Decision"
  echo
  echo "Primary low-latency dispatch is handled by \`project3-event-daemon.service\`. This cron tick is now a backup heartbeat and Hermes reasoning/checkpoint lane."
  echo
  echo "Tier 2 should assign work to idle machines as follows:"
  echo
  echo "- Omega: event daemon, sync, local Stage 2.4 GPU jobs when idle, metadata/reporting, Phase 3.1 design readiness, and SOTA integration validation."
  echo "- Dragon: Stage 2.4 learned representation GPU jobs for ready slices, then sync to Omega."
  echo "- Gamma: Stage 2.4 learned representation GPU jobs plus learned-input prep acceleration, then sync to Omega."
  echo "- Stage 1 acquisition/preflight: complete enough for Phase 2/3 progression; legacy repair dispatch is disabled unless explicitly re-enabled."
  echo "- Telegram: post only concise events to HermesAgentOrchestration: task start/finish, blocker, anomaly, idle reason, deliverable path, validation evidence, next action, or human action needed."
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
  echo "## Stage 1.5 Paid Provider Status"
  echo
  if [ -f "$LOG_DIR/stage15_paid_credential_check.md" ]; then
    sed -n '1,80p' "$LOG_DIR/stage15_paid_credential_check.md"
  else
    echo "Stage 1.5 credential check has not been written yet."
  fi
  echo
  if [ -f "$LOG_DIR/stage15_fxmacrodata_acquisition.md" ]; then
    sed -n '1,120p' "$LOG_DIR/stage15_fxmacrodata_acquisition.md"
  else
    echo "Stage 1.5 FXMacroData acquisition summary has not been written yet."
  fi
  echo
  if [ -f "$LOG_DIR/stage15_cryptoquant_acquisition.md" ]; then
    sed -n '1,120p' "$LOG_DIR/stage15_cryptoquant_acquisition.md"
  else
    echo "Stage 1.5 CryptoQuant acquisition summary has not been written yet."
  fi
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
  echo "Policy: event daemon detects idle machines every 45 seconds, starts pending safe and non-overlapping Stage 2.4 workers, syncs completed remote outputs back to Omega, and emits concise Telegram events. Cron remains a 12-minute model-reasoning heartbeat."
  echo
  if [ -f "$LOG_DIR/project3_event_daemon_status.md" ]; then
    sed -n '1,120p' "$LOG_DIR/project3_event_daemon_status.md"
  else
    echo "Project 3 event daemon status has not been written yet."
  fi
  echo
  echo "## Legacy Stage 1 Dispatch"
  echo
  echo "$dispatch_output"
  echo
  if [ "$PROJECT3_ENABLE_LEGACY_STAGE1_CRON" != "1" ]; then
    echo "No Stage 1 report is appended because the legacy dispatcher did not run."
  elif [ "$dispatch_rc" -eq 0 ]; then
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
  echo "## Stage 1.6 Preflight Dispatch"
  echo
  echo "Policy: legacy Stage 1.6 dispatcher is disabled by default while Stage 2.4/Phase 3.1 are active; re-enable only for an explicit repair pass."
  echo
  echo "$stage16_dispatch_output"
  echo
  if [ "$PROJECT3_ENABLE_LEGACY_STAGE1_CRON" != "1" ]; then
    echo "No Stage 1.6 report is appended because the legacy dispatcher did not run."
  elif [ "$stage16_dispatch_rc" -eq 0 ]; then
    if [ -f "$LOG_DIR/stage16_preflight_dispatch.md" ]; then
      sed -n '1,120p' "$LOG_DIR/stage16_preflight_dispatch.md"
    else
      echo "Stage 1.6 preflight dispatcher completed but did not write a markdown report."
    fi
  else
    echo "Stage 1.6 preflight dispatcher failed; stderr/stdout follows:"
    echo '```'
    echo "$stage16_dispatch_output"
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
Machines are reachable, Stage 1 acquisition/preflight is complete enough for Phase 2/3 progression, Stage 2.4 learned representations are active, and the Project 3 event daemon owns low-latency idle-machine dispatch. Do not ask the human routine questions.
Be honest and autocritical: mention stale context or uncertainty if present.
Reply with one concise next-action sentence for the human coordinator focused on autonomous dispatch, idle capacity, anomaly detection, sync, or reusable improvement."
run_hermes_summary() {
  local model attempt attempt_rc failures
  local base_args=(--skills "$PROJECT3_HERMES_SKILLS")
  if [ "${#MODEL_CANDIDATES[@]}" -eq 0 ]; then
    timeout "$PROJECT3_TIER2_MODEL_TIMEOUT_SECONDS" "$HERMES_BIN" "${base_args[@]}" -z "$summary_prompt"
    return $?
  fi

  failures=""
  for model in "${MODEL_CANDIDATES[@]}"; do
    attempt="$(timeout "$PROJECT3_TIER2_MODEL_TIMEOUT_SECONDS" "$HERMES_BIN" "${base_args[@]}" --model "$model" -z "$summary_prompt" 2>&1)"
    attempt_rc=$?
    if [ "$attempt_rc" -eq 0 ]; then
      echo "selected_model=${model}"
      echo "$attempt"
      return 0
    fi
    failures="${failures}"$'\n'"--- model=${model} rc=${attempt_rc} ---"$'\n'"${attempt}"$'\n'
  done
  echo "All configured Tier 2 model attempts failed:${failures}"
  return 1
}
{
  echo
  echo "## Hermes Tier 2 Note"
  echo
  echo "Model policy: ${MODEL_POLICY}"
  echo "Per-model timeout seconds: ${PROJECT3_TIER2_MODEL_TIMEOUT_SECONDS}"
  if run_hermes_summary; then
    true
  else
    echo "Hermes note timed out or failed; deterministic status above remains authoritative."
  fi
} >> "$GLOBAL_STATUS"

PYTHONDONTWRITEBYTECODE=1 python "$PROJECT_ROOT/_scripts/telegram_notify.py" \
  --event "tier2:global_status" \
  --title "Project 3 Tier 2 global status" \
  --status-file "$GLOBAL_STATUS" \
  --min-interval-minutes 20 >/dev/null 2>&1 || true
