# Acquisition request: economic calendar 2020–2024, point-in-time (for Musashi, data-gov)

Requested by lane D, 2026-10-19. Context and source evidence:
`work_plan/ECONOMIC_CALENDAR_SOURCES_2026_10_19.md`. Contract: `M5PHET/docs/ECONOMIC_CALENDAR.md`.
This is a request, not an execution; nothing has been fetched.

## What to fetch (FXMacroData, existing stage-15 adapter, key from the established environment)

Currencies `usd`, `eur`; period 2019-12-01..2025-01-01 (one month warm-up before TRAIN). Families
(provider indicator ids as listed in `release_actuals/fxmacrodata/announcements.parquet`):

| family | USD indicator ids | EUR indicator ids |
|---|---|---|
| policy decision | `policy_rate` | `policy_rate` |
| employment | `non_farm_payrolls`, `unemployment`, `average_hourly_earnings`, `initial_jobless_claims` | `unemployment` |
| prices | `inflation`, `inflation_mom`, `core_inflation`, `core_inflation_mom`, `pce`, `core_pce`, `ppi` | `inflation`, `inflation_mom`, `core_inflation`, `ppi` |
| activity | `gdp`, `retail_sales`, `durable_goods_orders`, `industrial_production`, `pmi`, `nmi` | `gdp`, `retail_sales` |
| sentiment / labour demand | `consumer_sentiment`, `business_sentiment`, `job_openings` | — |

For every (currency, indicator): `calendar` rows as observed (schedule vintages), `announcements`
(first print, `previous_value`, revisions where the payload carries them, `announcement_datetime`
UTC), and `predictions` (consensus with its publication/vintage timestamp). Also the `data_catalogue`
payloads so the id→official-series mapping, units and release time rules are retained.

## Required record shape (per observation, immutable bytes retained)

`currency, indicator, reference_period, field ∈ {schedule, consensus, first_actual, previous,
revision}, value, unit, source_publication_utc (provider field), system_receipt_utc, provider
vintage id, request sha256, response sha256, endpoint, plan/terms version`. Unknown clocks are
null with reason, never zero latency. Consensus must carry a vintage time strictly before the
scheduled release instant to be usable as a pre-release snapshot (CAL03); otherwise label
`CONSENSUS_VINTAGE_UNKNOWN`.

## Acceptance before any event study

- Per family and year: number of scheduled releases, number with first print, number with a
  pre-release consensus vintage, number with ≥1 revision vintage; a missing month is a row in the
  denominator, not an absence.
- Schedule instants cross-checked against the official source for a sample of ≥3 releases per
  family across both DST transitions each year (BEA JSON UTC offsets, BLS "Eastern Time",
  ECB "CET"); any mismatch retained as a typed finding, not corrected silently.
- Terms: internal use only, ≤1 request/s with sleeps, bounded requests/bytes/retries, provider
  cooldowns honoured; no raw provider rows in Git; the legacy Investing.com-derived CSV is not
  merged in.

## Bounded executable command (governed, dry-run flag first)

```
python _scripts/workers/stage15_fxmacrodata_worker.py --currencies usd eur --indicators <ids above> --from 2019-12-01 --to 2025-01-01 --include-predictions --dry-run
```

`--include-predictions`, `--from/--to` and `--dry-run` do not exist in the worker today; adding
them (tests first: schedule-observed-yesterday, consensus-after-release refused, revision keeps
earlier views, DST ambiguity refused) is the first engineering increment. Until then, the next
deterministic object is the worker extension, not a download.
