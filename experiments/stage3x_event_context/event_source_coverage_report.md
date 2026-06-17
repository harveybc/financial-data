# Project 3 Event-Context Source Coverage Report

Generated UTC: `2026-06-09T16:34:41+00:00`

## Summary

- Schema: `project3_event_context_source_coverage_v1`
- Source root: `/home/harveybc/Documents/GitHub/financial-data`
- Source count: `29`
- Sources with scheduled timestamps: `29`
- Sources with first-available timestamps: `0`
- Stage C access: `DENIED`
- Training launched: `false`

## Blocking Issues

- `POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS`: 24
- `ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS`: 24
- `SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS`: 11

## Warnings

- `SCHEDULED_TIMESTAMP_UNPARSEABLE`: 4

## Sources

| Path | Class | Timeframe | Rows | Coverage | Scheduled TS | First Available | Actual | Forecast | Issues |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| `economic_calendar/release_actuals/core_cpi_yoy/actuals.parquet` | `release_actuals` | `native` | 432 | 1990-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/core_pce_yoy/actuals.parquet` | `release_actuals` | `native` | 432 | 1990-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/cpi_yoy/actuals.parquet` | `release_actuals` | `native` | 432 | 1990-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/fed_funds/actuals.parquet` | `release_actuals` | `native` | 432 | 1990-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/fxmacrodata/announcements.parquet` | `release_actuals` | `native` | 18147 | 2024-12-12T08:30:00+00:00 -> 2026-05-01T23:36:47+00:00 | `announcement_datetime_utc` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/gdp_qoq_annualized/actuals.parquet` | `release_actuals` | `native` | 144 | 1990-01-01T00:00:00+00:00 -> 2025-10-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/initial_claims/actuals.parquet` | `release_actuals` | `native` | 1878 | 1990-01-06T00:00:00+00:00 -> 2025-12-27T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/nonfarm_payrolls_mom/actuals.parquet` | `release_actuals` | `native` | 432 | 1990-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/retail_sales_mom/actuals.parquet` | `release_actuals` | `native` | 408 | 1992-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/treasury_10y/actuals.parquet` | `release_actuals` | `native` | 9393 | 1990-01-01T00:00:00+00:00 -> 2025-12-31T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/release_actuals/unemployment_rate/actuals.parquet` | `release_actuals` | `native` | 432 | 1990-01-01T00:00:00+00:00 -> 2025-12-01T00:00:00+00:00 | `date` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/scheduled_events/fred_release_date_proxy/scheduled_events.parquet` | `scheduled_events` | `native` | 1200 | 1996-01-01T00:00:00+00:00 -> 2025-12-31T00:00:00+00:00 | `scheduled_date_proxy` | `` | true | true | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS, SURPRISE_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet` | `scheduled_events` | `native` | 896 | 2026-02-05T12:00:00+00:00 -> 2027-07-14T18:00:00+00:00 | `announcement_datetime_utc` | `` | false | false | none |
| `features/cross_source_features/15m/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `15m` | 43585 | 2025-03-03T21:15:00+00:00 -> 2026-04-30T12:15:00+00:00 | `announcement_datetime_utc` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_features/15m/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `15m` | 50329 | n/a | `announcement_datetime_local_utc` | `` | false | false | none |
| `features/cross_source_features/1h/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `1h` | 10897 | 2025-03-03T21:15:00+00:00 -> 2026-04-30T12:15:00+00:00 | `announcement_datetime_utc` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_features/1h/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `1h` | 12583 | n/a | `announcement_datetime_local_utc` | `` | false | false | none |
| `features/cross_source_features/4h/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `4h` | 2725 | 2025-03-03T21:15:00+00:00 -> 2026-04-30T12:15:00+00:00 | `announcement_datetime_utc` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_features/4h/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `4h` | 3147 | n/a | `announcement_datetime_local_utc` | `` | false | false | none |
| `features/cross_source_features/5m/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `5m` | 130753 | 2025-03-03T21:15:00+00:00 -> 2026-04-30T12:15:00+00:00 | `announcement_datetime_utc` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_features/5m/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `5m` | 150985 | n/a | `announcement_datetime_local_utc` | `` | false | false | none |
| `features/cross_source_statistical/15m/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `15m` | 43585 | 2025-01-31T00:00:00+00:00 -> 2026-04-30T00:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/15m/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `15m` | 50329 | 2026-02-05T12:00:00+00:00 -> 2027-07-14T18:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/1h/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `1h` | 10897 | 2025-01-31T00:00:00+00:00 -> 2026-04-30T00:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/1h/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `1h` | 12583 | 2026-02-05T12:00:00+00:00 -> 2027-07-14T18:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/4h/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `4h` | 2725 | 2025-01-31T00:00:00+00:00 -> 2026-04-30T00:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/4h/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `4h` | 3147 | 2026-02-05T12:00:00+00:00 -> 2027-07-14T20:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/5m/economic_calendar__release_actuals__fxmacrodata__announcements.parquet` | `release_actuals` | `5m` | 130753 | 2025-01-31T00:00:00+00:00 -> 2026-04-30T00:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
| `features/cross_source_statistical/5m/economic_calendar__scheduled_events__fxmacrodata__release_calendar.parquet` | `scheduled_events` | `5m` | 150985 | 2026-02-05T12:00:00+00:00 -> 2027-07-14T18:00:00+00:00 | `timestamp` | `` | true | false | POINT_IN_TIME_FIELDS_WITHOUT_FIRST_AVAILABLE_TS, ACTUAL_VALUES_WITHOUT_FIRST_AVAILABLE_TS |
