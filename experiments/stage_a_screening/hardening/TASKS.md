# Promotion Hardening — Task Ledger

Generated: 2026-06-02T09:51:49.218094+00:00

## COMPLETED checks (this worker)

- [x] load_stage_a_index() — loaded 5663 runs from index.csv
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
- [x] consume B1/B10 leakage-heldout evidence — loaded leakage_heldout_audit.csv when present
- [x] consume B8 simple-baseline evidence — loaded simple_baseline_report.json when present
- [x] consume B9 family-ablation evidence — loaded family_ablation_report.json when present
- [x] classify_candidate() — deterministic KILL_* / PROMOTE_BLOCKED_HARDENING
- [x] write_reports() — SPEC.md, PLAN.md, TASKS.md, .csv, .md, .json

## KILLED runs

- 5576 runs killed at KILL gate (no_trades, non_positive_return, negative_sharpe, ledger_missing, invalid_metrics)
- 87 run(s) survive KILLs but blocked by governance

## Evidence now wired into this gate

- [x] B1: Leakage/heldout evidence consumed from `leakage_heldout_audit.csv`
- [x] B8: Simple baseline evidence consumed from `simple_baseline_report.json`
- [x] B9: Feature-family ablation evidence consumed from `family_ablation_report.json`
- [x] B10: Heldout firewall evidence consumed from `leakage_heldout_audit.csv`
- [ ] B2: Availability/vintage contract — requires features/AVAILABILITY_CONTRACT.md per preset
- [ ] B3: Rigorous DSR — requires per-bar annualized return series with skewness/kurtosis
- [ ] B4: PBO/CSCV — requires multi-fold split structure (deferred to Stage B)

## BLOCKERS for current best surviving run

1. B3_DSR: Deflated Sharpe Ratio not rigorously computed. Requires annualized return series with skewness/kurtosis. Current approximation is directional only and not sufficient for promotion.
2. B4_PBO: PBO/CSCV not feasible with Stage A single-split structure. Deferred to Stage B per multiple_testing_correction.md.

## NEXT implementation tasks (priority order)

1. **At Stage B**: implement B3 rigorous DSR with per-bar annualized return series, skewness, kurtosis, and multiple-testing correction.
2. **At Stage B**: implement B4 PBO/CSCV with purged k-fold or CSCV-compatible split artifacts.
3. **Before any cross-source candidate promotes**: implement B2 availability/vintage contract validation.
4. Keep B1/B8/B9/B10 evidence refreshed as new Stage A/Stage B runs complete.
