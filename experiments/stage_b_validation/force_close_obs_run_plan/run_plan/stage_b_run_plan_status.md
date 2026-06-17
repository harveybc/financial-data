# Project 3 Stage B Run Plan Status

Generated UTC: `2026-05-14T03:45:35.462670+00:00`
Plan ID: `stageb_force_close_obs_ethusdt_4h_sac_diagnostic_v1`
Total configs: `90`
No-trade anomaly threshold: `20.0%`

## Status Counts

- `NOT_STARTED_LOCKED`: 90

## Anomaly Counts

- None

## Warning Counts

- None

## Final Trace Gates

- No-trade hard fail: `final_trades_total <= 0` when trace exists.
- Excessive-trade warning: `>312.0` trades/year.
- Excessive-trade hard fail: `>730.0` trades/year.
- Always-in-market hard fail when losing: exposure `>=0.95` and final return `<= 0`.

## Running Or Anomalous Rows

| Variant | Status | Progress % | Live Trades | Return | Final Trades/Yr | Exposure | Anomalies | Warnings |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| None | - | - | - | - | - |
