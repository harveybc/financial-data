# Promotion Hardening Report — Stage A → Stage B Gate

Generated: 2026-05-03T06:19:08.775073+00:00

---

## 1. Executive Summary

- **Total Stage A runs evaluated:** 356
- **Total ledger events/trials:** 2774 events, 733 distinct trial IDs
- **Killed:** 355
  - KILL_NEGATIVE_SHARPE: 66  
  - KILL_NON_POSITIVE_RETURN: 239  
  - KILL_NO_TRADES: 50
- **Watchlisted (secondary flags):** 0
- **Blocked from Stage B (governance):** 1
- **Promotable to Stage B now:** 0

> **VERDICT: No candidate can advance to Stage B.** All surviving runs carry unresolved P0 governance blockers (B1–B10). See §7 for the exact blocker list for the current best run.

---

## 2. Classification Breakdown

| Status | Count |
| --- | ---: |
| KILL_NEGATIVE_SHARPE | 66 |
| KILL_NON_POSITIVE_RETURN | 239 |
| KILL_NO_TRADES | 50 |
| PROMOTE_BLOCKED_HARDENING | 1 |

### Watch Flags (secondary, additive)

| Flag | Count |
| --- | ---: |

---

## 3. Current Best Run — Exact Governance Report

**Run:** `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave`

### 3.1 Performance Metrics

| Metric | Value |
| --- | --- |
| total_return | 0.1512 |
| sharpe_ratio | 0.0115 |
| max_drawdown_pct | 11.11% |
| trades_total | 426 |
| ledger_ok | True |
| metadata_ok | True |
| n_seeds_run | 3 |

### 3.2 Cost Proxy (net return estimates)

| Scenario | Net Return | Positive? |
| --- | ---: | --- |
| optimistic | 0.1495 | True |
| base       | 0.1360       | True |
| pessimistic| 0.1081 | True |

> Cost proxy assumptions: position_fraction=0.01, sim_fee=2bps/side. Crypto spot base: fee=5, spread=3, slippage=3 bps/side + turnover penalty.

### 3.3 Paired Uplift vs Matched Baseline

| Metric | Baseline | Candidate | Uplift |
| --- | ---: | ---: | ---: |
| total_return | -0.1353 | 0.1512 | **0.2865** |
| sharpe_ratio | -0.0398 | 0.0115 | **0.0514** |

Matched baseline: `ethusdt_4h_sac_baseline_12_direct_atr_sltp_s0_20260502T044025Z_project3_stage31_firstwave`

### 3.4 DSR Approximation

| Field | Value |
| --- | --- |
| SR observed | 0.0115 |
| E[max SR | N=733 trials] | 3.6324 |
| DSR approx | -3.6209 |
| DSR > 0? | False |
| Status | approximate_directional_only |

> APPROXIMATION ONLY. Full DSR requires annualized return series with skewness/kurtosis corrections. This uses a Bonferroni extreme-value correction: E_max = sqrt(2*log(N)) for N independent trials. SR is episode-level, not annualized. Do not use for formal promotion claims.

### 3.5 PBO/CSCV

> PBO/CSCV: not_enough_structure. Stage A uses single-split per run. Deferred to Stage B.

### 3.6 Exact Blockers for Best Run

**Classification:** `PROMOTE_BLOCKED_HARDENING`  
**Watch flags:** ``  
**Blocker count:** 6

1. B1_LEAKAGE_AUDIT: experiments/design/leakage_audit.md checks not executed. Required: heldout_timestamp_exclusion, transform_fit_window_check, scaler_fit_window_check, autoencoder_fit_window_check, hmm_regime_fit_window_check, forward_fill_availability_check, macro_vintage_check.
2. B3_DSR: Deflated Sharpe Ratio not rigorously computed. Requires annualized return series with skewness/kurtosis. Current approximation is directional only and not sufficient for promotion.
3. B4_PBO: PBO/CSCV not feasible with Stage A single-split structure. Deferred to Stage B per multiple_testing_correction.md.
4. B8_SIMPLE_BASELINES: No comparison against no-trade, buy-and-hold, random/turnover-matched random, simple momentum, or simple reversal has been computed. Required before Stage B per §1.3 Stage A deliverable spec.
5. B9_FAMILY_ABLATION: Feature-family marginal contribution not reported. feature_family_ablation_plan.md requires family-level paired attribution before leaderboard-only promotion is accepted.
6. B10_HELDOUT_FIREWALL: Cannot verify 2025 heldout exclusion without inspecting train.csv row timestamps. stage_b_promotion_gate.yaml §stage_c_firewall requires heldout_start=2025-01-01 exclusion audit.

