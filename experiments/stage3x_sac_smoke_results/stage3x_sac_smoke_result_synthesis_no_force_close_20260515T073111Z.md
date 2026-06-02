# Stage 3X SAC Smoke Result Synthesis

- Generated: `2026-05-15T07:08:32.298320+00:00`
- Stage C access: `DENIED`
- Task count: `15`
- Done / failed / running / pending: `13` / `2` / `0` / `0`
- Evidence files validated: `13`

## Contract Summary

| contract | done | failed | median val return | median test return | median test trades | force-close obs | action | blockers |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `audusd__4h__fx_full__corr_stability_topk__p00__selected` | 1 | 2 | 8.12642857144219e-05 | 0.0 | 0 | `False` | `kill_or_repair_before_rerun` | `FAILED_OR_ABORTED_SEEDS, TEST_NO_TRADES, MISSING_FORCE_CLOSE_OBSERVATION_FIELDS, NON_POSITIVE_MEDIAN_TEST_RETURN` |
| `btcusdt__1h__learned_cnn__rank_ic_topk__p00__selected` | 3 | 0 | -0.023835222874754036 | 0.03614787642579964 | 375 | `False` | `repair_observation_contract_then_repeat_smoke` | `MISSING_FORCE_CLOSE_OBSERVATION_FIELDS` |
| `btcusdt__1h__learned_lstm__regime_conditioned_topk__p00__selected` | 3 | 0 | -0.023835222874754036 | 0.03614787642579964 | 375 | `False` | `repair_observation_contract_then_repeat_smoke` | `MISSING_FORCE_CLOSE_OBSERVATION_FIELDS` |
| `btcusdt__4h__learned_cnn__rank_ic_topk__p00__selected` | 3 | 0 | -0.02273367019935102 | 0.04980534370300216 | 116 | `False` | `repair_observation_contract_then_repeat_smoke` | `MISSING_FORCE_CLOSE_OBSERVATION_FIELDS` |
| `btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00__selected` | 3 | 0 | -0.048566519656997875 | 0.04845364674707153 | 118 | `False` | `repair_observation_contract_then_repeat_smoke` | `MISSING_FORCE_CLOSE_OBSERVATION_FIELDS` |

## Decision

- Broad GPU launch allowed: `False`
- Stage C allowed: `False`
- Next action: `repair_force_close_observation_contract_and_repeat_small_smoke`

## Notes

- This smoke run validated that feature hashes and evidence files are now emitted for completed cells.
- The force-close/calendar observation fields were not present in completed evidence, so the next smoke should repair that contract before larger optimization.
- AUDUSD produced no-trade/test-no-trade behavior and should not consume more GPU until the execution/data contract is repaired.
