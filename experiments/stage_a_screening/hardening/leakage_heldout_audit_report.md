# Leakage & Held-Out Firewall Audit Report — Stage A

Generated: 2026-05-10T04:28:18.299916+00:00

---

## 1. Executive Summary

- **Total runs audited:** 4933
- **PASS_HELDOUT_FIREWALL:** 3515
- **FAIL_HELDOUT_LEAKAGE:** 0
- **BLOCKED_INPUT_MISSING:** 1418
- **BLOCKED_TIMESTAMP_INVALID:** 0
- **Runs with warnings:** 0
- **Unique (asset, timeframe, preset) combos in run index:** 509
- **Of those, with input CSV found and audited:** 368

**Best run** (`ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave`):
  - Input audit status: **PASS_HELDOUT_FIREWALL**
  - min(DATE_TIME): 2017-09-28 04:00:00
  - max(DATE_TIME): 2023-12-31 20:00:00
  - Heldout boundary: 2025-01-01 00:00:00
  - max_ts < boundary: True
  - Warnings: none
  - B10 firewall cleared: **True**

**B1_LEAKAGE_AUDIT clearance:** PARTIALLY_CLEARED — heldout_timestamp_exclusion checked for auditable runs. All other B1 sub-checks are NOT_APPLICABLE (own-asset OHLCV presets) or DEFERRED (learned presets — require Stage B model artifacts).
**B10_HELDOUT_FIREWALL clearance:** PARTIALLY_CLEARED — 3515 runs pass; 1418 runs have unauditable inputs (no train.csv)

---

## 2. Classification Breakdown

| Status | Count |
| --- | ---: |
| PASS_HELDOUT_FIREWALL | 3515 |
| FAIL_HELDOUT_LEAKAGE | 0 |
| BLOCKED_INPUT_MISSING | 1418 |
| BLOCKED_TIMESTAMP_INVALID | 0 |
| Runs with any warning | 0 |

---

## 3. B1 Leakage Audit Checklist Status

| Check | Auditable Now | Verdict | Notes |
| --- | :---: | --- | --- |
| `heldout_timestamp_exclusion` | Yes | PARTIAL PASS (3515 pass, 1418 unauditable) | max(DATE_TIME) < 2025-01-01 check on train.csv |
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

- Runs with input CSV found: **3515**
- Of those, passing heldout firewall: **3515**
- Of those, failing (data leakage): **0**
- Runs with missing input (cannot verify): **1418**

> **B10 PARTIALLY CLEARED:** All audited inputs pass. However, 1418 runs have missing input files and cannot be verified. These correspond to presets/timeframes without generated train.csv (crypto_full, fx_full, kitchen_sink_guarded, sota_low_cost, learned_cnn, all 15m runs).

---

## 5. Results by Asset

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| adausdt | 217 | 155 | 0 | 62 | 0 |
| audusd | 232 | 205 | 0 | 27 | 0 |
| bnbusdt | 219 | 157 | 0 | 62 | 0 |
| btcusdt | 243 | 171 | 0 | 72 | 0 |
| btcusdt_perp | 224 | 180 | 0 | 44 | 0 |
| dogeusdt | 229 | 166 | 0 | 63 | 0 |
| ethusdt | 241 | 171 | 0 | 70 | 0 |
| ethusdt_perp | 223 | 187 | 0 | 36 | 0 |
| eurgbp | 318 | 272 | 0 | 46 | 0 |
| eurjpy | 396 | 222 | 0 | 174 | 0 |
| eurusd | 250 | 104 | 0 | 146 | 0 |
| gbpjpy | 217 | 105 | 0 | 112 | 0 |
| gbpusd | 232 | 124 | 0 | 108 | 0 |
| linkusdt | 219 | 157 | 0 | 62 | 0 |
| nzdusd | 257 | 212 | 0 | 45 | 0 |
| solusdt | 225 | 154 | 0 | 71 | 0 |
| usdcad | 235 | 223 | 0 | 12 | 0 |
| usdchf | 280 | 229 | 0 | 51 | 0 |
| usdjpy | 253 | 143 | 0 | 110 | 0 |
| xrpusdt | 223 | 178 | 0 | 45 | 0 |

---

## 6. Results by Timeframe

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| 15m | 1570 | 685 | 0 | 885 | 0 |
| 1h | 1649 | 1366 | 0 | 283 | 0 |
| 4h | 1714 | 1464 | 0 | 250 | 0 |

---

## 7. Results by Preset

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline_12 | 612 | 461 | 0 | 151 | 0 |
| crypto_full | 248 | 179 | 0 | 69 | 0 |
| fx_full | 306 | 188 | 0 | 118 | 0 |
| kitchen_sink_guarded | 549 | 378 | 0 | 171 | 0 |
| learned_cnn | 554 | 349 | 0 | 205 | 0 |
| learned_lstm | 569 | 350 | 0 | 219 | 0 |
| sota_low_cost | 248 | 195 | 0 | 53 | 0 |
| tech_full | 615 | 461 | 0 | 154 | 0 |
| tech_stat | 633 | 500 | 0 | 133 | 0 |
| tech_stat_decomp | 599 | 454 | 0 | 145 | 0 |

---

## 8. Results by Algorithm

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| dqn | 1659 | 1191 | 0 | 468 | 0 |
| ppo | 1683 | 1206 | 0 | 477 | 0 |
| sac | 1591 | 1118 | 0 | 473 | 0 |

---

## 9. Results by Machine

| Group | Total | PASS | FAIL | BLOCKED | Warned |
| --- | ---: | ---: | ---: | ---: | ---: |
| dragon | 2490 | 1779 | 0 | 711 | 0 |
| gamma | 2290 | 1583 | 0 | 707 | 0 |
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
