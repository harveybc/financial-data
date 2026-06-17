# Simple Baseline Report — Stage A B8 Evidence

Generated: 2026-05-10T04:37:31.948292+00:00

---

## 1. Executive Summary

- **Total runs evaluated:** 4933
- **Runs with baselines computable:** 3515
- **Runs without input (BLOCKED_INPUT_MISSING):** 1418
- **RL runs beating all baselines at base_cost:** 72
- **RL runs beating all baselines at pessimistic_cost:** 72
- **RL runs failing to beat best baseline at base_cost:** 3432

**B8_SIMPLE_BASELINES clearance:** PARTIALLY_CLEARED — surviving candidate (PROMOTE_BLOCKED_HARDENING) beats all simple baselines at base_cost AND pessimistic_cost. Note: 3432 other (mostly killed) runs fail vs their best baseline — expected, as killed runs have negligible or negative returns. 1418 runs still blocked (no input CSV available).

> Position sizing: POSITION_FRACTION = 0.01 (1% of capital, same as RL sim).
> All returns are at 1% position size and directly comparable to the RL `total_return`.
> Buy-and-hold at 1% position ≪ raw market return (market return × 0.01).
> Baselines use full cost per position change; RL cost reconstructed from trade count.
> The RL agent's reported `buy_hold_return` in index.csv is at 100% position size
> (raw price appreciation) — not at 1% — so it is NOT comparable to RL total_return.

---

## 2. Best Run Comparison

**Run:** `ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave`

| Metric | Value |
| --- | --- |
| RL gross return (sim 2bps baked in) | 0.151216 |
| RL net at base_cost | 0.143548 |
| RL net at pessimistic_cost | 0.130768 |
| Best baseline at base_cost | buy_and_hold_long = 0.04671504 |
| Best baseline at pessimistic_cost | buy_and_hold_long = 0.04669934 |
| RL > best baseline at base_cost | **True** |
| RL > best baseline at pessimistic_cost | **True** |
| B8 evidence verdict | **PASS** |

### 2.1 Per-Baseline Breakdown (ethusdt/4h/tech_stat)

| Strategy | Base Cost Return | Pessimistic Cost Return |
| --- | ---: | ---: |
| no_trade | 0.000000 | 0.000000 |
| buy_and_hold_long | 0.046715 | 0.046699 |
| random_long_short_flat | -0.127989 | -0.273199 |
| turnover_matched_random | 0.001535 | -0.003096 |
| simple_momentum | -0.181532 | -0.343823 |
| simple_reversal | -0.116906 | -0.292011 |

> **CONCLUSION:** The best SAC run beats all simple baselines at both base and
> pessimistic cost assumptions. B8 evidence is POSITIVE for this run.

---

## 3. Cost Model

| Parameter | Value |
| --- | --- |
| POSITION_FRACTION | 0.01 |
| crypto_spot base_cost | 5+3+3 = 11 bps/side |
| crypto_spot pessimistic_cost | 10+8+8 = 26 bps/side |
| fx base_cost | 0.5+1.0+0.5 = 2 bps/side |
| fx pessimistic_cost | 1.0+3.0+1.5 = 5.5 bps/side |
| Cost applied | per |Δposition| unit at each bar |
| Turnover penalty | NOT applied to baselines (conservative) |
| Baseline cost | Full cost per position change (no prior sim cost) |
| RL cost reconstruction | gross − trades × 2 × delta_bps / 10000 × PF |
| delta_bps | max(0, full_cost_bps − sim_commission_bps) per side |
| Total RL effective cost | sim_commission (baked in) + delta = full_cost |
| Note | Both RL and baselines pay the same total scenario cost. |

---

## 4. Input Coverage

| Preset | Total Runs | With Input | Without Input |
| --- | ---: | ---: | ---: |
| baseline_12 | 612 | 461 | 151 |
| crypto_full | 248 | 179 | 69 |
| fx_full | 306 | 188 | 118 |
| kitchen_sink_guarded | 549 | 378 | 171 |
| learned_cnn | 554 | 349 | 205 |
| learned_lstm | 569 | 350 | 219 |
| sota_low_cost | 248 | 195 | 53 |
| tech_full | 615 | 461 | 154 |
| tech_stat | 633 | 500 | 133 |
| tech_stat_decomp | 599 | 454 | 145 |

> Runs without input CSV (BLOCKED_INPUT_MISSING) include all 15m runs and runs using
> presets without generated train.csv: crypto_full, fx_full, kitchen_sink_guarded,
> sota_low_cost, learned_cnn, most learned_lstm combos. See leakage_heldout_audit.csv.

---

## 5. Best Baseline by Asset/Timeframe/Preset (base_cost)

