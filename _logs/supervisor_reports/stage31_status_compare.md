# Stage 3.1 Status Compare

Generated local (America/Bogota): 2026-05-10T07:39:32.089458-05:00
Generated UTC: 2026-05-10T12:39:32.089458+00:00
Previous snapshot: `2026-05-10T11:47:57.031016+00:00`
Supervisor interval: `60s`
Supervisor last tick local: `2026-05-10T07:38:25.113400-05:00` (UTC `2026-05-10T12:38:25.113400+00:00`)
Supervisor next scheduled tick local: `2026-05-10T07:39:25.113400-05:00` (UTC `2026-05-10T12:39:25.113400+00:00`) (status=due_or_running, in=0.0s, overdue=6.976s)
Overall OK: `True`

| Machine | Current Task | Progress | Trades | Profit % | Action non-hold | Deadband | Diagnosis | Source | Tasks Left | GPU | Comparison |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- | --- |
| dragon | `NO_ACTIVE_TASK` | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | idle_or_sync_gap | no_active_row | 0 | gpu0 0% mem 63/16376MB; compute_procs=0 | idle_or_no_active_task: No active task on this machine. |
| gamma | `NO_ACTIVE_TASK` | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | idle_or_sync_gap | no_active_row | 0 | gpu0 0% mem 14/12227MB; compute_procs=0 | idle_or_no_active_task: No active task on this machine. |
| omega | `NO_ACTIVE_TASK` | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | NOT_EXECUTING | idle_or_sync_gap | no_active_row | 0 | gpu0 39% mem 3789/8188MB; compute_procs=1 | idle_or_no_active_task: No active task on this machine. |

## Active Task Details

### dragon
- Current task: `NO_ACTIVE_TASK`
- Status: `NOT_EXECUTING`
- Progress: `NOT_EXECUTING` via `no_active_row`
- Trades/profit: trades=`NOT_EXECUTING`, profit_percent=`NOT_EXECUTING`, total_return=`NOT_EXECUTING`, final_equity=`NOT_EXECUTING`
- Action diagnostics: non_hold_rate=`NOT_EXECUTING`, deadband_rate=`NOT_EXECUTING`, abs_mean=`NOT_EXECUTING`, diagnosis=`idle_or_sync_gap`
- Execution diagnostics: entry_actions=`NOT_EXECUTING`, orders_submitted=`NOT_EXECUTING`
- Detail: No active queue/progress row. If tasks_left > 0, this is idle or a sync/startup gap.
- Estimated remaining minutes: `NOT_EXECUTING`
- Tasks left on machine: `0`
- Queue counts: `{'complete': 2483, 'failed': 17, 'blocked_duplicate_kept_on_gamma': 28, 'blocked_resolved_rerouted_to_omega': 141, 'blocked_duplicate_kept_on_omega': 133, 'blocked_duplicate_cancelled_kept_on_gamma': 21, 'blocked_no_trade_early_abort': 166, 'blocked_no_trade_preflight': 1}`
- Queue active run ids: `[]`
- Live process run ids: `[]`
- GPU: gpu0 0% mem 63/16376MB; compute_procs=0
- Worker process count: `0`
- Compare: No active task on this machine.

### gamma
- Current task: `NO_ACTIVE_TASK`
- Status: `NOT_EXECUTING`
- Progress: `NOT_EXECUTING` via `no_active_row`
- Trades/profit: trades=`NOT_EXECUTING`, profit_percent=`NOT_EXECUTING`, total_return=`NOT_EXECUTING`, final_equity=`NOT_EXECUTING`
- Action diagnostics: non_hold_rate=`NOT_EXECUTING`, deadband_rate=`NOT_EXECUTING`, abs_mean=`NOT_EXECUTING`, diagnosis=`idle_or_sync_gap`
- Execution diagnostics: entry_actions=`NOT_EXECUTING`, orders_submitted=`NOT_EXECUTING`
- Detail: No active queue/progress row. If tasks_left > 0, this is idle or a sync/startup gap.
- Estimated remaining minutes: `NOT_EXECUTING`
- Tasks left on machine: `0`
- Queue counts: `{'complete': 2280, 'blocked_resolved_rerouted_to_dragon': 321, 'blocked_duplicate_kept_on_dragon': 301, 'blocked_duplicate_kept_on_omega': 58, 'blocked_resolved_rerouted_to_omega': 72, 'blocked_no_trade_early_abort': 248, 'failed': 13}`
- Queue active run ids: `[]`
- Live process run ids: `[]`
- GPU: gpu0 0% mem 14/12227MB; compute_procs=0
- Worker process count: `0`
- Compare: No active task on this machine.

### omega
- Current task: `NO_ACTIVE_TASK`
- Status: `NOT_EXECUTING`
- Progress: `NOT_EXECUTING` via `no_active_row`
- Trades/profit: trades=`NOT_EXECUTING`, profit_percent=`NOT_EXECUTING`, total_return=`NOT_EXECUTING`, final_equity=`NOT_EXECUTING`
- Action diagnostics: non_hold_rate=`NOT_EXECUTING`, deadband_rate=`NOT_EXECUTING`, abs_mean=`NOT_EXECUTING`, diagnosis=`idle_or_sync_gap`
- Execution diagnostics: entry_actions=`NOT_EXECUTING`, orders_submitted=`NOT_EXECUTING`
- Detail: No active queue/progress row. If tasks_left > 0, this is idle or a sync/startup gap.
- Estimated remaining minutes: `NOT_EXECUTING`
- Tasks left on machine: `0`
- Queue counts: `{'complete': 152, 'failed': 232, 'blocked_duplicate_kept_on_gamma': 50, 'blocked_duplicate_kept_on_dragon': 108, 'blocked_no_trade_early_abort': 274, 'blocked_no_trade_preflight': 35}`
- Queue active run ids: `[]`
- Live process run ids: `[]`
- GPU: gpu0 39% mem 3789/8188MB; compute_procs=1
- Worker process count: `0`
- Compare: No active task on this machine.

