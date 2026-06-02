# Stage 3X Market-State Causal Contract

- schema_version: `project3_stage3x_market_state_causal_contract_v1`
- ok: `true`
- stage_c_access: `DENIED`
- training_launched: `false`
- pretrade_gap_hours: `12`
- lookback_hours: `168`
- state_encoding_mode: `snapshot`
- rows: `12`
- temporal_issue_count: `0`

## Role Mapping

- `patient`: target_asset_at_weekly_anchor
- `patient_state`: market_state_observed_before_decision_cutoff
- `medicine`: observed_input_or_supervisor_exposure_defined_before_cutoff
- `outcome`: next_week_market_status_vector

## Rows

| unit | target | obs window | cutoff | outcome window | issues |
| --- | --- | --- | --- | --- | --- |
| `btcusdt_perp__weekly__anchor_2024-06-03__causal_state` | `btcusdt_perp` | 2024-06-02T12:00:00Z to 2024-06-02T12:00:00Z | 2024-06-02T12:00:00Z | 2024-06-03T00:00:00Z to 2024-06-09T23:59:59Z |  |
| `eurusd__weekly__anchor_2024-06-03__causal_state` | `eurusd` | 2024-06-02T12:00:00Z to 2024-06-02T12:00:00Z | 2024-06-02T12:00:00Z | 2024-06-03T00:00:00Z to 2024-06-09T23:59:59Z |  |
| `audusd__weekly__anchor_2024-06-03__causal_state` | `audusd` | 2024-06-02T12:00:00Z to 2024-06-02T12:00:00Z | 2024-06-02T12:00:00Z | 2024-06-03T00:00:00Z to 2024-06-09T23:59:59Z |  |
| `btcusdt_perp__weekly__anchor_2024-06-10__causal_state` | `btcusdt_perp` | 2024-06-09T12:00:00Z to 2024-06-09T12:00:00Z | 2024-06-09T12:00:00Z | 2024-06-10T00:00:00Z to 2024-06-16T23:59:59Z |  |
| `eurusd__weekly__anchor_2024-06-10__causal_state` | `eurusd` | 2024-06-09T12:00:00Z to 2024-06-09T12:00:00Z | 2024-06-09T12:00:00Z | 2024-06-10T00:00:00Z to 2024-06-16T23:59:59Z |  |
| `audusd__weekly__anchor_2024-06-10__causal_state` | `audusd` | 2024-06-09T12:00:00Z to 2024-06-09T12:00:00Z | 2024-06-09T12:00:00Z | 2024-06-10T00:00:00Z to 2024-06-16T23:59:59Z |  |
| `btcusdt_perp__weekly__anchor_2024-06-17__causal_state` | `btcusdt_perp` | 2024-06-16T12:00:00Z to 2024-06-16T12:00:00Z | 2024-06-16T12:00:00Z | 2024-06-17T00:00:00Z to 2024-06-23T23:59:59Z |  |
| `eurusd__weekly__anchor_2024-06-17__causal_state` | `eurusd` | 2024-06-16T12:00:00Z to 2024-06-16T12:00:00Z | 2024-06-16T12:00:00Z | 2024-06-17T00:00:00Z to 2024-06-23T23:59:59Z |  |
| `audusd__weekly__anchor_2024-06-17__causal_state` | `audusd` | 2024-06-16T12:00:00Z to 2024-06-16T12:00:00Z | 2024-06-16T12:00:00Z | 2024-06-17T00:00:00Z to 2024-06-23T23:59:59Z |  |
| `btcusdt_perp__weekly__anchor_2024-06-24__causal_state` | `btcusdt_perp` | 2024-06-23T12:00:00Z to 2024-06-23T12:00:00Z | 2024-06-23T12:00:00Z | 2024-06-24T00:00:00Z to 2024-06-30T23:59:59Z |  |
| `eurusd__weekly__anchor_2024-06-24__causal_state` | `eurusd` | 2024-06-23T12:00:00Z to 2024-06-23T12:00:00Z | 2024-06-23T12:00:00Z | 2024-06-24T00:00:00Z to 2024-06-30T23:59:59Z |  |
| `audusd__weekly__anchor_2024-06-24__causal_state` | `audusd` | 2024-06-23T12:00:00Z to 2024-06-23T12:00:00Z | 2024-06-23T12:00:00Z | 2024-06-24T00:00:00Z to 2024-06-30T23:59:59Z |  |
