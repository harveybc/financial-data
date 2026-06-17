# Stage B Data Context Gap Audit

Generated UTC: `2026-05-13T20:10:49.836632+00:00`

- Stage C touched: `False`
- Heldout boundary: `2025-01-01`
- Sample model-ready file: `/home/harveybc/Documents/GitHub/preprocessor/examples/data/ethusdt_4h_tech_stat_full_model_ready.csv`
- Sample model-ready calendar columns: `0`
- Stage B configs with Friday 20:00 force-close: `900`
- Diagnostic variants with session/calendar columns: `3`
- Diagnostic variants with paid-source columns: `0`

## Gaps

- `MODEL_READY_DATA_LACKS_EXPLICIT_TIME_TO_FRIDAY_CONTEXT`
- `OBSERVATION_STATE_LACKS_BARS_TO_FORCE_CLOSE_CONTEXT`
- `PAID_CRYPTOQUANT_SHADOW_PLAN_NOT_IN_STAGEB_DIAGNOSTIC_VARIANTS`

## Observation Context

- `position`: `True`
- `equity_norm`: `True`
- `unrealized_pnl_norm`: `True`
- `steps_remaining_norm`: `True`
- `bars_to_force_close`: `False`
- `hours_to_force_close`: `False`

## Diagnostic Variants

| variant | columns | calendar cols | paid/source cols |
| --- | ---: | ---: | ---: |
| `baseline_12` | 18 | 0 | 0 |
| `baseline_12_plus_session_calendar` | 37 | 19 | 0 |
| `tech_stat_full` | 89 | 0 | 0 |
| `tech_stat_full_plus_session_calendar` | 108 | 19 | 0 |
| `tech_stat_full_plus_train_only_ood_score` | 90 | 0 | 0 |
| `tech_stat_full_plus_train_only_regime_probs` | 93 | 0 | 0 |
| `tech_stat_momentum_only` | 18 | 0 | 0 |
| `tech_stat_reduced_corr_v1` | 56 | 0 | 0 |
| `tech_stat_reduced_corr_v1_plus_session_calendar` | 75 | 19 | 0 |
| `tech_stat_reduced_corr_v1_plus_train_only_regime_probs` | 60 | 0 | 0 |
| `tech_stat_trend_only` | 30 | 0 | 0 |
| `tech_stat_volatility_only` | 21 | 0 | 0 |
| `tech_stat_volume_liquidity_only` | 13 | 0 | 0 |

## Recommended Next Tasks

- Keep the Friday force-close rule, but add deterministic session/calendar context to candidate feature lists.
- Add bars/hours-to-force-close observation-state support in agent-multi/gym-fx if the CSV calendar columns are not enough.
- Build a paid-source diagnostic lane that compares best free feature stack against free-plus-CryptoQuant using matched asset/timeframe/seed/cost cells.
- Treat specialized open/close policy decomposition as a new strategy-family research lane, not as a silent change to the fixed PPO/SAC/DQN comparison.
