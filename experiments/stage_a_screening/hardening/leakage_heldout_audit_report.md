# Leakage & Held-Out Firewall Audit Report — Stage A

Generated: 2026-05-03T06:19:08.491275+00:00

---

## 1. Executive Summary

- **Total runs audited:** 356
- **PASS_HELDOUT_FIREWALL:** 206
- **FAIL_HELDOUT_LEAKAGE:** 0
- **BLOCKED_INPUT_MISSING:** 150
- **BLOCKED_TIMESTAMP_INVALID:** 0
- **Runs with warnings:** 0
- **Unique (asset, timeframe, preset) combos in run index:** 106
- **Of those, with input CSV found and audited:** 76

**Best run** (`ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave`):
  - Input audit status: **PASS_HELDOUT_FIREWALL**
  - min(DATE_TIME): 2017-09-28 04:00:00
  - max(DATE_TIME): 2023-12-31 20:00:00
  - Heldout boundary: 2025-01-01 00:00:00
  - max_ts < boundary: True
  - Warnings: none
  - B10 firewall cleared: **True**

**B1_LEAKAGE_AUDIT clearance:** PARTIALLY_CLEARED — heldout_timestamp_exclusion checked for auditable runs. All other B1 sub-checks are NOT_APPLICABLE (own-asset OHLCV presets) or DEFERRED (learned presets — require Stage B model artifacts).
**B10_HELDOUT_FIREWALL clearance:** PARTIALLY_CLEARED — 206 runs pass; 150 runs have unauditable inputs (no train.csv)

---

## 2. Classification Breakdown

| Status | Count |
| --- | ---: |
| PASS_HELDOUT_FIREWALL | 206 |
| FAIL_HELDOUT_LEAKAGE | 0 |
| BLOCKED_INPUT_MISSING | 150 |
| BLOCKED_TIMESTAMP_INVALID | 0 |
| Runs with any warning | 0 |

---

## 3. B1 Leakage Audit Checklist Status

| Check | Auditable Now | Verdict | Notes |
| --- | :---: | --- | --- |
| `heldout_timestamp_exclusion` | Yes | PARTIAL PASS (206 pass, 150 unauditable) | max(DATE_TIME) < 2025-01-01 check on train.csv |
| `transform_fit_window_check` | No | NOT_APPLICABLE / DEFERRED | No fitted-transform metadata artifacts found in Stage A inputs. |
| `scaler_fit_window_check` | No | NOT_APPLICABLE / DEFERRED | Scaler is fit inside training process; no Stage A artifact to inspect. |
| `autoencoder_fit_window_check` | No | NOT_APPLICABLE / DEFERRED | Applicable to learned presets only; encoder model artifacts not present in inputs/. |
| `hmm_regime_fit_window_check` | No | NOT_APPLICABLE / DEFERRED | HMM not used in any current Stage A preset. |
| `macro_vintage_check` | No | NOT_APPLICABLE / DEFERRED | No macro data used in current Stage A presets (baseline_12, tech_*, learned_*). |
| `forward_fill_availability_check` | No | NOT_APPLICABLE / DEFERRED | No forward-fill or availability features in current Stage A presets. |
| `post_cutoff_feature_audit` | No | NOT_APPLICABLE / DEFERRED | Cannot verify without fitted-transform metadata. |

> **Note:** Checks marked NOT_APPLICABLE apply only to presets that use the relevant
> feature type (macro data, autoencoder representations, HMM regimes, forward-fill
> sources). All current Stage A presets use own-asset OHLCV or LSTM/CNN latent vectors.
> Fitted-transform window checks are deferred to Stage B when model artifacts are available.

---

## 4. B10 Heldout Firewall Detail

The stage_b_promotion_gate.yaml requires `heldout_start: 2025-01-01T00:00:00Z`.
This audit verifies `max(DATE_TIME) < 2025-01-01 00:00:00` for every train.csv found.

- Runs with input CSV found: **206**
- Of those, passing heldout firewall: **206**
- Of those, failing (data leakage): **0**
- Runs with missing input (cannot verify): **150**

> **B10 PARTIALLY CLEARED:** All audited inputs pass. However, 150 runs have missing input files and cannot be verified. These correspond to presets/timeframes without generated train.csv (crypto_full, fx_full, kitchen_sink_guarded, sota_low_cost, learned_cnn, all 15m runs).

