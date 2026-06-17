# Project 3 Stage B Run Plan Status

Generated UTC: `2026-05-13T19:26:18.309733+00:00`
Plan ID: `stageb_pragmatic_ethusdt_4h_sac_diagnostic_v1`
Total configs: `900`
No-trade anomaly threshold: `20.0%`

## Status Counts

- `DONE`: 900

## Anomaly Counts

- `NO_TRADES_AFTER_20_PERCENT`: 600

## Warning Counts

- None

## Final Trace Gates

- No-trade hard fail: `final_trades_total <= 0` when trace exists.
- Excessive-trade warning: `>312.0` trades/year.
- Excessive-trade hard fail: `>730.0` trades/year.
- Always-in-market hard fail when losing: exposure `>=0.95` and final return `<= 0`.

## Running Or Anomalous Rows

| Variant | Status | Progress % | Live Trades | Return | Final Trades/Yr | Exposure | Anomalies | Warnings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| candidate_baseline_12_s0_base | DONE | 100.0 | 52106 | 0.014062325990111146 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s0_plus_50pct | DONE | 100.0 | 52106 | 0.014062325990111146 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s0_plus_100pct | DONE | 100.0 | 48198 | -0.010622681668281286 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s0_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s0_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s0_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s0_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s0_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s1_base | DONE | 100.0 | 52544 | 0.14266095230711673 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s1_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s1_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s1_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s1_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s1_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s1_plus_50pct | DONE | 100.0 | 55785 | -0.015042955696805582 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s1_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s1_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s1_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s1_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s1_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s1_plus_100pct | DONE | 100.0 | 61713 | 0.11479515354569059 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s1_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s1_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s1_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s1_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s1_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s2_base | DONE | 100.0 | 64629 | 0.040513788324950006 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s2_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s2_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s2_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s2_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s2_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s2_plus_50pct | DONE | 100.0 | 49795 | -0.017996971410488505 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s2_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s2_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s2_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s2_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s2_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s2_plus_100pct | DONE | 100.0 | 64629 | 0.040513788324950006 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s2_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s2_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s2_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s2_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s2_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s3_base | DONE | 100.0 | 40237 | 0.06198474597511883 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s3_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s3_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s3_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s3_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s3_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s3_plus_50pct | DONE | 100.0 | 40310 | 0.06310139541595827 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s3_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s3_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s3_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s3_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s3_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s3_plus_100pct | DONE | 100.0 | 40507 | 0.06198474597511883 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s3_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s3_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s3_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s3_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s3_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s4_base | DONE | 100.0 | 59459 | 0.1578318228497917 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s4_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s4_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s4_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s4_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s4_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s4_plus_50pct | DONE | 100.0 | 46771 | 0.03445065768348643 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s4_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s4_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s4_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s4_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s4_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_baseline_12_s4_plus_100pct | DONE | 100.0 | 43835 | 0.03313506699231383 | 0.0 | 0.0 |  |  |
| baseline_no_trade_baseline_12_s4_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_baseline_12_s4_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_baseline_12_s4_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_baseline_12_s4_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_baseline_12_s4_plus_100pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_tech_stat_full_s0_base | DONE | 100.0 | 46750 | -0.06071410643151809 | 0.0 | 0.0 |  |  |
| baseline_no_trade_tech_stat_full_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_tech_stat_full_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_tech_stat_full_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_momentum_tech_stat_full_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_reversal_tech_stat_full_s0_base | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| candidate_tech_stat_full_s0_plus_50pct | DONE | 100.0 | 49609 | -0.05452132894059247 | 0.0 | 0.0 |  |  |
| baseline_no_trade_tech_stat_full_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 |  |  |
| baseline_buy_and_hold_tech_stat_full_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
| baseline_random_tech_stat_full_s0_plus_50pct | DONE | 100.0 | 0 | 0.0 | 0.0 | 0.0 | NO_TRADES_AFTER_20_PERCENT |  |
