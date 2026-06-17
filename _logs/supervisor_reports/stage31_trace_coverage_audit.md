# Stage 3.1 Trace Coverage And Liveness Audit

Generated: `2026-05-10T04:19:21.153287+00:00`

## Summary

| Machine | Queue Counts | Active Classifications | Trace Files | GPU |
| --- | --- | --- | ---: | --- |
| omega | `{'complete': 152, 'failed': 232, 'blocked_duplicate_kept_on_gamma': 50, 'blocked_duplicate_kept_on_dragon': 108, 'blocked_no_trade_early_abort': 274, 'blocked_no_trade_preflight': 35}` | `{}` | 0 | NVIDIA GeForce RTX 4070 Laptop GPU util=39% mem=3246/8188 MiB |
| dragon | `{'complete': 2483, 'failed': 17, 'blocked_duplicate_kept_on_gamma': 28, 'blocked_resolved_rerouted_to_omega': 141, 'blocked_duplicate_kept_on_omega': 133, 'blocked_duplicate_cancelled_kept_on_gamma': 21, 'blocked_no_trade_early_abort': 166, 'blocked_no_trade_preflight': 1}` | `{}` | 1982 | NVIDIA GeForce RTX 4090 Laptop GPU util=0% mem=63/16376 MiB |
| gamma | `{'complete': 2280, 'blocked_resolved_rerouted_to_dragon': 321, 'blocked_duplicate_kept_on_dragon': 301, 'blocked_duplicate_kept_on_omega': 58, 'blocked_resolved_rerouted_to_omega': 72, 'blocked_no_trade_early_abort': 248, 'failed': 13}` | `{}` | 1903 | NVIDIA GeForce RTX 5070 Ti Laptop GPU util=15% mem=14/12227 MiB |

## Active Jobs

### omega
- No active Stage 3.1 training jobs in the mirrored queue.

### dragon
- No active Stage 3.1 training jobs in the mirrored queue.

### gamma
- No active Stage 3.1 training jobs in the mirrored queue.

## Interpretation

- `ACTIVE_TRACE_CONTRACT_READY` means a current/active job has both a process and a trace destination in config.
- `ACTIVE_TRACE_CONTRACT_MISSING` means the run can finish Stage A, but it will not create return traces for rigorous B3/B4 analysis.
- `ACTIVE_STATUS_NO_PROCESS` means the queue mirror says active but the target machine does not show a matching process.
