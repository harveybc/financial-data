# Stage 3.1 Leakage Audit

Updated: 2026-05-02

## Purpose

This checklist is now a P0 hardening gate. Stage A smoke/screening jobs may run to keep machines productive, but no result can be promoted to Stage B until the relevant rows in this audit pass or have an explicit Tier 4 exception.

## Required Tests

| Test id | Scope | Pass condition | Blocker |
| --- | --- | --- | --- |
| `heldout_timestamp_exclusion` | All Stage A/B training inputs | No rows from `2025-01-01` onward in train/validation fitting data | Yes |
| `transform_fit_window_check` | Any fitted transform | Fit end timestamp precedes the validation/held-out window it is evaluated on | Yes |
| `scaler_fit_window_check` | Scalers/normalizers/imputers | Statistics fit on training split only unless explicitly labeled transductive research | Yes |
| `autoencoder_fit_window_check` | LSTM/CNN/transformer/CVAE/VAE embeddings | Encoder training excludes 2025 and records train window, assets, columns, and seed | Yes |
| `hmm_regime_fit_window_check` | HMM/regime features | HMM model fit excludes 2025 and emits model metadata | Yes |
| `macro_vintage_check` | Macro/calendar features | Vintage or release-lag policy is documented in `features/AVAILABILITY_CONTRACT.md` terms | Yes |
| `forward_fill_availability_check` | Forward-filled cross-source features | Source age/staleness features are available or family is blocked from promotion | Yes |
| `negative_control_random_label_check` | Stage A report | Randomized target/control does not show promotion-grade edge | Stage B blocker |
| `feature_time_shift_sanity_check` | Stage A report | Positive time-shifted/future-shifted features do not outperform causal features | Stage B blocker |
| `post_cutoff_feature_audit` | Stage B/C candidates | No feature columns, fitted metadata, or source files include post-cutoff calibration | Yes |

## Fitted Transform Metadata

Every fitted transform used by a promoted candidate must expose:

```yaml
transform_id: string
feature_family: string
fit_start_timestamp: timestamp
fit_end_timestamp: timestamp
fit_assets: list
fit_timeframes: list
fit_columns: list
fit_excludes_heldout_2025: true
fit_excludes_validation_if_required: true|false
random_seed: int|null
software_version: string
input_manifest_hash: string
output_manifest_hash: string
```

## Promotion Rule

Any P0 leakage failure changes the candidate verdict to `blocked_leakage_review`. It may remain in Stage A exploratory reports, but it cannot be ranked as a valid Stage B candidate.
