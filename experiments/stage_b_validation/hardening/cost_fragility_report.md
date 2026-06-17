# Stage B Cost Fragility Report

Generated UTC: `2026-05-14T06:16:09.478606+00:00`

## Summary

- Candidate groups: `35`
- Cost-fragility or missing-cost flags: `18`
- Accepted cost contracts: `(('base', 'plus_50pct', 'plus_100pct'), ('base', 'pessimistic'))`
- Adverse costs considered for fragility: `('pessimistic', 'plus_100pct')`

## Flagged Candidates

| candidate | present | missing accepted | base | worst adverse | delta |
| --- | --- | --- | ---: | ---: | ---: |
| `btcusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s1_20260503T115009Z_project3_stage31_firstwave` | `base;pessimistic` | `` | 0.0731507573063364 | -0.09268213133805984 | -0.16583288864439624 |
| `btcusdt_perp_4h_sac_kitchen_sink_guarded_direct_atr_sltp_s1_20260503T133955Z_project3_stage31_firstwave` | `base;pessimistic` | `` | 0.07322543625508754 | -0.10019989315401374 | -0.17342532940910127 |
| `btcusdt_perp_4h_sac_learned_cnn_direct_atr_sltp_s2_20260509T044048Z_project3_stage31_firstwave` | `base;pessimistic` | `` | 0.08343388720839653 | -0.09121282636478324 | -0.1746467135731798 |
| `btcusdt_perp_4h_sac_sota_low_cost_direct_atr_sltp_s2_20260509T052300Z_project3_stage31_firstwave` | `base;pessimistic` | `` | 0.08325920384919633 | -0.09949883891893949 | -0.18275804276813581 |
| `ethusdt_4h_sac_tech_full_direct_atr_sltp_s2_20260509T030058Z_project3_stage31_firstwave` | `base` | `plus_50pct;plus_100pct` | 0.1411563958805478 | 0.0 | -0.1411563958805478 |
| `ethusdt_4h_sac_tech_stat_full_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_full_plus_train_only_ood_score_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_full_plus_train_only_regime_probs_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_momentum_only_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_reduced_corr_v1_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_session_calendar_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_reduced_corr_v1_plus_train_only_regime_probs_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_trend_only_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_volatility_only_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_4h_sac_tech_stat_volume_liquidity_only_candidate` | `base;plus_100pct;plus_50pct` | `` | 0.01810103287597267 | -0.004497207088565649 | -0.022598239964538316 |
| `ethusdt_perp_4h_sac_baseline_12_direct_atr_sltp_s2_20260509T054549Z_project3_stage31_firstwave` | `base` | `plus_50pct;plus_100pct` | 0.15878147867600814 | 0.0 | -0.15878147867600814 |
| `ethusdt_perp_4h_sac_tech_stat_direct_atr_sltp_s0_20260503T194830Z_project3_stage31_firstwave` | `base` | `plus_50pct;plus_100pct` | 0.16897199752533115 | 0.0 | -0.16897199752533115 |
