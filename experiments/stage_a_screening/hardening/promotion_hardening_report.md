# Promotion Hardening Report — Stage A → Stage B Gate

Generated: 2026-06-02T09:51:49.197978+00:00

---

## 1. Executive Summary

- **Total Stage A runs evaluated:** 5663
- **Total ledger events/trials:** 61348 events, 7178 distinct trial IDs
- **Killed:** 5576
  - KILL_NEGATIVE_SHARPE: 1281  
  - KILL_NON_POSITIVE_RETURN: 3101  
  - KILL_NO_TRADES: 1194
- **Watchlisted (secondary flags):** 3
- **Blocked from Stage B (governance):** 87
- **Promotable to Stage B now:** 0

> **VERDICT: No candidate can advance to Stage B.** All surviving runs carry unresolved P0 governance blockers (B1–B10). See §7 for the exact blocker list for the current best run.

---

## 2. Classification Breakdown

| Status | Count |
| --- | ---: |
| KILL_NEGATIVE_SHARPE | 1281 |
| KILL_NON_POSITIVE_RETURN | 3101 |
| KILL_NO_TRADES | 1194 |
| PROMOTE_BLOCKED_HARDENING | 87 |

### Watch Flags (secondary, additive)

| Flag | Count |
| --- | ---: |
| WATCH_NEEDS_BASELINE | 3 |

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
| E[max SR | N=7178 trials] | 4.2140 |
| DSR approx | -4.2024 |
| DSR > 0? | False |
| Status | approximate_directional_only |

> APPROXIMATION ONLY. Full DSR requires annualized return series with skewness/kurtosis corrections. This uses a Bonferroni extreme-value correction: E_max = sqrt(2*log(N)) for N independent trials. SR is episode-level, not annualized. Do not use for formal promotion claims.

### 3.5 PBO/CSCV

> PBO/CSCV: not_enough_structure. Stage A uses single-split per run. Deferred to Stage B.

### 3.6 Exact Blockers for Best Run

**Classification:** `PROMOTE_BLOCKED_HARDENING`  
**Watch flags:** ``  
**Blocker count:** 2

1. B3_DSR: Deflated Sharpe Ratio not rigorously computed. Requires annualized return series with skewness/kurtosis. Current approximation is directional only and not sufficient for promotion.
2. B4_PBO: PBO/CSCV not feasible with Stage A single-split structure. Deferred to Stage B per multiple_testing_correction.md.

---

## 4. Seed Dispersion — Best Config (ETH/USDT 4h SAC tech_stat)

- Seeds run: ['0', '0', '1', '1', '2', '2']
- Return mean: -0.0370  std: 0.1458  min: -0.1312  max: 0.1512
- Sharpe mean: -0.0228  std: 0.0266

> High std across seeds indicates policy instability. Only seed 0 shows positive return; other seeds must be examined before promotion.

---

## 5. Group Statistics by Preset

| Preset | Runs | Pos. Return | Return Mean | Return Median | Return Std | Sharpe Mean | DD Mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline_12 | 702 | 165 | -0.0034 | -0.0000 | 0.0270 | -636.0002 | 1.19 |
| crypto_full | 328 | 101 | -0.0131 | -0.0000 | 0.0719 | -1357.3011 | 2.87 |
| fx_full | 310 | 28 | -0.0021 | -0.0000 | 0.0059 | -43.9714 | 0.31 |
| kitchen_sink_guarded | 622 | 145 | -0.0021 | -0.0000 | 0.0230 | -325.6082 | 1.08 |
| learned_cnn | 627 | 156 | -0.0025 | -0.0000 | 0.0289 | -705.7079 | 1.31 |
| learned_lstm | 657 | 163 | -0.0044 | -0.0000 | 0.0330 | -798.8722 | 1.48 |
| sota_low_cost | 336 | 136 | -0.0014 | 0.0000 | 0.0548 | -1057.8367 | 2.79 |
| tech_full | 682 | 142 | -0.0038 | -0.0000 | 0.0502 | -673.1959 | 1.36 |
| tech_stat | 715 | 194 | -0.0034 | -0.0000 | 0.0354 | -598.1020 | 1.45 |
| tech_stat_decomp | 684 | 138 | -0.0081 | -0.0000 | 0.0501 | -735.5763 | 1.59 |

## 6. Bootstrap CI for total_return by Preset

| Preset | N | Mean | 95% CI Lo | 95% CI Hi | Note |
| --- | ---: | ---: | ---: | ---: | --- |
| baseline_12 | 702 | -0.0034 | -0.0053 | -0.0015 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| crypto_full | 328 | -0.0131 | -0.0219 | -0.0065 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| fx_full | 310 | -0.0021 | -0.0028 | -0.0015 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| kitchen_sink_guarded | 622 | -0.0021 | -0.0038 | -0.0003 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| learned_cnn | 627 | -0.0025 | -0.0047 | -0.0003 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| learned_lstm | 657 | -0.0044 | -0.0069 | -0.0020 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| sota_low_cost | 336 | -0.0014 | -0.0074 | 0.0046 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| tech_full | 682 | -0.0038 | -0.0082 | -0.0005 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| tech_stat | 715 | -0.0034 | -0.0059 | -0.0008 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |
| tech_stat_decomp | 684 | -0.0081 | -0.0123 | -0.0049 | 95% bootstrap CI for total_return (2000 resamples, seed=42) |

---

## 7. Governance Gate Status

| Gate | Status |
| --- | --- |
| Immutable ledger | ✓ Checked |
| Leakage audit (B1) | ~ PARTIALLY_CLEARED — 1874 PASS, 1636 PARTIAL, 1418 BLOCKED_INPUT_MISSING |
| Availability contract (B2) | ✗ NOT VERIFIED for cross-source presets |
| DSR rigorous (B3) | ✗ APPROXIMATION ONLY |
| PBO/CSCV (B4) | ✗ DEFERRED to Stage B |
| Paired uplift (B5) | ✓ Computed where baseline exists |
| Seed dispersion (B6) | ✓ Reported |
| Cost sensitivity (B7) | ✓ Proxy computed; exact rerun needed |
| Simple baselines (B8) | ~ PARTIALLY_CLEARED — 72 run(s) PASS, 3427 FAIL (mostly killed), 1418 BLOCKED_NO_INPUT |
| Family ablation (B9) | ~ PARTIALLY_CLEARED — 1163 run(s) PASS, 426 PARTIAL, 2319 FAIL, 167 BLOCKED_NO_MATCH, 612 N/A |
| Heldout firewall (B10) | ~ PARTIALLY_CLEARED — 3510 PASS, 0 FAIL, 1418 BLOCKED_INPUT_MISSING |

**All surviving candidates remain BLOCKED from Stage B promotion until B3/B4 are resolved through Stage B infrastructure.**

---

*End of report. Generated by stage31_promotion_hardening_worker.py at 2026-06-02T09:51:49.200328+00:00*
