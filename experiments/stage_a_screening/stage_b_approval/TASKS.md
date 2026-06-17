# Stage B Approval — Required Next Actions

_Generated: 2026-05-14T09:00:44.976534+00:00_

## Blocking Issues (must resolve before any PASS_STAGE_B_READY)

### ABLATION_FAIL
- Feature family does not provide marginal value vs ablation; investigate or drop feature family

### ABLATION_NO_MATCH
- Run matched ablation variant (same asset/timeframe/algo/seed)

### BASELINE_FAIL
- Candidate must outperform all simple baselines under base AND pessimistic cost

### DSR_RIGOROUS_FAIL
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### FAMILY_REALITY_CHECK_FAIL
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### FINAL_ALWAYS_IN_MARKET_LOSING
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### FINAL_EXCESSIVE_TRADES_HARD
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### MISSING_COST_SCENARIO
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### NEGATIVE_SHARPE
- Run is killed by hardening. No promotion path.

### NON_POSITIVE_RETURN
- Run is killed by hardening. No promotion path.

### NO_TRADES
- Investigate reward shaping; do not promote zero-trade runs

### PBO_DEFERRED_OR_FAIL
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### SEED_UNCERTAINTY_BLOCKED
- Inspect stageb_dsr_pbo_report.json, correct missing evidence/configuration, and re-run Stage B evaluator before any Stage C access

### STAGEB_STAT_EVIDENCE_MISSING
- Produce return-trace evidence and re-run stageb_dsr_pbo_evaluator.py

## Summary

- Total candidates: 4933
- BLOCKED_BASELINE_COMPARISON: 4
- BLOCKED_DSR_DEFERRED: 19
- BLOCKED_FAMILY_ABLATION: 8
- BLOCKED_MISSING_EVIDENCE: 13
- KILL_NEGATIVE_SHARPE: 974
- KILL_NON_POSITIVE_RETURN: 2761
- KILL_NO_TRADES: 1154

## Required Stage B Artifacts

1. **Return trace files** — agent-multi must emit `return_trace_file` for each 1M-step run
2. **stageb_dsr_pbo_evaluator.py** — run after Stage B training to compute rigorous DSR and PBO
3. **Purged k-fold splits** — required for CSCV/PBO; implement in Stage B training config

## Do NOT

- Do not mark any candidate `PASS_STAGE_B_READY` until B3/B4 clear via the above artifacts
- Do not treat Stage B diagnostic/statistical runs as promotion evidence until rigorous DSR/PBO reports exist
- Do not inspect or use any data from 2025-01-01 onwards (heldout firewall)
- Do not modify existing Stage A hardening artifacts