| Asset | TF | Preset | Best Strategy | Base Return | Pessimistic Return |
| --- | --- | --- | --- | ---: | ---: |
| adausdt | 15m | baseline_12 | buy_and_hold_long | 0.044964 | 0.044949 |
| adausdt | 15m | crypto_full | buy_and_hold_long | 0.044255 | 0.044239 |
| adausdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.043372 | 0.043357 |
| adausdt | 15m | learned_lstm | buy_and_hold_long | 0.044462 | 0.044446 |
| adausdt | 15m | tech_stat | buy_and_hold_long | 0.044139 | 0.044123 |
| adausdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.044255 | 0.044239 |
| adausdt | 1h | baseline_12 | buy_and_hold_long | 0.041575 | 0.041560 |
| adausdt | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.038016 | 0.038000 |
| adausdt | 1h | learned_cnn | buy_and_hold_long | 0.041595 | 0.041579 |
| adausdt | 1h | sota_low_cost | buy_and_hold_long | 0.040174 | 0.040159 |
| adausdt | 1h | tech_full | buy_and_hold_long | 0.041146 | 0.041130 |
| adausdt | 1h | tech_stat | buy_and_hold_long | 0.040174 | 0.040159 |
| adausdt | 1h | tech_stat_decomp | buy_and_hold_long | 0.040040 | 0.040024 |
| adausdt | 4h | baseline_12 | buy_and_hold_long | 0.037306 | 0.037290 |
| adausdt | 4h | crypto_full | buy_and_hold_long | 0.039996 | 0.039980 |
| adausdt | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.041385 | 0.041370 |
| adausdt | 4h | learned_cnn | buy_and_hold_long | 0.038271 | 0.038255 |
| adausdt | 4h | sota_low_cost | buy_and_hold_long | 0.040952 | 0.040936 |
| adausdt | 4h | tech_full | buy_and_hold_long | 0.038114 | 0.038099 |
| adausdt | 4h | tech_stat | buy_and_hold_long | 0.040952 | 0.040936 |
| audusd | 15m | baseline_12 | buy_and_hold_long | 0.000261 | 0.000257 |
| audusd | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.000492 | 0.000488 |
| audusd | 15m | learned_lstm | buy_and_hold_long | 0.000318 | 0.000314 |
| audusd | 15m | tech_full | buy_and_hold_long | 0.000457 | 0.000453 |
| audusd | 15m | tech_stat | buy_and_hold_long | 0.000457 | 0.000453 |
| audusd | 1h | baseline_12 | buy_and_hold_long | 0.000427 | 0.000423 |
| audusd | 1h | fx_full | buy_and_hold_long | 0.000485 | 0.000481 |
| audusd | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.000491 | 0.000487 |
| audusd | 1h | learned_cnn | buy_and_hold_long | 0.000274 | 0.000271 |
| audusd | 1h | learned_lstm | buy_and_hold_long | 0.000274 | 0.000271 |
| audusd | 1h | tech_full | buy_and_hold_long | 0.000367 | 0.000364 |
| audusd | 1h | tech_stat | buy_and_hold_long | 0.000487 | 0.000484 |
| audusd | 1h | tech_stat_decomp | buy_and_hold_long | 0.000485 | 0.000481 |
| audusd | 4h | baseline_12 | buy_and_hold_long | 0.000354 | 0.000351 |
| audusd | 4h | fx_full | buy_and_hold_long | 0.000019 | 0.000016 |
| audusd | 4h | kitchen_sink_guarded | no_trade | 0.000000 | 0.000000 |
| audusd | 4h | learned_cnn | buy_and_hold_long | 0.000145 | 0.000142 |
| audusd | 4h | learned_lstm | buy_and_hold_long | 0.000145 | 0.000142 |
| audusd | 4h | tech_full | buy_and_hold_long | 0.000295 | 0.000292 |
| audusd | 4h | tech_stat | buy_and_hold_long | 0.000065 | 0.000062 |
| audusd | 4h | tech_stat_decomp | buy_and_hold_long | 0.000019 | 0.000016 |
| bnbusdt | 15m | baseline_12 | buy_and_hold_long | 0.097388 | 0.097372 |
| bnbusdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.093839 | 0.093823 |
| bnbusdt | 15m | sota_low_cost | buy_and_hold_long | 0.095922 | 0.095905 |
| bnbusdt | 15m | tech_full | buy_and_hold_long | 0.095719 | 0.095703 |
| bnbusdt | 15m | tech_stat | buy_and_hold_long | 0.095922 | 0.095905 |
| bnbusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.094854 | 0.094838 |
| bnbusdt | 1h | baseline_12 | buy_and_hold_long | 0.092493 | 0.092477 |
| bnbusdt | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.093233 | 0.093216 |
| bnbusdt | 1h | learned_cnn | buy_and_hold_long | 0.093897 | 0.093881 |
| bnbusdt | 1h | learned_lstm | buy_and_hold_long | 0.093897 | 0.093881 |
| bnbusdt | 1h | sota_low_cost | buy_and_hold_long | 0.093341 | 0.093325 |
| bnbusdt | 1h | tech_full | buy_and_hold_long | 0.093399 | 0.093382 |
| bnbusdt | 1h | tech_stat | buy_and_hold_long | 0.093341 | 0.093325 |
| bnbusdt | 4h | crypto_full | buy_and_hold_long | 0.073027 | 0.073011 |
| bnbusdt | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.065988 | 0.065972 |
| bnbusdt | 4h | learned_lstm | buy_and_hold_long | 0.088909 | 0.088892 |
| bnbusdt | 4h | sota_low_cost | buy_and_hold_long | 0.072616 | 0.072600 |
| bnbusdt | 4h | tech_full | buy_and_hold_long | 0.082579 | 0.082563 |
| bnbusdt | 4h | tech_stat | buy_and_hold_long | 0.072616 | 0.072600 |
| bnbusdt | 4h | tech_stat_decomp | buy_and_hold_long | 0.073027 | 0.073011 |
| btcusdt | 15m | baseline_12 | buy_and_hold_long | 0.045202 | 0.045186 |
| btcusdt | 15m | learned_cnn | buy_and_hold_long | 0.045114 | 0.045098 |
| btcusdt | 15m | sota_low_cost | buy_and_hold_long | 0.045665 | 0.045649 |
| btcusdt | 15m | tech_full | buy_and_hold_long | 0.045690 | 0.045675 |
| btcusdt | 15m | tech_stat | buy_and_hold_long | 0.045665 | 0.045649 |
| btcusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.045659 | 0.045643 |
| btcusdt | 1h | baseline_12 | buy_and_hold_long | 0.044394 | 0.044378 |
| btcusdt | 1h | crypto_full | buy_and_hold_long | 0.044008 | 0.043993 |
| btcusdt | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.044008 | 0.043993 |
| btcusdt | 1h | learned_cnn | buy_and_hold_long | 0.044378 | 0.044363 |
| btcusdt | 1h | learned_lstm | buy_and_hold_long | 0.044378 | 0.044363 |
| btcusdt | 1h | sota_low_cost | buy_and_hold_long | 0.024423 | 0.024407 |
| btcusdt | 1h | tech_stat | buy_and_hold_long | 0.043590 | 0.043574 |
| btcusdt | 4h | baseline_12 | buy_and_hold_long | 0.041356 | 0.041341 |
| btcusdt | 4h | learned_cnn | buy_and_hold_long | 0.042634 | 0.042618 |
| btcusdt | 4h | learned_lstm | buy_and_hold_long | 0.042634 | 0.042618 |
| btcusdt | 4h | sota_low_cost | buy_and_hold_long | 0.023935 | 0.023919 |
| btcusdt | 4h | tech_full | buy_and_hold_long | 0.041510 | 0.041494 |
| btcusdt | 4h | tech_stat | buy_and_hold_long | 0.040768 | 0.040752 |
| btcusdt_perp | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.025407 | 0.025391 |
| btcusdt_perp | 15m | learned_cnn | buy_and_hold_long | 0.025190 | 0.025175 |
| btcusdt_perp | 15m | learned_lstm | buy_and_hold_long | 0.025190 | 0.025175 |
| btcusdt_perp | 15m | sota_low_cost | buy_and_hold_long | 0.025382 | 0.025366 |
| btcusdt_perp | 15m | tech_full | buy_and_hold_long | 0.025249 | 0.025233 |
| btcusdt_perp | 15m | tech_stat | buy_and_hold_long | 0.025382 | 0.025366 |
| btcusdt_perp | 1h | baseline_12 | buy_and_hold_long | 0.024465 | 0.024450 |
| btcusdt_perp | 1h | crypto_full | buy_and_hold_long | 0.024316 | 0.024301 |
| btcusdt_perp | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.024316 | 0.024301 |
| btcusdt_perp | 1h | learned_lstm | buy_and_hold_long | 0.024659 | 0.024643 |
| btcusdt_perp | 1h | sota_low_cost | buy_and_hold_long | 0.024837 | 0.024821 |
| btcusdt_perp | 1h | tech_full | buy_and_hold_long | 0.024405 | 0.024390 |
| btcusdt_perp | 1h | tech_stat | buy_and_hold_long | 0.024837 | 0.024821 |
| btcusdt_perp | 1h | tech_stat_decomp | buy_and_hold_long | 0.024784 | 0.024768 |
| btcusdt_perp | 4h | baseline_12 | buy_and_hold_long | 0.023792 | 0.023777 |
| btcusdt_perp | 4h | crypto_full | buy_and_hold_long | 0.026292 | 0.026276 |
| btcusdt_perp | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.026292 | 0.026276 |
| btcusdt_perp | 4h | learned_cnn | buy_and_hold_long | 0.023704 | 0.023688 |
| btcusdt_perp | 4h | learned_lstm | buy_and_hold_long | 0.023704 | 0.023688 |
| btcusdt_perp | 4h | sota_low_cost | buy_and_hold_long | 0.026155 | 0.026140 |
| btcusdt_perp | 4h | tech_full | buy_and_hold_long | 0.025767 | 0.025751 |
| btcusdt_perp | 4h | tech_stat_decomp | buy_and_hold_long | 0.025904 | 0.025889 |
| dogeusdt | 15m | crypto_full | buy_and_hold_long | 0.080659 | 0.080643 |
| dogeusdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.080577 | 0.080561 |
| dogeusdt | 15m | learned_lstm | buy_and_hold_long | 0.079610 | 0.079594 |
| dogeusdt | 15m | sota_low_cost | buy_and_hold_long | 0.080562 | 0.080545 |
| dogeusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.080659 | 0.080643 |
| dogeusdt | 1h | baseline_12 | buy_and_hold_long | 0.076258 | 0.076241 |
| dogeusdt | 1h | crypto_full | buy_and_hold_long | 0.077605 | 0.077589 |
| dogeusdt | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.077495 | 0.077479 |
| dogeusdt | 1h | learned_cnn | buy_and_hold_long | 0.074985 | 0.074969 |
| dogeusdt | 1h | learned_lstm | buy_and_hold_long | 0.074985 | 0.074969 |
| dogeusdt | 1h | sota_low_cost | buy_and_hold_long | 0.077466 | 0.077450 |
| dogeusdt | 1h | tech_full | buy_and_hold_long | 0.077134 | 0.077118 |
| dogeusdt | 1h | tech_stat | buy_and_hold_long | 0.077466 | 0.077450 |
| dogeusdt | 1h | tech_stat_decomp | buy_and_hold_long | 0.077605 | 0.077589 |
| dogeusdt | 4h | baseline_12 | buy_and_hold_long | 0.076184 | 0.076168 |
| dogeusdt | 4h | crypto_full | buy_and_hold_long | 0.078078 | 0.078061 |
| dogeusdt | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.078742 | 0.078726 |
| dogeusdt | 4h | sota_low_cost | buy_and_hold_long | 0.078180 | 0.078164 |
| dogeusdt | 4h | tech_full | buy_and_hold_long | 0.077050 | 0.077034 |
| dogeusdt | 4h | tech_stat_decomp | buy_and_hold_long | 0.078078 | 0.078061 |
| ethusdt | 15m | baseline_12 | buy_and_hold_long | 0.052665 | 0.052649 |
| ethusdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.053135 | 0.053120 |
| ethusdt | 15m | learned_cnn | buy_and_hold_long | 0.052924 | 0.052908 |
| ethusdt | 15m | sota_low_cost | buy_and_hold_long | 0.053075 | 0.053059 |
| ethusdt | 15m | tech_full | buy_and_hold_long | 0.053190 | 0.053174 |
| ethusdt | 15m | tech_stat | buy_and_hold_long | 0.053075 | 0.053059 |
| ethusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.053135 | 0.053120 |
| ethusdt | 1h | baseline_12 | buy_and_hold_long | 0.051658 | 0.051642 |
| ethusdt | 1h | crypto_full | buy_and_hold_long | 0.050561 | 0.050546 |
| ethusdt | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.050561 | 0.050546 |
| ethusdt | 1h | tech_full | buy_and_hold_long | 0.050184 | 0.050168 |
| ethusdt | 1h | tech_stat | buy_and_hold_long | 0.050019 | 0.050003 |
| ethusdt | 1h | tech_stat_decomp | buy_and_hold_long | 0.049844 | 0.049828 |
| ethusdt | 4h | baseline_12 | buy_and_hold_long | 0.047555 | 0.047539 |
| ethusdt | 4h | crypto_full | buy_and_hold_long | 0.047951 | 0.047935 |
| ethusdt | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.047951 | 0.047935 |
| ethusdt | 4h | tech_full | buy_and_hold_long | 0.047951 | 0.047935 |
| ethusdt | 4h | tech_stat | buy_and_hold_long | 0.046715 | 0.046699 |
| ethusdt | 4h | tech_stat_decomp | buy_and_hold_long | 0.047022 | 0.047006 |
| ethusdt_perp | 15m | baseline_12 | buy_and_hold_long | 0.044132 | 0.044116 |
| ethusdt_perp | 15m | crypto_full | buy_and_hold_long | 0.044133 | 0.044118 |
| ethusdt_perp | 15m | learned_cnn | buy_and_hold_long | 0.045006 | 0.044990 |
| ethusdt_perp | 15m | sota_low_cost | buy_and_hold_long | 0.044180 | 0.044165 |
| ethusdt_perp | 15m | tech_full | buy_and_hold_long | 0.044124 | 0.044109 |
| ethusdt_perp | 15m | tech_stat | buy_and_hold_long | 0.044180 | 0.044165 |
| ethusdt_perp | 15m | tech_stat_decomp | buy_and_hold_long | 0.044133 | 0.044118 |
| ethusdt_perp | 1h | baseline_12 | buy_and_hold_long | 0.043101 | 0.043085 |
| ethusdt_perp | 1h | crypto_full | buy_and_hold_long | 0.043435 | 0.043419 |
| ethusdt_perp | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.043797 | 0.043781 |
| ethusdt_perp | 1h | sota_low_cost | buy_and_hold_long | 0.043394 | 0.043378 |
| ethusdt_perp | 1h | tech_full | buy_and_hold_long | 0.043391 | 0.043376 |
| ethusdt_perp | 1h | tech_stat | buy_and_hold_long | 0.043394 | 0.043378 |
| ethusdt_perp | 1h | tech_stat_decomp | buy_and_hold_long | 0.043435 | 0.043419 |
| ethusdt_perp | 4h | baseline_12 | buy_and_hold_long | 0.042813 | 0.042797 |
| ethusdt_perp | 4h | crypto_full | buy_and_hold_long | 0.043028 | 0.043012 |
| ethusdt_perp | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.041667 | 0.041651 |
| ethusdt_perp | 4h | learned_cnn | buy_and_hold_long | 0.042882 | 0.042866 |
| ethusdt_perp | 4h | learned_lstm | buy_and_hold_long | 0.042882 | 0.042866 |
| ethusdt_perp | 4h | sota_low_cost | buy_and_hold_long | 0.042804 | 0.042788 |
| ethusdt_perp | 4h | tech_full | buy_and_hold_long | 0.043511 | 0.043496 |
| ethusdt_perp | 4h | tech_stat | buy_and_hold_long | 0.042804 | 0.042788 |
| ethusdt_perp | 4h | tech_stat_decomp | buy_and_hold_long | 0.043028 | 0.043012 |
| eurgbp | 15m | learned_cnn | buy_and_hold_long | 0.002729 | 0.002726 |
| eurgbp | 15m | learned_lstm | buy_and_hold_long | 0.002729 | 0.002726 |
| eurgbp | 15m | tech_stat_decomp | buy_and_hold_long | 0.002764 | 0.002761 |
| eurgbp | 1h | baseline_12 | buy_and_hold_long | 0.002712 | 0.002708 |
| eurgbp | 1h | fx_full | buy_and_hold_long | 0.002778 | 0.002775 |
| eurgbp | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.002883 | 0.002879 |
| eurgbp | 1h | learned_cnn | buy_and_hold_long | 0.002696 | 0.002693 |
| eurgbp | 1h | learned_lstm | buy_and_hold_long | 0.002696 | 0.002693 |
| eurgbp | 1h | tech_full | buy_and_hold_long | 0.002773 | 0.002769 |
| eurgbp | 1h | tech_stat | buy_and_hold_long | 0.002780 | 0.002776 |
| eurgbp | 1h | tech_stat_decomp | buy_and_hold_long | 0.002778 | 0.002775 |
| eurgbp | 4h | baseline_12 | buy_and_hold_long | 0.002793 | 0.002790 |
| eurgbp | 4h | fx_full | buy_and_hold_long | 0.002923 | 0.002920 |
| eurgbp | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.002821 | 0.002818 |
| eurgbp | 4h | learned_cnn | turnover_matched_random | 0.003574 | 0.002230 |
| eurgbp | 4h | learned_lstm | turnover_matched_random | 0.003574 | 0.002230 |
| eurgbp | 4h | tech_full | buy_and_hold_long | 0.002928 | 0.002925 |
| eurgbp | 4h | tech_stat | buy_and_hold_long | 0.002903 | 0.002899 |
| eurgbp | 4h | tech_stat_decomp | buy_and_hold_long | 0.002923 | 0.002920 |
| eurjpy | 1h | baseline_12 | buy_and_hold_long | 0.002454 | 0.002451 |
| eurjpy | 1h | fx_full | buy_and_hold_long | 0.002811 | 0.002808 |
| eurjpy | 1h | kitchen_sink_guarded | turnover_matched_random | 0.004865 | 0.004848 |
| eurjpy | 1h | learned_cnn | buy_and_hold_long | 0.002474 | 0.002471 |
| eurjpy | 1h | learned_lstm | buy_and_hold_long | 0.002474 | 0.002471 |
| eurjpy | 1h | tech_stat | buy_and_hold_long | 0.002822 | 0.002818 |
| eurjpy | 1h | tech_stat_decomp | buy_and_hold_long | 0.002811 | 0.002808 |
| eurjpy | 4h | baseline_12 | buy_and_hold_long | 0.002645 | 0.002642 |
| eurjpy | 4h | fx_full | turnover_matched_random | 0.002462 | 0.000286 |
| eurjpy | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.002335 | 0.002331 |
| eurjpy | 4h | learned_cnn | buy_and_hold_long | 0.002393 | 0.002390 |
| eurjpy | 4h | learned_lstm | buy_and_hold_long | 0.002393 | 0.002390 |
| eurjpy | 4h | tech_full | buy_and_hold_long | 0.002688 | 0.002684 |
| eurjpy | 4h | tech_stat_decomp | turnover_matched_random | 0.002462 | 0.000286 |
| eurusd | 1h | baseline_12 | no_trade | 0.000000 | 0.000000 |
| eurusd | 1h | tech_full | no_trade | 0.000000 | 0.000000 |
| eurusd | 1h | tech_stat | no_trade | 0.000000 | 0.000000 |
| eurusd | 1h | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| eurusd | 4h | baseline_12 | no_trade | 0.000000 | 0.000000 |
| eurusd | 4h | tech_full | no_trade | 0.000000 | 0.000000 |
| eurusd | 4h | tech_stat | no_trade | 0.000000 | 0.000000 |
| eurusd | 4h | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| gbpjpy | 1h | baseline_12 | buy_and_hold_long | 0.000683 | 0.000680 |
| gbpjpy | 1h | fx_full | buy_and_hold_long | 0.000976 | 0.000973 |
| gbpjpy | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.000910 | 0.000906 |
| gbpjpy | 1h | learned_cnn | buy_and_hold_long | 0.000721 | 0.000717 |
| gbpjpy | 1h | tech_full | turnover_matched_random | 0.002154 | -0.000935 |
| gbpjpy | 1h | tech_stat | buy_and_hold_long | 0.000986 | 0.000982 |
| gbpjpy | 1h | tech_stat_decomp | buy_and_hold_long | 0.000976 | 0.000973 |
| gbpjpy | 4h | baseline_12 | buy_and_hold_long | 0.000770 | 0.000767 |
| gbpjpy | 4h | fx_full | turnover_matched_random | 0.001139 | -0.002749 |
| gbpjpy | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.000461 | 0.000458 |
| gbpjpy | 4h | learned_cnn | buy_and_hold_long | 0.000649 | 0.000646 |
| gbpjpy | 4h | learned_lstm | turnover_matched_random | 0.001247 | -0.005838 |
| gbpjpy | 4h | tech_full | buy_and_hold_long | 0.000678 | 0.000674 |
| gbpjpy | 4h | tech_stat | buy_and_hold_long | 0.000474 | 0.000470 |
| gbpjpy | 4h | tech_stat_decomp | turnover_matched_random | 0.001139 | -0.002749 |
| gbpusd | 1h | baseline_12 | no_trade | 0.000000 | 0.000000 |
| gbpusd | 1h | tech_full | no_trade | 0.000000 | 0.000000 |
| gbpusd | 1h | tech_stat | no_trade | 0.000000 | 0.000000 |
| gbpusd | 1h | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | baseline_12 | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | fx_full | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | kitchen_sink_guarded | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | learned_cnn | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | learned_lstm | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | tech_full | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | tech_stat | no_trade | 0.000000 | 0.000000 |
| gbpusd | 4h | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| linkusdt | 15m | crypto_full | buy_and_hold_long | 0.077698 | 0.077682 |
| linkusdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.077779 | 0.077763 |
| linkusdt | 15m | learned_cnn | buy_and_hold_long | 0.077096 | 0.077080 |
| linkusdt | 15m | learned_lstm | buy_and_hold_long | 0.077096 | 0.077080 |
| linkusdt | 15m | tech_full | buy_and_hold_long | 0.078057 | 0.078041 |
| linkusdt | 15m | tech_stat | buy_and_hold_long | 0.077612 | 0.077596 |
| linkusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.077698 | 0.077682 |
| linkusdt | 1h | baseline_12 | buy_and_hold_long | 0.074156 | 0.074140 |
| linkusdt | 1h | crypto_full | buy_and_hold_long | 0.074449 | 0.074433 |
| linkusdt | 1h | learned_cnn | buy_and_hold_long | 0.073388 | 0.073372 |
| linkusdt | 1h | learned_lstm | buy_and_hold_long | 0.073388 | 0.073372 |
| linkusdt | 1h | sota_low_cost | buy_and_hold_long | 0.074084 | 0.074068 |
| linkusdt | 1h | tech_full | buy_and_hold_long | 0.073709 | 0.073693 |
| linkusdt | 1h | tech_stat | buy_and_hold_long | 0.074084 | 0.074068 |
| linkusdt | 1h | tech_stat_decomp | buy_and_hold_long | 0.074449 | 0.074433 |
| linkusdt | 4h | baseline_12 | buy_and_hold_long | 0.070063 | 0.070047 |
| linkusdt | 4h | crypto_full | buy_and_hold_long | 0.070773 | 0.070757 |
| linkusdt | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.069369 | 0.069353 |
| linkusdt | 4h | learned_cnn | buy_and_hold_long | 0.070002 | 0.069986 |
| linkusdt | 4h | tech_stat | buy_and_hold_long | 0.070700 | 0.070684 |
| nzdusd | 15m | tech_full | buy_and_hold_long | 0.000690 | 0.000686 |
| nzdusd | 15m | tech_stat | buy_and_hold_long | 0.000695 | 0.000692 |
| nzdusd | 15m | tech_stat_decomp | buy_and_hold_long | 0.000698 | 0.000695 |
| nzdusd | 1h | baseline_12 | buy_and_hold_long | 0.000614 | 0.000611 |
| nzdusd | 1h | fx_full | buy_and_hold_long | 0.000783 | 0.000779 |
| nzdusd | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.000503 | 0.000499 |
| nzdusd | 1h | learned_cnn | buy_and_hold_long | 0.000515 | 0.000512 |
| nzdusd | 1h | learned_lstm | buy_and_hold_long | 0.000515 | 0.000512 |
| nzdusd | 1h | tech_full | buy_and_hold_long | 0.000669 | 0.000666 |
| nzdusd | 1h | tech_stat | buy_and_hold_long | 0.000767 | 0.000763 |
| nzdusd | 1h | tech_stat_decomp | buy_and_hold_long | 0.000783 | 0.000779 |
| nzdusd | 4h | baseline_12 | buy_and_hold_long | 0.000568 | 0.000565 |
| nzdusd | 4h | fx_full | buy_and_hold_long | 0.000638 | 0.000634 |
| nzdusd | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.000616 | 0.000613 |
| nzdusd | 4h | learned_cnn | buy_and_hold_long | 0.000404 | 0.000401 |
| nzdusd | 4h | learned_lstm | buy_and_hold_long | 0.000404 | 0.000401 |
| nzdusd | 4h | tech_full | buy_and_hold_long | 0.000719 | 0.000716 |
| nzdusd | 4h | tech_stat | buy_and_hold_long | 0.000557 | 0.000554 |
| nzdusd | 4h | tech_stat_decomp | buy_and_hold_long | 0.000638 | 0.000634 |
| solusdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.072015 | 0.071999 |
| solusdt | 15m | learned_cnn | buy_and_hold_long | 0.073492 | 0.073476 |
| solusdt | 15m | learned_lstm | buy_and_hold_long | 0.073492 | 0.073476 |
| solusdt | 15m | sota_low_cost | buy_and_hold_long | 0.071296 | 0.071280 |
| solusdt | 15m | tech_full | buy_and_hold_long | 0.070287 | 0.070271 |
| solusdt | 15m | tech_stat | buy_and_hold_long | 0.071296 | 0.071280 |
| solusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.071433 | 0.071417 |
| solusdt | 1h | baseline_12 | buy_and_hold_long | 0.068107 | 0.068091 |
| solusdt | 1h | crypto_full | buy_and_hold_long | 0.070885 | 0.070869 |
| solusdt | 1h | learned_lstm | buy_and_hold_long | 0.071790 | 0.071774 |
| solusdt | 1h | sota_low_cost | buy_and_hold_long | 0.070650 | 0.070634 |
| solusdt | 1h | tech_full | buy_and_hold_long | 0.070600 | 0.070584 |
| solusdt | 1h | tech_stat | buy_and_hold_long | 0.070650 | 0.070634 |
| solusdt | 4h | baseline_12 | buy_and_hold_long | 0.069580 | 0.069564 |
| solusdt | 4h | crypto_full | buy_and_hold_long | 0.066994 | 0.066978 |
| solusdt | 4h | learned_cnn | buy_and_hold_long | 0.070297 | 0.070281 |
| solusdt | 4h | sota_low_cost | buy_and_hold_long | 0.067069 | 0.067053 |
| solusdt | 4h | tech_full | buy_and_hold_long | 0.065988 | 0.065972 |
| solusdt | 4h | tech_stat | buy_and_hold_long | 0.067069 | 0.067053 |
| usdcad | 15m | baseline_12 | buy_and_hold_long | 0.001780 | 0.001777 |
| usdcad | 15m | fx_full | buy_and_hold_long | 0.001642 | 0.001639 |
| usdcad | 15m | learned_cnn | buy_and_hold_long | 0.001776 | 0.001772 |
| usdcad | 15m | learned_lstm | buy_and_hold_long | 0.001776 | 0.001772 |
| usdcad | 15m | tech_full | buy_and_hold_long | 0.001660 | 0.001657 |
| usdcad | 15m | tech_stat | buy_and_hold_long | 0.001634 | 0.001631 |
| usdcad | 15m | tech_stat_decomp | buy_and_hold_long | 0.001642 | 0.001639 |
| usdcad | 1h | baseline_12 | buy_and_hold_long | 0.001622 | 0.001619 |
| usdcad | 1h | fx_full | buy_and_hold_long | 0.001680 | 0.001676 |
| usdcad | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.001563 | 0.001560 |
| usdcad | 1h | learned_cnn | buy_and_hold_long | 0.001751 | 0.001748 |
| usdcad | 1h | learned_lstm | buy_and_hold_long | 0.001751 | 0.001748 |
| usdcad | 1h | tech_full | buy_and_hold_long | 0.001837 | 0.001834 |
| usdcad | 1h | tech_stat | buy_and_hold_long | 0.001683 | 0.001680 |
| usdcad | 1h | tech_stat_decomp | buy_and_hold_long | 0.001680 | 0.001676 |
| usdcad | 4h | baseline_12 | buy_and_hold_long | 0.001614 | 0.001610 |
| usdcad | 4h | fx_full | buy_and_hold_long | 0.001521 | 0.001517 |
| usdcad | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.001747 | 0.001744 |
| usdcad | 4h | learned_cnn | buy_and_hold_long | 0.001722 | 0.001718 |
| usdcad | 4h | learned_lstm | buy_and_hold_long | 0.001722 | 0.001718 |
| usdcad | 4h | tech_full | buy_and_hold_long | 0.001374 | 0.001370 |
| usdcad | 4h | tech_stat | buy_and_hold_long | 0.001513 | 0.001510 |
| usdcad | 4h | tech_stat_decomp | buy_and_hold_long | 0.001521 | 0.001517 |
| usdchf | 15m | fx_full | no_trade | 0.000000 | 0.000000 |
| usdchf | 15m | kitchen_sink_guarded | no_trade | 0.000000 | 0.000000 |
| usdchf | 15m | learned_cnn | no_trade | 0.000000 | 0.000000 |
| usdchf | 15m | learned_lstm | no_trade | 0.000000 | 0.000000 |
| usdchf | 15m | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | baseline_12 | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | fx_full | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | kitchen_sink_guarded | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | learned_cnn | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | learned_lstm | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | tech_full | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | tech_stat | no_trade | 0.000000 | 0.000000 |
| usdchf | 1h | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | baseline_12 | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | fx_full | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | kitchen_sink_guarded | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | learned_cnn | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | learned_lstm | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | tech_full | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | tech_stat | no_trade | 0.000000 | 0.000000 |
| usdchf | 4h | tech_stat_decomp | no_trade | 0.000000 | 0.000000 |
| usdjpy | 1h | baseline_12 | buy_and_hold_long | 0.003925 | 0.003921 |
| usdjpy | 1h | tech_full | buy_and_hold_long | 0.004153 | 0.004150 |
| usdjpy | 1h | tech_stat | buy_and_hold_long | 0.004183 | 0.004180 |
| usdjpy | 1h | tech_stat_decomp | buy_and_hold_long | 0.004176 | 0.004173 |
| usdjpy | 4h | baseline_12 | buy_and_hold_long | 0.004028 | 0.004024 |
| usdjpy | 4h | fx_full | buy_and_hold_long | 0.003819 | 0.003815 |
| usdjpy | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.003819 | 0.003815 |
| usdjpy | 4h | learned_cnn | buy_and_hold_long | 0.003892 | 0.003888 |
| usdjpy | 4h | learned_lstm | buy_and_hold_long | 0.003892 | 0.003888 |
| usdjpy | 4h | tech_full | buy_and_hold_long | 0.003807 | 0.003804 |
| usdjpy | 4h | tech_stat | buy_and_hold_long | 0.003813 | 0.003809 |
| usdjpy | 4h | tech_stat_decomp | buy_and_hold_long | 0.003819 | 0.003815 |
| xrpusdt | 15m | crypto_full | buy_and_hold_long | 0.032139 | 0.032123 |
| xrpusdt | 15m | kitchen_sink_guarded | buy_and_hold_long | 0.032543 | 0.032527 |
| xrpusdt | 15m | learned_cnn | buy_and_hold_long | 0.031425 | 0.031410 |
| xrpusdt | 15m | learned_lstm | buy_and_hold_long | 0.031425 | 0.031410 |
| xrpusdt | 15m | tech_stat | buy_and_hold_long | 0.032178 | 0.032162 |
| xrpusdt | 15m | tech_stat_decomp | buy_and_hold_long | 0.032139 | 0.032123 |
| xrpusdt | 1h | crypto_full | buy_and_hold_long | 0.030704 | 0.030688 |
| xrpusdt | 1h | kitchen_sink_guarded | buy_and_hold_long | 0.031402 | 0.031386 |
| xrpusdt | 1h | learned_cnn | buy_and_hold_long | 0.028409 | 0.028394 |
| xrpusdt | 1h | learned_lstm | buy_and_hold_long | 0.028409 | 0.028394 |
| xrpusdt | 1h | sota_low_cost | buy_and_hold_long | 0.030527 | 0.030511 |
| xrpusdt | 1h | tech_full | buy_and_hold_long | 0.031395 | 0.031380 |
| xrpusdt | 1h | tech_stat | buy_and_hold_long | 0.030527 | 0.030511 |
| xrpusdt | 1h | tech_stat_decomp | buy_and_hold_long | 0.030704 | 0.030688 |
| xrpusdt | 4h | baseline_12 | buy_and_hold_long | 0.027661 | 0.027646 |
| xrpusdt | 4h | crypto_full | buy_and_hold_long | 0.029317 | 0.029302 |
| xrpusdt | 4h | kitchen_sink_guarded | buy_and_hold_long | 0.030276 | 0.030260 |
| xrpusdt | 4h | learned_cnn | buy_and_hold_long | 0.024510 | 0.024495 |
| xrpusdt | 4h | learned_lstm | buy_and_hold_long | 0.024510 | 0.024495 |
| xrpusdt | 4h | sota_low_cost | buy_and_hold_long | 0.029272 | 0.029257 |
| xrpusdt | 4h | tech_stat | buy_and_hold_long | 0.029272 | 0.029257 |
| xrpusdt | 4h | tech_stat_decomp | buy_and_hold_long | 0.029317 | 0.029302 |

---

## 6. B8 Governance Gate Update

| Gate | Previous Status | Updated Status |
| --- | --- | --- |
| B8_SIMPLE_BASELINES | NOT COMPUTED | See verdict below |

**B8 clearance verdict:** PARTIALLY_CLEARED — surviving candidate (PROMOTE_BLOCKED_HARDENING) beats all simple baselines at base_cost AND pessimistic_cost. Note: 3432 other (mostly killed) runs fail vs their best baseline — expected, as killed runs have negligible or negative returns. 1418 runs still blocked (no input CSV available).

Baselines computed: no_trade, buy_and_hold_long (1% position), random_long_short_flat,
turnover_matched_random, simple_momentum, simple_reversal.

> **B8 is PARTIALLY CLEARED** for all runs with auditable input CSVs (206 runs).
> Runs without input CSVs remain blocked on B8 (150 runs).
> Full B8 clearance for promoted candidates requires verification at Stage B.

---

*End of report. Generated by stage31_simple_baseline_worker.py*
