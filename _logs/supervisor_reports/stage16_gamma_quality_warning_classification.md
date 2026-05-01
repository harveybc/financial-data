# Stage 1.6 Gamma Quality Warning Classification

Generated: 2026-05-01T22:10:55Z

Gamma quality validation initially flagged 10 timestamp duplicate/non-monotonic warnings. Codex inspected the affected files, removed exact duplicate FINRA rows, and improved the quality worker to use panel natural keys. The current Gamma quality pass reports 0 warnings.

## Classification

| Class | Files | Severity | Decision |
| --- | ---: | --- | --- |
| Expected panel data | 7 | advisory | Not a data defect. Multiple entities/series share the same period or filing date; quality worker now uses natural keys. |
| Exact duplicate source rows | 3 | low | Fixed by dropping exact duplicate rows from FINRA Reg SHO daily short-volume files. |

## Expected Panel-Data Warnings

- BEA NIPA files: multiple `SeriesCode`/`LineNumber` rows share each `TimePeriod`; no full-row duplicates found.
- BLS public series: `period` alone is not a unique timestamp because `year` and `series_id` are also part of the natural key.
- OECD CLI: multiple countries/measures share each monthly `period`; no full-row duplicates found.
- Treasury average interest rates: multiple security types share the same `record_date`; no full-row duplicates found.
- SEC S&P 500 filings: multiple forms/accessions can share the same `filing_date`; `accession_number` is the natural key.

## Fixed Exact Duplicates

| File | Duplicate Rows Removed | Post-Fix Full-Row Duplicates |
| --- | ---: | ---: |
| `alternative_data/short_interest/finra_regsho_daily/cnms/2025_daily_short_volume.parquet` | 34 | 0 |
| `alternative_data/short_interest/finra_regsho_daily/fnsq/2025_daily_short_volume.parquet` | 25 | 0 |
| `alternative_data/short_interest/finra_regsho_daily/fnyx/2025_daily_short_volume.parquet` | 30 | 0 |

## Current Result

- `_metadata/stage16_quality_validation_gamma.json`: `files_checked=200`, `files_with_warnings=0`.
- No Tier 4 blocker remains from these warnings.
