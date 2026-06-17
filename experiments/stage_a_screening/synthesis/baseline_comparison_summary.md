# Baseline Comparison Summary

Generated: 2026-06-04T01:04:03.015575+00:00

Baseline comparison is partially available from the Stage A simple-baseline worker.

| Metric | Value |
| --- | --- |
| total_runs | 4933 |
| runs_with_baselines | 3515 |
| runs_blocked_input | 1418 |
| rl_beats_base | 72 |
| rl_beats_pess | 72 |
| rl_fails_base | 3432 |
| unique_input_combos | 509 |
| input_combos_loaded | 368 |
| surviving_candidate_b8 | PASS |
| note_on_fails | Most FAIL runs are Stage-A-killed (negative/zero return). B8 governance requirement is for surviving promoted candidates only. |

Promotion interpretation: candidates that fail matched simple baselines remain blocked even when raw return is positive.
