#!/usr/bin/env bash
set -u

ROOT="${ROOT:-/home/harveybc/Documents/GitHub/financial-data}"

echo "# Project 3 Agent Status"
echo
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

echo "## Omega"
echo "- Agent: Hermes/OpenCode Go Tier 2 + Omega Stage 1.3 local worker"
omega_primary="$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER2_HERMES_MODEL=/{print $2; exit}')"
omega_fallbacks="$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER2_HERMES_FALLBACK_MODELS=/{print $2; exit}')"
omega_experiment_until="$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL=/{print $2; exit}')"
omega_tier1_primary="$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER1_HERMES_MODEL=/{print $2; exit}')"
omega_tier1_fallbacks="$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER1_HERMES_FALLBACK_MODELS=/{print $2; exit}')"
echo "- Tier 2 inference policy: primary ${omega_primary:-default Hermes/OpenCode provider}; fallbacks ${omega_fallbacks:-none}; experiment until ${omega_experiment_until:-none}"
echo "- Omega Flash worker lane: primary ${omega_tier1_primary:-not installed}; fallbacks ${omega_tier1_fallbacks:-none}"
echo "- Work-plan stage: Stage 1.3 Free Data Acquisition complete; Stage 1.6 preflight validation/documentation active while Stage 1.4/1.5 subscription decisions remain gated"
echo "- Assigned tasks: completed Stage 1.3 utilities/yfinance/HistData/CFTC/calendars/economic-calendar/metadata/validation/inventory; active Stage 1.6 preflight documentation audit, master inventory, acquisition gap handoff, and status/context refresh"
omega_busy=""
for pid_file in \
  "$ROOT/_logs/omega/stage13_light_sources_python.pid" \
  "$ROOT/_logs/omega/stage13_reference_python.pid" \
  "$ROOT/_logs/omega/stage13_economic_calendar_python.pid" \
  "$ROOT/_logs/omega/stage13_omega_followup_python.pid" \
  "$ROOT/_logs/omega/stage13_housekeeping_python.pid" \
  "$ROOT/_logs/omega/stage16_preflight_omega_python.pid"; do
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && ps -p "$pid" >/dev/null 2>&1; then
    omega_busy="${omega_busy}${pid} "
  fi
done
if [ -n "$omega_busy" ]; then
  echo "- State: busy"
  echo "- Reason: Omega local worker PID(s) $omega_busy are running"
else
  echo "- State: idle or between worker attempts"
  echo "- Reason: no active Omega Python worker PID found"
fi
echo "- Expected/generated deliverables: Stage 1.3 data lake outputs, _metadata/STAGE_1_3_INVENTORY.json, _metadata/STAGE_1_3_DELIVERABLE_VALIDATION.json, STAGE_1.6_PREFLIGHT.md, INVENTORY.md, _metadata/audit_documentation_preflight.json, _metadata/stage16_preflight_omega.json"
echo "- Latest log:"
for log in \
  "$ROOT/_logs/omega/stage13_light_sources_worker.log" \
  "$ROOT/_logs/omega/stage13_reference_worker.log" \
  "$ROOT/_logs/omega/stage13_economic_calendar_worker.log" \
  "$ROOT/_logs/omega/stage13_omega_followup_worker.log" \
  "$ROOT/_logs/omega/stage13_housekeeping_worker.log" \
  "$ROOT/_logs/omega/stage13_doc_backfill_worker.log" \
  "$ROOT/_logs/omega/stage13_validation_inventory_worker.log" \
  "$ROOT/_logs/omega/stage13_deliverable_validator_worker.log" \
  "$ROOT/_logs/omega/stage16_preflight_omega_worker.log"; do
  test -f "$log" && tail -n 3 "$log" | sed 's/^/  /'
done
if [ -f "$ROOT/_logs/supervisor_reports/$(hostname)_status.json" ]; then
  echo "- Omega Flash supervisor latest status:"
  sed 's/^/  /' "$ROOT/_logs/supervisor_reports/$(hostname)_status.json"
