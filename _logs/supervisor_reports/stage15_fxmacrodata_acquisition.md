# Stage 1.5 FXMacroData Acquisition

Generated: 2026-05-01T23:38:43.553046+00:00

## Summary

- Provider: FXMacroData
- Status: ok
- Calendar rows: 896
- Announcement rows: 18147
- Currencies with calendar: AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY, NZD, PLN, SEK, SGD, USD
- Currencies with announcements: AUD, BRL, CAD, CHF, CNY, DKK, EUR, GBP, JPY, NZD, PLN, SEK, SGD, USD
- Consensus/forecast columns present: none
- Provider endpoint failures: 19

## Outputs

- `economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet`
- `economic_calendar/release_actuals/fxmacrodata/announcements.parquet`

## Notes

- FXMacroData improves no-lookahead macro timing because rows include announcement timestamps.
- It does not currently provide consensus/forecast/surprise fields in the acquired payload, so it does not fully replace Trading Economics or FXStreet Calendar API consensus-surprise data.
- Provider 503/404 endpoint failures are recorded in the JSON summary for supervisor review; successful rows are preserved.
