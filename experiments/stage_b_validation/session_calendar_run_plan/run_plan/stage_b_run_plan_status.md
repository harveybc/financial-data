# Project 3 Stage B Run Plan Status

Generated UTC: `2026-05-13T20:26:26.860335+00:00`
Plan ID: `stageb_session_calendar_ethusdt_4h_sac_diagnostic_v1`
Total configs: `270`
No-trade anomaly threshold: `20.0%`

## Status Counts

- `NOT_STARTED_LOCKED`: 270

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