fi
echo

remote_status() {
  local label="$1"
  local host="$2"
  local stage="$3"
  local tasks="$4"
  local pid_file="$5"
  local worker_log="$6"
  local deliverable="$7"
  echo "## $label"
  ssh "$host" "pid_files='$pid_file'; worker_logs='$worker_log'; busy=''; model=\$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER1_HERMES_MODEL=/{print \$2; exit}'); fallbacks=\$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER1_HERMES_FALLBACK_MODELS=/{print \$2; exit}'); experiment_until=\$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_DEEPSEEK_PRO_EXPERIMENT_UNTIL=/{print \$2; exit}'); model=\${model:-local default}; gpu=\$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 || true); ollama_resident=\$(ollama ps 2>/dev/null | awk 'NR>1{print \$1}' | paste -sd, -); for pf in \$pid_files; do pid=\$(cat \"\$pf\" 2>/dev/null || true); if [ -n \"\$pid\" ] && ps -p \"\$pid\" >/dev/null 2>&1; then busy=\"\$busy \$pid\"; fi; done; echo \"- Agent: Hermes/DeepSeek supervisor + Stage 1.3 worker\"; echo \"- Inference policy: primary \$model; fallbacks \${fallbacks:-none}; experiment until \${experiment_until:-none}\"; echo \"- GPU memory used: \${gpu:-unknown} MiB\"; echo \"- Ollama resident models: \${ollama_resident:-none}\"; echo \"- Work-plan stage: $stage\"; echo \"- Assigned tasks: $tasks\"; if [ -n \"\$busy\" ]; then echo \"- State: busy\"; echo \"- Reason: worker PID(s)\$busy are running\"; else echo \"- State: idle or completed current slice\"; echo \"- Reason: no active worker PID found\"; fi; echo \"- Expected/generated deliverables: $deliverable\"; echo \"- Latest log:\"; for log in \$worker_logs; do test -f \"\$log\" && tail -n 3 \"\$log\" | sed 's/^/  /'; done" 2>&1
  echo
}

remote_status \
  "Dragon" \
  "dragon" \
  "Stage 1.3 Free Data Acquisition complete; Stage 1.6 preflight validation of market_data active" \
  "completed Binance crypto and FINRA follow-up; active/prepared market_data validation profile" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage13_crypto_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage13_crypto_quality_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage16_preflight_validation_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage16_quality_python.pid" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage13_crypto_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage13_dragon_quality_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage16_preflight_validation_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage16_quality_worker.log" \
  "market_data/crypto/spot_top50, market_data/crypto/perpetuals, market_data/crypto/funding_rates, _logs/dragon/stage13_crypto_quality_report.md, _metadata/stage16_preflight_validation_dragon.json, _metadata/stage16_quality_validation_dragon.json"

remote_status \
  "Gamma" \
  "gamma" \
  "Stage 1.3 Free Data Acquisition complete; Stage 1.6 preflight validation of macro/alternative/reference/calendar active" \
  "completed FRED/CoinMetrics/SEC/BEA/OECD/BLS/Treasury/Etherscan/free-source follow-up; active/prepared macro/alternative/reference/calendar validation profile" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_macro_onchain_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_supplemental_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_remaining_free_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_gamma_followup_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_crypto_perp_accelerator_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage16_preflight_validation_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage16_quality_python.pid" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_macro_onchain_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_supplemental_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_remaining_free_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_gamma_followup_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_crypto_perp_accelerator_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage16_preflight_validation_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage16_quality_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage16_finra_regsho_dedup_worker.log" \
  "macro_economic/fred expansion, alternative_data/onchain_*/coinmetrics_community, alternative_data/sec_filings/edgar_sp500_metadata, macro_economic/oecd, defi_metrics, short_interest outputs, market_data/crypto/perpetuals, funding_rates, _metadata/stage16_preflight_validation_gamma.json, _metadata/stage16_quality_validation_gamma.json, _metadata/stage16_gamma_quality_warning_classification.json"
