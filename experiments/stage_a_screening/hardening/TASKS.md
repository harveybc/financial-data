# Promotion Hardening — Task Ledger

Generated: 2026-05-03T06:19:08.777361+00:00

## COMPLETED checks (this worker)

- [x] load_stage_a_index() — loaded 356 runs from index.csv
- [x] load_run_ledger() — loaded events from artifacts/run_ledger.jsonl
- [x] verify_ledger_membership() — per run, by (asset, tf, algo, preset, seed)
- [x] validate_required_metadata() — asset, timeframe, algo, preset, seed, machine
- [x] compute_cost_proxy() — optimistic, base, pessimistic scenarios
- [x] find_matched_baselines() — same (asset, tf, algo, seed), preset=baseline_12
- [x] compute_paired_uplift() — Δ return, Δ Sharpe, Δ drawdown vs baseline_12
- [x] compute_group_statistics() — by preset, asset, algo (mean/median/std/min/max)
- [x] compute_seed_dispersion() — for all (asset, tf, algo, preset) with ≥2 seeds
- [x] compute_bootstrap_ci() — 95% bootstrap CI for total_return by preset (n_boot=2000)
- [x] compute_dsr_placeholder_or_approximation() — directional approximation, caveat-flagged
- [x] compute_pbo_placeholder() — not_enough_structure documented
- [x] classify_candidate() — deterministic KILL_* / PROMOTE_BLOCKED_HARDENING
- [x] write_reports() — SPEC.md, PLAN.md, TASKS.md, .csv, .md, .json

## KILLED runs

- 355 runs killed at KILL gate (no_trades, non_positive_return, negative_sharpe, ledger_missing, invalid_metrics)
- 1 run(s) survive KILLs but blocked by governance

## SKIPPED checks (require external evidence — not implementable from summary.json)

- [ ] B1: Leakage audit — requires timestamp inspection of train.csv and fitted-transform metadata
- [ ] B2: Availability/vintage contract — requires features/AVAILABILITY_CONTRACT.md per preset
- [ ] B3: Rigorous DSR — requires per-bar annualized return series with skewness/kurtosis
- [ ] B4: PBO/CSCV — requires multi-fold split structure (deferred to Stage B)
- [ ] B8: Simple baselines — requires running no-trade, B&H, random, momentum, reversal strategies
- [ ] B9: Feature-family ablation — requires matched runs with one family removed per config
- [ ] B10: Heldout firewall — requires timestamp audit of inputs/{asset}/{tf}/{preset}/train.csv

## BLOCKERS for Stage B (summary)

All 1 surviving run(s) carry these unresolved blockers:

1. **B1 LEAKAGE**: Complete leakage_audit.md checks (transform windows, scaler windows, heldout exclusion)
2. **B2 AVAILABILITY**: Verify availability/vintage contracts for cross-source presets
3. **B3 DSR**: Compute rigorous Deflated Sharpe Ratio with annualized return series
4. **B4 PBO**: Implement PBO/CSCV at Stage B with purged k-fold validation
5. **B8 BASELINES**: Run simple baseline comparisons (no-trade, B&H, random, momentum, reversal)
6. **B9 ABLATION**: Run feature-family ablation (one family removed per matched pair)
7. **B10 HELDOUT**: Audit train.csv timestamps to confirm no 2025 rows

## NEXT implementation tasks (priority order)

1. **Implement B1 leakage audit worker** (`stage31_leakage_audit_worker.py`):
   - Read train.csv timestamp columns for each run's input file
   - Verify max(timestamp) < 2025-01-01T00:00:00Z
   - Inspect fitted-transform metadata files for window violations
   - Output: experiments/design/leakage_audit_results.json

2. **Implement B8 simple baseline worker** (`stage31_simple_baseline_worker.py`):
   - Run no-trade (cash) return = 0 for each run period
   - Run buy-and-hold return from input CSV first/last close
   - Run random policy (turnover-matched) 100x Monte Carlo → CI
   - Run simple momentum (past-N-bar return sign) strategy
   - Output: experiments/stage_a_screening/baseline_comparisons.csv

3. **Implement B9 family ablation worker** (`stage31_family_ablation_worker.py`):
   - For each surviving config, identify matched runs with one family removed
   - Compute paired marginal contribution per family
   - Output: experiments/design/family_ablation_results.csv

4. **Verify B10 heldout firewall** (can be added to leakage audit worker):
   - Read each input CSV, check max(date) < 2025-01-01
   - Flag any train.csv with post-cutoff rows as KILL_LEAKAGE

5. **At Stage B**: implement B3 (rigorous DSR) and B4 (PBO/CSCV) with longer run artifacts.

6. **At Stage B**: implement B2 (availability contract) for any cross-source promoted config.