---

## 5. Results by Asset

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| audusd | 16 | 16 | 0 | 0 | 0 |
| btcusdt | 113 | 27 | 0 | 86 | 0 |
| ethusdt | 20 | 17 | 0 | 3 | 0 |
| eurgbp | 16 | 16 | 0 | 0 | 0 |
| eurusd | 90 | 32 | 0 | 58 | 0 |
| gbpusd | 16 | 16 | 0 | 0 | 0 |
| nzdusd | 16 | 16 | 0 | 0 | 0 |
| usdcad | 16 | 16 | 0 | 0 | 0 |
| usdchf | 16 | 16 | 0 | 0 | 0 |
| usdjpy | 37 | 34 | 0 | 3 | 0 |

---

## 6. Results by Timeframe

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| 15m | 110 | 0 | 0 | 110 | 0 |
| 1h | 137 | 105 | 0 | 32 | 0 |
| 4h | 109 | 101 | 0 | 8 | 0 |

---

## 7. Results by Preset

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline_12 | 72 | 57 | 0 | 15 | 0 |
| crypto_full | 6 | 0 | 0 | 6 | 0 |
| fx_full | 2 | 0 | 0 | 2 | 0 |
| kitchen_sink_guarded | 6 | 0 | 0 | 6 | 0 |
| learned_cnn | 22 | 0 | 0 | 22 | 0 |
| learned_lstm | 30 | 1 | 0 | 29 | 0 |
| sota_low_cost | 10 | 0 | 0 | 10 | 0 |
| tech_full | 74 | 52 | 0 | 22 | 0 |
| tech_stat | 77 | 62 | 0 | 15 | 0 |
| tech_stat_decomp | 57 | 34 | 0 | 23 | 0 |

---

## 8. Results by Algorithm

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| dqn | 136 | 90 | 0 | 46 | 0 |
| ppo | 147 | 94 | 0 | 53 | 0 |
| sac | 73 | 22 | 0 | 51 | 0 |

---

## 9. Results by Machine

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| dragon | 120 | 31 | 0 | 89 | 0 |
| gamma | 83 | 22 | 0 | 61 | 0 |
| omega | 153 | 153 | 0 | 0 | 0 |

---

## 10. Missing Input Files — Explanation

Runs with `BLOCKED_INPUT_MISSING` correspond to (asset, timeframe, preset) combinations
where no `train.csv` was generated during input preparation. Root causes:

| Reason | Affected |
| --- | --- |
| 15m timeframe — no 15m input CSVs generated | All 15m runs |
| crypto_full preset — no input CSV generated | All crypto_full runs |
| fx_full preset — no input CSV generated | All fx_full runs |
| kitchen_sink_guarded — no input CSV generated | All kitchen_sink_guarded runs |
| sota_low_cost — no input CSV generated | All sota_low_cost runs |
| learned_cnn — no input CSV generated | All learned_cnn runs |
| learned_lstm — only btcusdt/4h generated | Other learned_lstm asset/tf combos |

> Missing input CSVs do not indicate leakage; they indicate the input preparation worker
> did not export train.csv for that (asset, timeframe, preset) combination. The heldout
> firewall for these runs must be verified at the feature parquet source level (Stage B).

---

## 11. Governance Gate Update

| Gate | Previous Status | Updated Status |
| --- | --- | --- |
| B1_LEAKAGE_AUDIT | NOT COMPLETED | PARTIALLY CLEARED — `heldout_timestamp_exclusion` |
|  |  | checked for all runs with available inputs. Other checks deferred |
|  |  | (N/A for current presets or require Stage B artifacts). |
| B10_HELDOUT_FIREWALL | NOT AUDITED | PARTIALLY CLEARED — all audited inputs pass. |
|  |  | Runs without input files remain unverified (blocked). |

> **Conclusion:** The best run (`ethusdt_4h_sac_tech_stat`) uses the `tech_stat` preset
> which has a fully audited input CSV with max(DATE_TIME)=2023-12-31, well before the
> 2025-01-01 heldout boundary. B10 is **cleared** for this specific run. B1 is **partially
> cleared** — only `heldout_timestamp_exclusion` is verifiable; all other B1 sub-checks are
> N/A for `tech_stat` (own-asset OHLCV features only, no fitted transforms).

---

*End of report. Generated by stage31_leakage_heldout_audit_worker.py*
