# Stage 3.1 Watchdog

Generated: 2026-05-03T07:24:09.821372+00:00

Supervisor service: `already_active`

| Machine | Busy | Pending | Action | Active Task | Next Assignment Hint | Detail |
| --- | --- | ---: | --- | --- | --- | --- |
| omega | False | 0 | idle_no_pending | `-` | `-` | `{   "active": [],   "counts": {     "complete": 152   },   "machine": "omega",   "reconciled": [] } omega_maintenance: stage32_synthesis_recent` |
| dragon | True | 48 | busy | `btcusdt_perp_15m_tech_stat_decomp_sac_s0_50000` | `btcusdt_perp_15m_tech_stat_decomp_sac_s1_50000 (btcusdt_perp 15m sac tech_stat_decomp seed=1)` | `{   "active": [     "btcusdt_perp_15m_tech_stat_decomp_sac_s0_50000"   ],   "counts": {     "complete": 370,     "pending": 48,     "training": 1   },   "machin` |
| gamma | True | 48 | busy | `usdjpy_15m_learned_cnn_sac_s0_50000` | `usdjpy_15m_learned_cnn_sac_s1_50000 (usdjpy 15m sac learned_cnn seed=1)` | `{   "active": [     "usdjpy_15m_learned_cnn_sac_s0_50000"   ],   "counts": {     "blocked_resolved_rerouted_to_dragon": 3,     "complete": 284,     "pending": 4` |
