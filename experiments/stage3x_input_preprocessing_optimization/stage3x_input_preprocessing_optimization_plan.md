# Stage 3X Input / Preprocessing / Representation Optimization Plan

Generated UTC: `2026-05-18T01:29:59.518113+00:00`

## Decision

Do not spend another broad GPU batch on the same feature/preprocessing contract. The next step is a CPU-first selection protocol that proves which inputs and preprocessing settings deserve counted RL trials.

- Stage C access: `DENIED`
- Training launched: `False`
- Planned diagnostic cells: `56`
- Selected feature variants: `8`
- Preprocessing profiles: `7`

## Hard Gates Before More GPU

- `D1_feature_contract` (hard): all new evidence has non-null feature_list_hash and observation_state_hash
- `D2_redundancy_stability` (hard): near-constant and highly redundant features are explicitly tagged
- `D3_target_relation_screen` (hard): candidate feature groups show nonzero train-to-validation stable relation to future returns
- `D4_preprocessing_ablation` (hard): scaling/window/clip choices selected from train/validation diagnostics, not preference
- `D5_representation_research` (research): only train-row pretraining proposals become counted trials

## Matrix

| cell_id | source_variant | profile | scaling | window | clip | obs_window |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `tech_stat_full__p00_current_contract` | `tech_stat_full` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_full__p01_no_scaling_control` | `tech_stat_full` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_full__p02_rolling_short_64` | `tech_stat_full` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_full__p03_rolling_long_512` | `tech_stat_full` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_full__p04_expanding_zscore` | `tech_stat_full` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_full__p05_clip_tight_5` | `tech_stat_full` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_full__p06_wide_observation_64` | `tech_stat_full` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_reduced_corr_v1__p00_current_contract` | `tech_stat_reduced_corr_v1` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_reduced_corr_v1__p01_no_scaling_control` | `tech_stat_reduced_corr_v1` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_reduced_corr_v1__p02_rolling_short_64` | `tech_stat_reduced_corr_v1` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_reduced_corr_v1__p03_rolling_long_512` | `tech_stat_reduced_corr_v1` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_reduced_corr_v1__p04_expanding_zscore` | `tech_stat_reduced_corr_v1` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_reduced_corr_v1__p05_clip_tight_5` | `tech_stat_reduced_corr_v1` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_reduced_corr_v1__p06_wide_observation_64` | `tech_stat_reduced_corr_v1` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_trend_only__p00_current_contract` | `tech_stat_trend_only` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_trend_only__p01_no_scaling_control` | `tech_stat_trend_only` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_trend_only__p02_rolling_short_64` | `tech_stat_trend_only` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_trend_only__p03_rolling_long_512` | `tech_stat_trend_only` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_trend_only__p04_expanding_zscore` | `tech_stat_trend_only` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_trend_only__p05_clip_tight_5` | `tech_stat_trend_only` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_trend_only__p06_wide_observation_64` | `tech_stat_trend_only` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_momentum_only__p00_current_contract` | `tech_stat_momentum_only` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_momentum_only__p01_no_scaling_control` | `tech_stat_momentum_only` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_momentum_only__p02_rolling_short_64` | `tech_stat_momentum_only` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_momentum_only__p03_rolling_long_512` | `tech_stat_momentum_only` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_momentum_only__p04_expanding_zscore` | `tech_stat_momentum_only` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_momentum_only__p05_clip_tight_5` | `tech_stat_momentum_only` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_momentum_only__p06_wide_observation_64` | `tech_stat_momentum_only` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_volatility_only__p00_current_contract` | `tech_stat_volatility_only` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_volatility_only__p01_no_scaling_control` | `tech_stat_volatility_only` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_volatility_only__p02_rolling_short_64` | `tech_stat_volatility_only` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_volatility_only__p03_rolling_long_512` | `tech_stat_volatility_only` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_volatility_only__p04_expanding_zscore` | `tech_stat_volatility_only` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_volatility_only__p05_clip_tight_5` | `tech_stat_volatility_only` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_volatility_only__p06_wide_observation_64` | `tech_stat_volatility_only` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_volume_liquidity_only__p00_current_contract` | `tech_stat_volume_liquidity_only` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_volume_liquidity_only__p01_no_scaling_control` | `tech_stat_volume_liquidity_only` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_volume_liquidity_only__p02_rolling_short_64` | `tech_stat_volume_liquidity_only` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_volume_liquidity_only__p03_rolling_long_512` | `tech_stat_volume_liquidity_only` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_volume_liquidity_only__p04_expanding_zscore` | `tech_stat_volume_liquidity_only` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_volume_liquidity_only__p05_clip_tight_5` | `tech_stat_volume_liquidity_only` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_volume_liquidity_only__p06_wide_observation_64` | `tech_stat_volume_liquidity_only` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_full_plus_train_only_regime_probs__p00_current_contract` | `tech_stat_full_plus_train_only_regime_probs` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_full_plus_train_only_regime_probs__p01_no_scaling_control` | `tech_stat_full_plus_train_only_regime_probs` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_full_plus_train_only_regime_probs__p02_rolling_short_64` | `tech_stat_full_plus_train_only_regime_probs` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_full_plus_train_only_regime_probs__p03_rolling_long_512` | `tech_stat_full_plus_train_only_regime_probs` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_full_plus_train_only_regime_probs__p04_expanding_zscore` | `tech_stat_full_plus_train_only_regime_probs` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_full_plus_train_only_regime_probs__p05_clip_tight_5` | `tech_stat_full_plus_train_only_regime_probs` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_full_plus_train_only_regime_probs__p06_wide_observation_64` | `tech_stat_full_plus_train_only_regime_probs` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |
| `tech_stat_full_plus_train_only_ood_score__p00_current_contract` | `tech_stat_full_plus_train_only_ood_score` | `p00_current_contract` | `rolling_zscore` | 256 | 10 | 32 |
| `tech_stat_full_plus_train_only_ood_score__p01_no_scaling_control` | `tech_stat_full_plus_train_only_ood_score` | `p01_no_scaling_control` | `none` | 0 | 0 | 32 |
| `tech_stat_full_plus_train_only_ood_score__p02_rolling_short_64` | `tech_stat_full_plus_train_only_ood_score` | `p02_rolling_short_64` | `rolling_zscore` | 64 | 10 | 32 |
| `tech_stat_full_plus_train_only_ood_score__p03_rolling_long_512` | `tech_stat_full_plus_train_only_ood_score` | `p03_rolling_long_512` | `rolling_zscore` | 512 | 10 | 32 |
| `tech_stat_full_plus_train_only_ood_score__p04_expanding_zscore` | `tech_stat_full_plus_train_only_ood_score` | `p04_expanding_zscore` | `expanding_zscore` | 0 | 10 | 32 |
| `tech_stat_full_plus_train_only_ood_score__p05_clip_tight_5` | `tech_stat_full_plus_train_only_ood_score` | `p05_clip_tight_5` | `rolling_zscore` | 256 | 5 | 32 |
| `tech_stat_full_plus_train_only_ood_score__p06_wide_observation_64` | `tech_stat_full_plus_train_only_ood_score` | `p06_wide_observation_64` | `rolling_zscore` | 256 | 10 | 64 |

## Non-Negotiables

- Stage C remains locked; no 2025-01-01+ rows are used for selection.
- PPO/SAC/DQN algorithms remain fixed; this plan selects inputs and preprocessing.
- Any future RL smoke or Stage B run is a counted trial in the ledger.
- CryptoQuant stays cancelled unless a free/paid-source coverage audit proves it is uniquely needed.
