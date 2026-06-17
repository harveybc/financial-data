# Stage B Pragmatic Diagnostic Manifest

Experiment: `stageb_ethusdt_4h_sac_pragmatic_diagnostic_v1`

## Lock State

- Stage C allowed: `False`
- Stage C access: `DENIED`
- Training launch allowed by this manifest: `False`
- Heldout boundary: `2025-01-01`

## Matrix

- Target: `ETHUSDT 4h SAC`
- Seeds: `[0, 1, 2, 3, 4]`
- Cost scenarios: `['base', 'plus_50pct', 'plus_100pct']`
- Feature variants: `10`
- Planned run cells: `150`

| variant | status | question |
| --- | --- | --- |
| `baseline_12` | `materialized_preheldout` | Does the candidate beat a compact OHLCV baseline? |
| `tech_stat_full` | `materialized_preheldout` | Does the broad technical/statistical family still carry signal? |
| `tech_stat_reduced_corr_v1` | `materialized_preheldout` | Is the full tech_stat family too redundant/noisy? |
| `tech_stat_volatility_only` | `materialized_preheldout` | Are volatility features driving useful behavior? |
| `tech_stat_trend_only` | `materialized_preheldout` | Are trend features driving useful behavior? |
| `tech_stat_momentum_only` | `materialized_preheldout` | Are momentum features driving useful behavior? |
| `tech_stat_volume_liquidity_only` | `materialized_preheldout` | Are volume/liquidity features driving useful behavior? |
| `tech_stat_full_plus_train_only_regime_probs` | `materialized_preheldout` | Do train-only regime probabilities reduce bad exposure? |
| `tech_stat_reduced_corr_v1_plus_train_only_regime_probs` | `materialized_preheldout` | Do regime probabilities help after redundancy reduction? |
| `tech_stat_full_plus_train_only_ood_score` | `materialized_preheldout` | Can train-only OOD state reduce overtrading/drawdown? |

## Hard Blocks Before Training

- `stage_b_operator_approval_missing`

This packet is diagnostic-only. It does not unlock Stage C and every
resulting run cell must be counted as a new trial in downstream DSR/PBO
accounting.
