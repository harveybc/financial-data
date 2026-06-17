# Project 3 Stage B Run Plan — ethusdt_4h_sac_baseline_12_plus_session_calendar

- schema_version: `project3_stageb_run_plan_v1`
- generated_at: 2026-05-13T20:25:51Z
- algorithm: `sac`
- asset: `ETHUSDT` timeframe: `4h`
- feature_preset: `baseline_12_plus_session_calendar`
- heldout_start: `2025-01-01`
- stage_c_access: **DENIED**
- training_launched: **False**
- seeds: [0, 1, 2, 3, 4]
- cost_scenarios: ['base', 'plus_50pct', 'plus_100pct']
- baselines: ['no_trade', 'buy_and_hold', 'random', 'momentum', 'reversal']
- promotion_eligible: **True**

## Configs (90)

| role | baseline | seed | cost | config |
|------|----------|------|------|--------|
| candidate |  | 0 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s0_base.json` |
| baseline | no_trade | 0 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s0_base.json` |
| baseline | buy_and_hold | 0 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s0_base.json` |
| baseline | random | 0 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s0_base.json` |
| baseline | momentum | 0 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s0_base.json` |
| baseline | reversal | 0 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s0_base.json` |
| candidate |  | 0 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s0_plus_50pct.json` |
| baseline | no_trade | 0 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s0_plus_50pct.json` |
| baseline | buy_and_hold | 0 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s0_plus_50pct.json` |
| baseline | random | 0 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s0_plus_50pct.json` |
| baseline | momentum | 0 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s0_plus_50pct.json` |
| baseline | reversal | 0 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s0_plus_50pct.json` |
| candidate |  | 0 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s0_plus_100pct.json` |
| baseline | no_trade | 0 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s0_plus_100pct.json` |
| baseline | buy_and_hold | 0 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s0_plus_100pct.json` |
| baseline | random | 0 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s0_plus_100pct.json` |
| baseline | momentum | 0 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s0_plus_100pct.json` |
| baseline | reversal | 0 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s0_plus_100pct.json` |
| candidate |  | 1 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s1_base.json` |
| baseline | no_trade | 1 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s1_base.json` |
| baseline | buy_and_hold | 1 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s1_base.json` |
| baseline | random | 1 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s1_base.json` |
| baseline | momentum | 1 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s1_base.json` |
| baseline | reversal | 1 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s1_base.json` |
| candidate |  | 1 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s1_plus_50pct.json` |
| baseline | no_trade | 1 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s1_plus_50pct.json` |
| baseline | buy_and_hold | 1 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s1_plus_50pct.json` |
| baseline | random | 1 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s1_plus_50pct.json` |
| baseline | momentum | 1 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s1_plus_50pct.json` |
| baseline | reversal | 1 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s1_plus_50pct.json` |
| candidate |  | 1 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s1_plus_100pct.json` |
| baseline | no_trade | 1 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s1_plus_100pct.json` |
| baseline | buy_and_hold | 1 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s1_plus_100pct.json` |
| baseline | random | 1 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s1_plus_100pct.json` |
| baseline | momentum | 1 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s1_plus_100pct.json` |
| baseline | reversal | 1 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s1_plus_100pct.json` |
| candidate |  | 2 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s2_base.json` |
| baseline | no_trade | 2 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s2_base.json` |
| baseline | buy_and_hold | 2 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s2_base.json` |
| baseline | random | 2 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s2_base.json` |
| baseline | momentum | 2 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s2_base.json` |
| baseline | reversal | 2 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s2_base.json` |
| candidate |  | 2 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s2_plus_50pct.json` |
| baseline | no_trade | 2 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s2_plus_50pct.json` |
| baseline | buy_and_hold | 2 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s2_plus_50pct.json` |
| baseline | random | 2 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s2_plus_50pct.json` |
| baseline | momentum | 2 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s2_plus_50pct.json` |
| baseline | reversal | 2 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s2_plus_50pct.json` |
| candidate |  | 2 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s2_plus_100pct.json` |
| baseline | no_trade | 2 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s2_plus_100pct.json` |
| baseline | buy_and_hold | 2 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s2_plus_100pct.json` |
| baseline | random | 2 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s2_plus_100pct.json` |
| baseline | momentum | 2 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s2_plus_100pct.json` |
| baseline | reversal | 2 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s2_plus_100pct.json` |
| candidate |  | 3 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s3_base.json` |
| baseline | no_trade | 3 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s3_base.json` |
| baseline | buy_and_hold | 3 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s3_base.json` |
| baseline | random | 3 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s3_base.json` |
| baseline | momentum | 3 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s3_base.json` |
| baseline | reversal | 3 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s3_base.json` |
| candidate |  | 3 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s3_plus_50pct.json` |
| baseline | no_trade | 3 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s3_plus_50pct.json` |
| baseline | buy_and_hold | 3 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s3_plus_50pct.json` |
| baseline | random | 3 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s3_plus_50pct.json` |
| baseline | momentum | 3 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s3_plus_50pct.json` |
| baseline | reversal | 3 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s3_plus_50pct.json` |
| candidate |  | 3 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s3_plus_100pct.json` |
| baseline | no_trade | 3 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s3_plus_100pct.json` |
| baseline | buy_and_hold | 3 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s3_plus_100pct.json` |
| baseline | random | 3 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s3_plus_100pct.json` |
| baseline | momentum | 3 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s3_plus_100pct.json` |
| baseline | reversal | 3 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s3_plus_100pct.json` |
| candidate |  | 4 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s4_base.json` |
| baseline | no_trade | 4 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s4_base.json` |
| baseline | buy_and_hold | 4 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s4_base.json` |
| baseline | random | 4 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s4_base.json` |
| baseline | momentum | 4 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s4_base.json` |
| baseline | reversal | 4 | base | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s4_base.json` |
| candidate |  | 4 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s4_plus_50pct.json` |
| baseline | no_trade | 4 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s4_plus_50pct.json` |
| baseline | buy_and_hold | 4 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s4_plus_50pct.json` |
| baseline | random | 4 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s4_plus_50pct.json` |
| baseline | momentum | 4 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s4_plus_50pct.json` |
| baseline | reversal | 4 | plus_50pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s4_plus_50pct.json` |
| candidate |  | 4 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_candidate_s4_plus_100pct.json` |
| baseline | no_trade | 4 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_no_trade_s4_plus_100pct.json` |
| baseline | buy_and_hold | 4 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_buy_and_hold_s4_plus_100pct.json` |
| baseline | random | 4 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_random_s4_plus_100pct.json` |
| baseline | momentum | 4 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_momentum_s4_plus_100pct.json` |
| baseline | reversal | 4 | plus_100pct | `stageb_ethusdt_4h_sac_baseline_12_plus_session_calendar_baseline_reversal_s4_plus_100pct.json` |

> NOTE: every emitted config is locked with `_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED: true` and `stage_c_access: DENIED`. This tool never launches training.
