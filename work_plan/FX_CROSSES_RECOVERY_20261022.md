# FX crosses recovery from the independent public source (2026-10-22)

Lane: data engineering for the EURUSD H1 cross-asset feature store (feature-eng plugin
`cross_asset_h1`, revision r4). Branch `satoshi/fx-crosses-recovery-20261022`, additive to
`codex/data-curation-20261018`. Nothing here is admitted to the lake.

## Problem

The lake files `market_data/forex/g10/<pair>/1h.parquet` (HistData, resampled from minutes)
miss 25-40 % of the business hours in 2023-02..2023-07 and about 8 % in 2023H2 for every pair,
so the r3 cross-asset store carried ~40 % NaN in `fx.*.ret_1` and ~75 % NaN in `rv_24` and the
factor returns in 2023H1.

## Method (`_scripts/recover_independent_hf_crosses.py`)

Reuses, by import and without editing, `recover_independent_hf_fx.py` (bounded `download`,
`audit_source`, `verify_m30`, `compare`) and `admit_core_fx.py` (`required_hours`,
`require_declared_clock`). Dataset `Yllvar/fx-historical-data`, revision pinned to the one
already receipted by the core recovery (`4e694887c7f63d7e2c15a66aeebc4f45450cb381`).

Per symbol (eurusd gbpusd usdchf usdjpy eurgbp eurjpy audusd usdcad nzdusd xauusd):

1. `<SYMBOL>_H1.parquet` and `<SYMBOL>_M30.parquet`: one bounded GET each (32 MiB cap, sha256 of
   the complete file, no retry; a retained partial is never re-requested). EURUSD and GBPUSD
   bytes were reused from the core recovery receipt after re-hashing (no network).
2. Schema/quality audit: declared `UTC` labels, monotonic, no duplicates, no non-aligned rows,
   positive OHLC with valid shape, `timestamp_ms` agrees with `Time`.
3. H1 identity recomputed from M30 (`verify_m30`, tolerance 1e-12) on 2020-01..2024-12.
4. Monthly coverage 2020-01..2024-12 against the business calendar `fx_business_calendar.v1`
   (31,116 required hours); every missing hour is LISTED in `MISSING_HOURS.csv`, never filled.
5. Clock corroboration of the declared UTC bar-start label against the HistData lake 1h file
   re-localized from the lake clock (Europe/London wall - 5 h; the rule of the feature-eng
   plugin `relocalize_lake_clock`), hourly offsets -3..+3 as negative controls:
   (a) the core's OHLC-pip rule (`require_declared_clock` + monthly check) on the identical
   seven-shift common support, pip-scaled per symbol (JPY 0.01, XAU 0.1);
   (b) correlation of EXACT one-hour consecutive log returns (never across a missing interval).
6. EURUSD: the HF series against the admitted core on common support.

Derived artifacts exclude every row at or after 2025-01-01 (TEST); the raw files keep the
producer's rows untouched. Outputs under `<bulk-root>/independent-hf-crosses/`:
`<pair>.parquet` (`timestamp` UTC bar start, open/high/low/close, `m30_exact`, `source` =
`independent-hf:<revision>`), `STATUS.json`, `COVERAGE.csv`, `MISSING_HOURS.csv`, `CLOCK.json`,
`CLOCK_MONTHLY.csv`, per-pair `*.audit.json` and `*.m30_lineage.json`.

## Result (run 2026-10-21, peak RSS 301 MB, 14 GETs, 4 reused files)

| pair | H1 rows < 2025 | M30-exact 2020-24 | mismatch | missing required hours 2020-24 | 2023H1 | 2023H2 | 2024 | clock offset 0 |
|---|---|---|---|---|---|---|---|---|
| eurusd | 91,273 | 31,202 / 31,204 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| gbpusd | 91,280 | 31,198 / 31,201 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| usdchf | 91,277 | 31,184 / 31,196 | 0 | 2 | 1.000 | 0.9997 | 1.000 | corroborated |
| usdjpy | 91,273 | 31,200 / 31,204 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| eurgbp | 91,271 | 31,199 / 31,202 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| eurjpy | 91,277 | 31,195 / 31,203 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| audusd | 91,284 | 31,198 / 31,203 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| usdcad | 91,274 | 31,196 / 31,202 | 0 | 2 | 1.000 | 0.9997 | 1.000 | corroborated |
| nzdusd | 91,277 | 31,189 / 31,198 | 0 | 1 | 1.000 | 0.9997 | 1.000 | corroborated |
| xauusd | 92,063 | 29,554 / 29,575 | 0 | 1,571 | 0.943 | 0.955 | 0.952 | NO WITNESS |

Missing required hours: `2023-11-29T13:00Z` is absent from the producer for all nine FX pairs
(the admitted EURUSD core filled exactly that hour from its verified fallback); usdchf also
lacks `2022-05-19T21:00Z` and usdcad `2022-10-09T21:00Z`. XAUUSD's 1,571 "missing" hours are
concentrated at 21:00 and 22:00 UTC (872 and 448): the daily metals break, which the FX business
calendar does not model; they are not data loss and are not filled.

Clock: for the nine FX pairs the lake file, after re-localization, is the SAME price series on
the common support (offset 0: median and p95 OHLC difference 0.0 pips on 28.8k hours; return
correlation 1.000 on ~29.4k exact-hour returns), and every control offset is far away (median
2.8-12.5 pips, p95 14.7-58 pips; return correlation |r| <= 0.035). Both rules pass in every
month for every pair. XAUUSD has no hourly witness in the lake or the bulk root: its label
convention is the producer's, shared with the nine corroborated symbols, and is reported as
not independently corroborated. The `x-repo-commit` header was not present on the CDN
responses, so the revision is pinned by URL and by the receipted digests only.

EURUSD vs the admitted core (sha256 c80847bb...): 31,115 common hours of 31,116, 31,113 rows
identical (0.0 pips median and p95); the two differing rows (`2023-09-25T10:00Z`,
`2024-10-09T23:00Z`, max 5.5 pips) are exactly the two hours whose M30 lineage is incomplete
in the producer and which the admitted core took from its fallback.

## Not done

- No admission to the lake; no interpolation; no price fill; no invented bars.
- XAUUSD clock not corroborated by an independent witness (none available).
- No row at or after 2025-01-01 was analysed.

Tests: `tests/test_recover_independent_hf_crosses.py` (injected fetcher, no network).
