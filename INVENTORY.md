# Financial Data Lake - Master Inventory

Generated: 2026-05-02T01:25:02.578377+00:00

**Status:** Stage 1.6 preflight inventory. Current Stage 1.4/1.5 paid-source decisions are resolved for the active budget; remaining paid providers are deferred unless later evidence requires them.

## Summary

- Total documented data directories: 329
- Total files across data roots: 1662
- Total size: 2.44 GB
- Suffix counts: {".csv": 2, ".json": 336, ".md": 669, ".parquet": 571, ".txt": 16, ".xml": 1, ".zip": 16, "<none>": 51}

## Roots

| Root | Exists | Files | Size GB |
| --- | --- | ---: | ---: |
| market_data | True | 728 | 2.05 |
| macro_economic | True | 580 | 0.01 |
| alternative_data | True | 264 | 0.38 |
| reference_data | True | 33 | 0.00 |
| economic_calendar | True | 57 | 0.00 |

## Validation Preflight

- dragon: files_profiled=222 warnings=0 roots=market_data
- gamma: files_profiled=370 warnings=2 roots=macro_economic,alternative_data,reference_data,economic_calendar

## Quality Validation

- dragon: files_checked=170 warnings=0 roots=market_data
- gamma: files_checked=200 warnings=0 roots=macro_economic,alternative_data,reference_data,economic_calendar
- gamma warning classification: expected_panel=7 fixed_exact_duplicate_files=3 remaining_blockers=0

## Known Gaps Pending Stage 1.4/1.5

- 1.3.G CoinMetrics Community on-chain: partial - Review metric coverage against advanced on-chain subscription gaps.
- 1.3.I Etherscan ETH supplementary: partial - Treat historical Pro endpoints as Stage 1.4 subscription evidence; no more free-source retry unless a replacement source is approved.
- 1.3.P Economic calendar scheduled events and actuals: partial - FRED actuals and release-date proxy are present; Trading Economics guest access is discontinued and FXStreet requires OAuth, so consensus/surprise is a Stage 1.4 credential/subscription decision.
