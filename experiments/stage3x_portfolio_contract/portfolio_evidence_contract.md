# Project 3 Stage 3X Portfolio Evidence Contract

Schema: `project3_stage3x_portfolio_evidence_v1`

Required top-level fields:

- `stage_c_access: DENIED`
- `stage_c_allowed: false`
- `training_launched: false`
- `portfolio_id`
- `weekly_anchor_id`
- `first_timestamp`
- `last_timestamp`
- `portfolio_return`
- `portfolio_trades`
- `portfolio_cost`
- `allocation`
- `no_trade_flags`
- `assets`

Each asset row must include:

- `asset`
- `timeframe`
- `broker_profile`
- `weight`
- `net_return`
- `trades`
- `cost`
- `first_timestamp`
- `last_timestamp`
- `force_close_exposed_bars`
- `friday_force_flat_violations`
- `daily_break_trade_attempts`

Mechanical blockers:

- any 2025-01-01+ timestamp in non-Stage-C evidence;
- Stage C not denied;
- missing per-asset accounting;
- per-asset returns/costs/trades do not aggregate to portfolio totals;
- missing force-close fields;
- OANDA FX force-close/daily-break violations;
- per-asset or portfolio trade frequency above the broker/timeframe hard max.

Negative returns are not blockers here. They are optimizer objectives.
