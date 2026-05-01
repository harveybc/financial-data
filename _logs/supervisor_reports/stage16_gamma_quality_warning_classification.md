# Stage 1.6 Gamma Quality Warning Classification

Generated: 2026-05-01T22:03:10Z

Gamma quality validation flagged 10 timestamp duplicate/non-monotonic warnings. Codex inspected the affected files and classified them as follows.

## Classification

| Class | Files | Severity | Decision |
| --- | ---: | --- | --- |
| Expected panel data | 7 | advisory | Not a data defect. Multiple entities/series share the same period or filing date. |
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

## Follow-Up

The generic quality worker should be improved later to understand panel natural keys so benign duplicate-date warnings do not look like anomalies. No Tier 4 blocker remains from these warnings.
