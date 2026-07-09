# Project3 DOIN Handoff Candidate Pack - 2026-07-05

Snapshot time: 2026-07-05 16:45 COT.

This document records the Sunday-night candidate set for the Monday RTX 5090 /
`doin` transition. It is intentionally a handoff pack, not a new broad
experiment plan.

## Operational Decision

The remaining weekly-pool work is in finish-only mode. Do not start new broad
weekly sweeps before the Monday `doin` transition. The active workers should
finish the bounded ETHUSDT 4h phase7 queue. Deferred work stays deferred unless
the user explicitly reopens Project3 weekly-pool exploration after the `doin`
switch.

The Monday handoff should use:

1. **Primary full-year control**: best near/full-year candidate by annual RAP.
2. **Secondary opportunity seed**: strongest partial bloom candidate, currently
   SOLUSDT 4h.
3. **Portfolio research lane**: rush-week/bloom detection from OLAP weekly
   records, evaluated causally later.

## Primary Full-Year Control

Candidate:

```text
ethusdt_4h_kitchen_sink_guarded_exec_annual_4y_2022val_2023test_rap_sac_annual_fyv2022_fyt2023_scratch_4y_testyear_fixed_rv0p10_sl1p5_tp2_sltp_risk_geometry_phase8_v3
```

Current OLAP metrics:

| Metric | Value |
|---|---:|
| Asset | ETHUSDT |
| Timeframe | 4h |
| Model | SAC |
| Input family | kitchen_sink_guarded |
| Test coverage | 52 weeks |
| Mean weekly return | +0.1302% |
| Annual return | +6.7688% |
| Mean weekly RAP | -0.0365% |
| Annual RAP | -1.8978% |
| Mean weekly drawdown | 0.3333% |
| SL/TP mode | fixed_atr |
| rel_volume | 0.10 |
| k_sl / k_tp | 1.5 / 2.0 |

Interpretation:

- This is the strongest current full-year control, but it does not beat the
  Colombia 12% E.A. low-risk hurdle and has negative annual RAP.
- It is still the correct primary `doin` starting point because it has complete
  52-week evidence and reproducible configuration.

## Secondary Opportunity Seed

Candidate:

```text
solusdt_4h_kitchen_sink_guarded_all_available_sac_fine_tune_recent_window_m6_base3y_margin_aware_rv0p50_cap2p5_sltp_risk_geometry_phase8_v1_seed9_adaptive_top_seed_extension_seed9_v1_seed17_adaptive_top_seed_extension_seed17_v1
```

Current OLAP metrics:

| Metric | Value |
|---|---:|
| Asset | SOLUSDT |
| Timeframe | 4h |
| Model | SAC |
| Input family | kitchen_sink_guarded |
| Test coverage | 10 weeks |
| Mean weekly return | +6.3157% |
| Projected annual return from observed weeks | +63.1570% |
| Mean weekly RAP | +4.6243% |
| Projected annual RAP from observed weeks | +46.2434% |
| Mean weekly drawdown | 3.3827% |
| SL/TP mode | margin_aware_atr |
| rel_volume | 0.50 |
| k_sl / k_tp | 2.0 / 3.0 |

Interpretation:

- This is not a full-year winner. It is a bloom/opportunity seed.
- It should be used to design and test a portfolio opportunity detector, not to
  claim the whole-year strategy is solved.

## Rush-Week Evidence By Asset

Definition used for this quick snapshot:

```text
rush row = weekly_result_test_week_olap row where
           mean_test_return > 1% and mean_test_rap > 1%
```

| Asset | Candidates | Weekly rows | Max weekly return | Max weekly RAP | Rush-row rate |
|---|---:|---:|---:|---:|---:|
| SOLUSDT | 207 | 3085 | +29.1544% | +26.9426% | 12.45% |
| ETHUSDT | 281 | 7029 | +13.5071% | +12.2728% | 3.84% |
| XRPUSDT | 34 | 376 | +0.5973% | +0.5635% | 0.00% |
| BNBUSDT | 44 | 572 | +0.7519% | +0.4173% | 0.00% |
| BTCUSDT | 48 | 570 | +9.2646% | +0.3454% | 0.00% |
| ADAUSDT | 34 | 407 | +0.2020% | +0.1642% | 0.00% |
| DOGEUSDT | 2 | 64 | +0.0080% | +0.0016% | 0.00% |
| BTCUSDT_PERP | 32 | 240 | +9.0774% | +0.0000% | 0.00% |

Practical conclusion:

- SOLUSDT is the clearest opportunity/bloom asset in the current OLAP.
- ETHUSDT has fewer but nonzero rush rows and remains the full-year control.
- Other assets should not be discarded forever, but there is not enough current
  evidence to prioritize them before the Monday handoff.

## Monday DOIN Search Priority

Start with a small, high-signal search space:

1. ETHUSDT 4h kitchen_sink_guarded SAC full-year control.
2. SOLUSDT 4h kitchen_sink_guarded SAC bloom seed.
3. Risk geometry around the already useful range:
   - rel_volume around 0.05, 0.075, 0.10 for full-year control;
   - rel_volume around 0.25 to 0.50 for bloom/opportunity candidates;
   - k_sl / k_tp around 1.5/2.0, 2.0/3.0, and nearby values.
4. The objective should report at least:
   - mean weekly return;
   - annual return;
   - mean weekly RAP;
   - annual RAP;
   - mean weekly drawdown;
   - worst weekly RAP;
   - coverage weeks.

Do not optimize against partial-week projections as if they were full-year
truth. Use them as exploration priors only.

## Later Portfolio Opportunity Lane

After `doin` is running, build a causal weekly opportunity dataset from OLAP:

```text
features available before weekend rebalance
  -> probability of next-week opportunity/rush
  -> portfolio asset weights
  -> realized next-week return/RAP/drawdown
```

The detector should learn asset-specific and cross-asset bloom conditions. The
goal is not merely to find a good static asset, but to rotate allocation toward
assets entering temporarily exploitable regimes.
