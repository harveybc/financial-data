#!/usr/bin/env bash
set -u

ROOT="${ROOT:-/home/harveybc/Documents/GitHub/financial-data}"

echo "# Project 3 Agent Status"
echo
echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

echo "## Omega"
echo "- Agent: Hermes/OpenCode Go Tier 2 + Omega Stage 1.3 local worker"
echo "- Work-plan stage: Stage 1.3 Free Data Acquisition"
echo "- Assigned tasks: Task 1.3.A shared utilities, 1.3.C/1.3.D yfinance, 1.3.E HistData processing from /home/harveybc/Downloads/histdata, CFTC/calendars/metadata aggregation, 1.3.P economic calendar, documentation backfill, deliverable validation against the work plan, repeating Stage 1.3 inventory/context refresh"
omega_busy=""
for pid_file in \
  "$ROOT/_logs/omega/stage13_light_sources_python.pid" \
  "$ROOT/_logs/omega/stage13_reference_python.pid" \
  "$ROOT/_logs/omega/stage13_economic_calendar_python.pid" \
  "$ROOT/_logs/omega/stage13_housekeeping_python.pid"; do
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
echo "- Expected/generated deliverables: shared _scripts utilities, market_data/equities, market_data/commodities, market_data/forex/g10, economic_calendar/release_actuals, reference outputs, acquisition_log rows, missing-doc backfills, _metadata/STAGE_1_3_INVENTORY.json, _metadata/STAGE_1_3_DELIVERABLE_VALIDATION.json, stage13_validation_inventory.md, stage13_deliverable_validation.md"
echo "- Latest log:"
for log in \
  "$ROOT/_logs/omega/stage13_light_sources_worker.log" \
  "$ROOT/_logs/omega/stage13_reference_worker.log" \
  "$ROOT/_logs/omega/stage13_economic_calendar_worker.log" \
  "$ROOT/_logs/omega/stage13_housekeeping_worker.log" \
  "$ROOT/_logs/omega/stage13_doc_backfill_worker.log" \
  "$ROOT/_logs/omega/stage13_validation_inventory_worker.log" \
  "$ROOT/_logs/omega/stage13_deliverable_validator_worker.log"; do
  test -f "$log" && tail -n 3 "$log" | sed 's/^/  /'
done
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
  ssh "$host" "pid_files='$pid_file'; worker_logs='$worker_log'; busy=''; model=\$(crontab -l 2>/dev/null | awk -F= '/^PROJECT3_TIER1_HERMES_MODEL=/{print \$2; exit}'); model=\${model:-local default}; gpu=\$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 || true); ollama_resident=\$(ollama ps 2>/dev/null | awk 'NR>1{print \$1}' | paste -sd, -); for pf in \$pid_files; do pid=\$(cat \"\$pf\" 2>/dev/null || true); if [ -n \"\$pid\" ] && ps -p \"\$pid\" >/dev/null 2>&1; then busy=\"\$busy \$pid\"; fi; done; echo \"- Agent: Hermes/Gemma supervisor + Stage 1.3 worker\"; echo \"- Inference model: \$model\"; echo \"- GPU memory used: \${gpu:-unknown} MiB\"; echo \"- Ollama resident models: \${ollama_resident:-none}\"; echo \"- Work-plan stage: $stage\"; echo \"- Assigned tasks: $tasks\"; if [ -n \"\$busy\" ]; then echo \"- State: busy\"; echo \"- Reason: worker PID(s)\$busy are running\"; else echo \"- State: idle or completed current slice\"; echo \"- Reason: no active worker PID found\"; fi; echo \"- Expected/generated deliverables: $deliverable\"; echo \"- Latest log:\"; for log in \$worker_logs; do test -f \"\$log\" && tail -n 3 \"\$log\" | sed 's/^/  /'; done" 2>&1
  echo
}

remote_status \
  "Dragon" \
  "dragon" \
  "Stage 1.3 Free Data Acquisition, Task 1.3.F Binance crypto comprehensive" \
  "Binance top 50 spot OHLCV, top 10 perpetual OHLCV, funding rates" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage13_crypto_python.pid" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/dragon/stage13_crypto_worker.log" \
  "market_data/crypto/spot_top50, market_data/crypto/perpetuals, market_data/crypto/funding_rates"

remote_status \
  "Gamma" \
  "gamma" \
  "Stage 1.3 Free Data Acquisition, Tasks 1.3.B/1.3.G plus Gamma macro/on-chain, remaining free-source follow-up, and Binance crypto acceleration" \
  "FRED, CoinMetrics Community, Blockchain.com, mempool.space, SEC EDGAR metadata, FINRA, DeFiLlama, Etherscan, OECD/BLS/BEA/Treasury where available, Binance perpetual/funding acceleration" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_macro_onchain_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_supplemental_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_remaining_free_python.pid /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_crypto_perp_accelerator_python.pid" \
  "/home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_macro_onchain_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_supplemental_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_remaining_free_worker.log /home/harveybc/Documents/GitHub/financial-data/_logs/gamma/stage13_crypto_perp_accelerator_worker.log" \
  "macro_economic/fred, macro_economic/oecd, alternative_data/onchain_* / defi_metrics / short_interest outputs, market_data/crypto/perpetuals, market_data/crypto/funding_rates plus source-specific docs"
