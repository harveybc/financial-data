# Feature Redundancy and Stability Report

**Asset:** ethusdt  **Timeframe:** 4h  **Feature family:** tech_stat
**Fit window:** 2017-09-28T04:00:00+00:00 → 2023-12-31T20:00:00+00:00 (13699 rows)
**Heldout boundary:** 2025-01-01T00:00:00Z (Stage C firewall)
**Correlation clustering threshold:** |r| ≥ 0.9
**Chronological folds:** 5

---

## 1. Feature Count and Family Grouping

Total feature columns analysed: **83**

| Family | Count | Features (truncated) |
| --- | --- | --- |
| bollinger | 5 | bb_upper, bb_middle, bb_lower, bb_pct_b, bb_width |
| momentum_oscillators | 12 | rsi_7, rsi_14, rsi_21, stoch_k, stoch_d, … (+7) |
| regime_flags | 4 | vol_regime_high, vol_regime_low, hurst_proxy_200, zscore_close_100 |
| returns | 11 | return_1, log_return_1, return_5, log_return_5, return_10, … (+6) |
| rolling_moments | 15 | roll_mean_ret_20, roll_std_ret_20, roll_skew_ret_20, roll_kurt_ret_20, roll_mean_ret_60, … (+10) |
| trend | 24 | sma_10, ema_10, close_sma_ratio_10, sma_20, ema_20, … (+19) |
| volatility | 7 | atr_14, natr_14, hist_vol_10, hist_vol_20, hist_vol_60, … (+2) |
| volume_liquidity | 5 | obv, obv_delta_20, volume_ratio_20, vwap_60, mfi_14 |

---

## 2. Near-Constant and Binary Features

| Feature | Flag | std | mean | n_unique |
| --- | --- | --- | --- | --- |
| vol_regime_high | BINARY_FLAG | 0.452012 | 0.286225 | 2 |
| vol_regime_low | BINARY_FLAG | 0.496853 | 0.556172 | 2 |

---

## 3. Missingness and Warmup Profile

All features have zero NaN rows in the train CSV.  Warmup rows may have been pre-filled to 0 by the feature-engineering pipeline.

Features with longest heuristic warmup period (top 10):

| Feature | warmup_heuristic |
| --- | --- |
| roll_mean_ret_252 | 252 |
| roll_std_ret_252 | 252 |
| roll_skew_ret_252 | 252 |
| roll_kurt_ret_252 | 252 |
| sma_200 | 200 |
| ema_200 | 200 |
| close_sma_ratio_200 | 200 |
| hurst_proxy_200 | 200 |
| sma_100 | 100 |
| ema_100 | 100 |

---

## 4. Perfect and Near-Perfect Correlations (|r| ≥ 0.99)

| Feature A | Feature B | |r| |
| --- | --- | --- |
| roll_mean_ret_20 | log_return_20 | 1.000000 |

> **1 feature pair(s)** with |r| ≥ 0.99.  These are functionally redundant and one of each pair can be dropped.

---

## 5. Greedy Cluster Representatives

Clustering method: **greedy_column_order**    Threshold: |r| ≥ 0.9
Total features: 83    Clusters: 41    Standalone: 27

Clusters with more than 1 member (showing representative → members):

| Cluster ID | Representative | n_members | Members |
| --- | --- | --- | --- |
| 0 | return_1 | 3 | return_1, log_return_1, statistical__log_return_1 |
| 1 | return_5 | 3 | return_5, log_return_5, close_sma_ratio_10 |
| 2 | return_10 | 4 | return_10, log_return_10, close_sma_ratio_20, roc_10 |
| 3 | return_20 | 4 | return_20, log_return_20, roc_20, roll_mean_ret_20 |
| 4 | return_60 | 6 | return_60, log_return_60, close_sma_ratio_100, roc_60, trend_slope_50, roll_mean_ret_60 |
| 5 | sma_10 | 15 | sma_10, ema_10, sma_20, ema_20, sma_50, ema_50, sma_100, ema_100, sma_200, ema_200, bb_upper, bb_middle, bb_lower, obv, vwap_60 |
| 6 | close_sma_ratio_50 | 2 | close_sma_ratio_50, ema_cross_10_50 |
| 7 | close_sma_ratio_200 | 2 | close_sma_ratio_200, ema_cross_20_100 |
| 8 | macd | 2 | macd, macd_signal |
| 10 | rsi_7 | 5 | rsi_7, rsi_14, stoch_k, williams_r_14, bb_pct_b |
| 11 | rsi_21 | 2 | rsi_21, zscore_close_100 |
| 18 | natr_14 | 3 | natr_14, hist_vol_20, roll_std_ret_20 |
| 20 | hist_vol_60 | 3 | hist_vol_60, roll_std_ret_60, realized_var_48 |
| 23 | volume_sma_10 | 2 | volume_sma_10, volume_sma_20 |

---

## 6. Feature Stability Across Chronological Train Folds

(5 equal-size chronological folds over the train window.)

**Most stable features** (lowest CV of std across folds):

| Rank | Feature | mean_std | std_of_std | cv_of_std |
| --- | --- | --- | --- | --- |
| 1 | bb_pct_b | 0.328242 | 0.002070 | 0.0063 |
| 2 | vol_regime_low | 0.494222 | 0.004203 | 0.0085 |
| 3 | vol_regime_high | 0.451754 | 0.008286 | 0.0183 |
| 4 | rsi_7 | 17.293711 | 0.433215 | 0.0251 |
| 5 | mfi_14 | 17.046395 | 0.538821 | 0.0316 |
| 6 | cci_14 | 94.368023 | 3.266387 | 0.0346 |
| 7 | zscore_close_100 | 1.415444 | 0.051741 | 0.0366 |
| 8 | rsi_14 | 12.814757 | 0.511551 | 0.0399 |
| 9 | rsi_21 | 10.734715 | 0.589730 | 0.0549 |
| 10 | stoch_k | 26.629955 | 1.610496 | 0.0605 |

**Least stable features** (highest CV of std across folds):

| Rank | Feature | mean_std | std_of_std | cv_of_std |
| --- | --- | --- | --- | --- |
| 83 | obv | 3334360.856929 | 3915765.931080 | 1.1744 |
| 82 | ema_200 | 464.923556 | 402.832176 | 0.8664 |
| 81 | sma_200 | 476.309379 | 411.356563 | 0.8636 |
| 80 | ema_100 | 489.020146 | 418.936415 | 0.8567 |
| 79 | sma_100 | 494.627009 | 422.488582 | 0.8542 |
| 78 | vwap_60 | 497.049730 | 423.383544 | 0.8518 |
| 77 | ema_50 | 499.998463 | 425.598751 | 0.8512 |
| 76 | sma_50 | 502.645142 | 427.286770 | 0.8501 |
| 75 | bb_lower | 475.310244 | 403.063348 | 0.8480 |
| 74 | ema_20 | 506.263560 | 429.241749 | 0.8479 |

---

## 7. Governance

| Check | Result |
| --- | --- |
| Heldout rows (>= 2025-01-01) in fit data | NONE — PASS |
| Validation rows used for fitting | NONE — PASS |
| Timestamp column present and valid | PASS |
| Timestamps monotonic, no duplicates | PASS |
| uses_heldout | false |
| fit_excludes_heldout_2025 | true |

---

*Generated by stage3x_feature_redundancy_stability_worker.py  at 2026-05-18T01:30:01.701655+00:00*
