# Stage B Feature/Action Audit

Generated UTC: `2026-05-14T22:55:20.993806+00:00`

This is a diagnosis artifact only. It does not approve Stage C.

## Summary

- `top_n`: `12`
- `audited_candidates`: `13`
- `feature_list_hash_missing_candidates`: `12`
- `distinct_data_hashes`: `12`
- `identical_performance_signature_groups`: `1`
- `largest_identical_performance_group`: `11`
- `paired_calendar_pairs_count`: `2`
- `paired_calendar_identical_signature_count`: `2`
- `force_close_obs_pairs_count`: `2`
- `force_close_obs_behavior_changed_count`: `2`
- `force_close_obs_friday_exposure_improved_count`: `2`
- `force_close_obs_contract_ok`: `True`
- `stage_c_allowed`: `False`

## Warnings

- feature_list_hash is missing for one or more top candidates; agent-multi evidence contract should persist a deterministic hash.
- Session-calendar columns produced identical action and trade signatures vs. matched non-calendar variants for every audited pair; the policy is not consuming the calendar features.
- At least one audited candidate emits two or fewer distinct rounded actions across OOS; check action deadband / squashing in agent-multi.

## Audited Candidates

| Rank | Candidate | Columns | Calendar Cols | Missing Feature Hash | Missing Obs Hash | Force Obs OK | Mean Trades OOS | Mean Exposure | Action Std | Action Entropy | Flip Rate | Fri-late Exp | Same-Perf Clue |
| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | `ethusdt_4h_sac_tech_stat_full_candidate` | 89 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 2 | `ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate` | 108 | 19 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 3 | `ethusdt_4h_sac_tech_stat_full_plus_train_only_ood_score_candidate` | 90 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 4 | `ethusdt_4h_sac_tech_stat_full_plus_train_only_regime_probs_candidate` | 93 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 5 | `ethusdt_4h_sac_tech_stat_momentum_only_candidate` | 18 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 6 | `ethusdt_4h_sac_tech_stat_reduced_corr_v1_candidate` | 56 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 7 | `ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_session_calendar_candidate` | 75 | 19 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 8 | `ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_train_only_regime_probs_candidate` | 60 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 9 | `ethusdt_4h_sac_tech_stat_trend_only_candidate` | 30 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 10 | `ethusdt_4h_sac_tech_stat_volatility_only_candidate` | 21 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 11 | `ethusdt_4h_sac_tech_stat_volume_liquidity_only_candidate` | 13 | 0 | `True` | `True` | `False` | 368.13 | 0.5122 | 0.095240 | 9.4123 | 0.1415 | 0.8247 | yes |
| 12 | `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s1_20260503T195207Z_project3_stage31_firstwave` | 89 | 0 | `True` | `True` | `False` | 165.00 | 0.9794 | 0.000000 | 0.0000 | 0.0379 | 0.9928 |  |
| 33 | `ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate` | 89 | 0 | `False` | `False` | `True` | 308.07 | 0.4089 | 0.077138 | 6.4620 | 0.1148 | 0.6731 |  |

## Paired Calendar vs Non-Calendar Compare

| Calendar slug | Non-calendar partner | Δ action std | Δ action entropy | Δ trades OOS | Δ flip rate | Δ Fri-late exposure | Identical action sig |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate` | `ethusdt_4h_sac_tech_stat_full_candidate` | +0.000000 | +0.000000 | +0.0000 | +0.000000 | +0.000000 | `True` |
| `ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_session_calendar_candidate` | `ethusdt_4h_sac_tech_stat_reduced_corr_v1_candidate` | +0.000000 | +0.000000 | +0.0000 | +0.000000 | +0.000000 | `True` |

## Force-Close Observation Compare

| Force-close slug | Partner | Partner type | Contract OK | Δ action std | Δ action entropy | Δ trades OOS | Δ flip rate | Δ Fri-late exposure | Behavior changed | Fri-late exposure improved |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate` | `ethusdt_4h_sac_tech_stat_full_candidate` | non_calendar | `True` | -0.018102 | -2.950309 | -60.0667 | -0.026728 | -0.151603 | `True` | `True` |
| `ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate` | `ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate` | session_calendar | `True` | -0.018102 | -2.950309 | -60.0667 | -0.026728 | -0.151603 | `True` | `True` |

## Findings

- Distinct data hashes with identical ranking metrics indicate the run plan did not collapse to one file, but policy behavior may be insensitive to feature differences.
- Missing `feature_list_hash` in legacy evidence is an evidence-contract gap; repaired force-close evidence must carry both feature and observation hashes.
- If action statistics are near-identical across variants, the next fix belongs in observation/action/reward diagnostics before another broad GPU matrix.
