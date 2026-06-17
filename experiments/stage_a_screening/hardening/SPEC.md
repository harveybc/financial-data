# Promotion Hardening Evaluator — SPEC

Generated: 2026-06-02T09:51:38.738825+00:00

## Purpose

This evaluator enforces the Stage A → Stage B promotion gate defined in:
- experiments/design/stage_b_promotion_gate.yaml
- experiments/design/leakage_audit.md
- experiments/design/cost_model.md
- experiments/design/multiple_testing_correction.md
- work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md §1.0 (SOTA Hardening Gate)

No run may advance to Stage B until all blockers are cleared.

## Checks Implemented

| Check | Status |
| --- | --- |
| Ledger membership (immutable record) | IMPLEMENTED |
| Required metadata validation (asset, tf, algo, preset, seed, machine) | IMPLEMENTED |
| total_return present and finite | IMPLEMENTED |
| sharpe_ratio present and finite | IMPLEMENTED |
| max_drawdown_pct present and finite | IMPLEMENTED |
| trades_total > 0 (no-trade detection) | IMPLEMENTED |
| Base-cost proxy positive | IMPLEMENTED |
| Pessimistic-cost proxy catastrophic collapse detection | IMPLEMENTED |
| Matched baseline_12 lookup | IMPLEMENTED |
| Paired uplift vs baseline_12 | IMPLEMENTED |
| Seed dispersion (≥ 2 seeds check) | IMPLEMENTED |
| Preset-level group statistics | IMPLEMENTED |
| Bootstrap CI for total_return by preset | IMPLEMENTED |
| DSR approximation (directional, not rigorous) | IMPLEMENTED (caveat-flagged) |
| PBO/CSCV placeholder | IMPLEMENTED (not_enough_structure) |

## Checks NOT Yet Implemented (Require External Evidence)

| Check | Reason | Blocking? |
| --- | --- | --- |
| Leakage audit (train timestamp exclusion, transform fit windows) | Requires inspecting input CSV timestamps and fitted-transform metadata | YES — all runs blocked |
| Availability/vintage contract for cross-source presets | Requires features/AVAILABILITY_CONTRACT.md per preset | YES — cross-source presets blocked |
| Rigorous DSR (annualized, with skewness/kurtosis) | Requires full per-bar return series, not available in summary.json | YES — approximation only |
| PBO/CSCV combinatorial cross-validation | Stage A has single-split; fold structure not available | YES — deferred to Stage B |
| Simple baseline comparisons (B&H, random, momentum) | Requires running baseline strategies on same data/period | YES — all runs blocked |
| Feature-family ablation (marginal contribution) | Requires matched runs with one family removed | YES — all runs blocked |
| 2025 heldout firewall verification | Requires timestamp audit of train.csv files | YES — all runs blocked |
| Regime-sliced performance | Requires regime labels or HMM regime assignments | Deferred to Stage B |
| Reality Check / SPA family tests | Requires family-level block bootstrap | Deferred to Stage B |

## Cost Proxy Model

Simulation environment applied commission=2 bps per side, slippage=0.
Cost proxy adds the delta from simulation to each real-world scenario:

    extra_bps = scenario_fee + spread + slippage - 2 bps (sim)
    cost = trades × max(0, extra_bps × 2) / 10000 × position_fraction (0.01)
    turnover_contribution = |gross| × turnover_penalty × min(1, trades/200)

This is a simplified proxy. Actual costs depend on execution quality, market
impact, holding period, and leverage. Do not treat as exact net performance.

## DSR Approximation Limitations

The DSR approximation uses:
    E[max SR | N] ≈ sqrt(2 × log(N))

Limitations:
1. SR is episode-level (backtesting engine), NOT annualized.
2. Skewness and kurtosis corrections are absent (no return series).
3. N = 672 trials (all ledger trials, not only competing strategies).
4. Trials are correlated (same asset/period), making E_max conservative.
5. Result is directional only — negative DSR_approx is a warning, not proof of overfit.

## PBO Limitation

Stage A uses a single train split. CSCV requires multiple combinatorial folds
of the same strategy on the same data. Implement at Stage B with purged k-fold.