---

## 4. Seed Dispersion — Best Config (ETH/USDT 4h SAC tech_stat)

- Seeds run: ['0', '1', '2']
- Return mean: -0.0370  std: 0.1630  min: -0.1312  max: 0.1512
- Sharpe mean: -0.0228  std: 0.0298

> High std across seeds indicates policy instability. Only seed 0 shows positive return; other seeds must be examined before promotion.

---

## 5. Group Statistics by Preset

| Preset | Runs | Pos. Return | Return Mean | Return Median | Return Std | Sharpe Mean | DD Mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_12 | 72 | 14 | -0.0077 | -0.0001 | 0.0388 | -37.2475 | 1.80 |
| crypto_full | 6 | 0 | -0.0524 | -0.0541 | 0.0465 | -0.1041 | 7.88 |
| fx_full | 2 | 0 | -0.0126 | -0.0126 | 0.0178 | -1.0350 | 1.95 |
| kitchen_sink_guarded | 6 | 3 | -0.0167 | 0.0001 | 0.0414 | -0.8277 | 2.32 |
| learned_cnn | 22 | 3 | -0.0155 | -0.0003 | 0.0337 | -16.7332 | 2.93 |
| learned_lstm | 30 | 3 | -0.0128 | -0.0002 | 0.0274 | -18.9942 | 2.03 |
| sota_low_cost | 10 | 6 | 0.0163 | 0.0020 | 0.0381 | -0.0709 | 4.78 |
| tech_full | 74 | 9 | -0.0061 | -0.0001 | 0.0275 | -40.2631 | 1.50 |
| tech_stat | 77 | 24 | 0.0010 | -0.0000 | 0.0321 | -36.0915 | 1.96 |
| tech_stat_decomp | 57 | 5 | -0.0139 | -0.0001 | 0.0356 | -39.3454 | 2.10 |

## 6. Bootstrap CI for total_return by Preset

| Preset | N | Mean | 95% CI Lo | 95% CI Hi | Note |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline_12 | 72 | -0.0077 | -0.0178 | -0.0001 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| crypto_full | 6 | -0.0524 | -0.0845 | -0.0200 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| fx_full | 2 | -0.0126 | — | — | Too few samples (n=2 < 5); CI not computed |
| kitchen_sink_guarded | 6 | -0.0167 | -0.0507 | 0.0009 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| learned_cnn | 22 | -0.0155 | -0.0296 | -0.0025 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| learned_lstm | 30 | -0.0128 | -0.0232 | -0.0040 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| sota_low_cost | 10 | 0.0163 | -0.0046 | 0.0390 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| tech_full | 74 | -0.0061 | -0.0124 | -0.0005 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| tech_stat | 77 | 0.0010 | -0.0064 | 0.0081 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| tech_stat_decomp | 57 | -0.0139 | -0.0236 | -0.0062 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |

---

## 7. Governance Gate Status

| Gate | Status |
| --- | --- |
| Immutable ledger | ✓ Checked |
| Leakage audit (B1) | ✗ NOT COMPLETED — all runs blocked |
| Availability contract (B2) | ✗ NOT VERIFIED for cross-source presets |
| DSR rigorous (B3) | ✗ APPROXIMATION ONLY |
| PBO/CSCV (B4) | ✗ DEFERRED to Stage B |
| Paired uplift (B5) | ✓ Computed where baseline exists |
| Seed dispersion (B6) | ✓ Reported |
| Cost sensitivity (B7) | ✓ Proxy computed; exact rerun needed |
| Simple baselines (B8) | ✗ NOT COMPUTED |
| Family ablation (B9) | ✗ NOT COMPUTED |
| Heldout firewall (B10) | ✗ NOT AUDITED |

**All candidates remain BLOCKED from Stage B promotion until B1, B8, B9, B10 are cleared**
**and B3/B4 are resolved through Stage B infrastructure.**

---

*End of report. Generated by stage31_promotion_hardening_worker.py at 2026-05-03T06:19:08.775261+00:00*
