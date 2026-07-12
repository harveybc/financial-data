# Leakage And Availability Audit Summary

Generated: 2026-07-08T03:13:44.505976+00:00

Stage C remains untouched. No 2025-01-01+ data may be inspected for tuning.

## Stage B Approval Counts

| Status | Count |
| --- | --- |
| BLOCKED_BASELINE_COMPARISON | 4 |
| BLOCKED_DSR_DEFERRED | 19 |
| BLOCKED_FAMILY_ABLATION | 8 |
| BLOCKED_MISSING_EVIDENCE | 13 |
| KILL_NEGATIVE_SHARPE | 974 |
| KILL_NON_POSITIVE_RETURN | 2761 |
| KILL_NO_TRADES | 1154 |

## Leakage Audit Summary

| Metric | Value |
| --- | --- |
| total | 4933 |
| pass | 3515 |
| fail | 0 |
| blocked_missing | 1418 |
| blocked_invalid | 0 |
| warned | 0 |

## Trace/Statistical Gate Snapshot

| Metric | Value |
| --- | --- |
| Trace found | 1346 |
| Trace missing | 0 |
| DSR pass | 0 |
| DSR fail | 693 |
| PBO groups | 6 |
| Stage B ready | 0 |
