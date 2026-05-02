# Stage 1.3 Validation Inventory

Generated: 2026-05-02T01:12:10.781905+00:00

## File Counts

| Root | Exists | Files | Size MB | Top suffixes |
| --- | --- | ---: | ---: | --- |
| market_data | True | 728 | 2103.9 | .json:140, .md:280, .parquet:288, <none>:20 |
| macro_economic | True | 580 | 5.8 | .csv:1, .json:143, .md:285, .parquet:140, .xml:1, <none>:10 |
| alternative_data | True | 264 | 384.6 | .csv:1, .json:33, .md:62, .parquet:123, .txt:16, .zip:16, <none>:13 |
| reference_data | True | 33 | 0.7 | .json:7, .md:14, .parquet:7, <none>:5 |
| economic_calendar | True | 57 | 0.5 | .json:13, .md:28, .parquet:13, <none>:3 |

## Documentation Coverage

- Data directories checked: 329
- Directories missing docs: 0

## Acquisition Log

- Rows: 196
- Latest timestamp: 2026-05-02T00:00:28.255611+00:00
- Status counts: {"ok": 151, "schema_shifted_or_malformed": 45}

## Known Gaps And Handoffs

- _logs/gamma/stage13_macro_onchain_escalation.md - - Stage: 1.3 Free Data Acquisition
- _logs/gamma/stage13_remaining_free_gaps.md - - 2026-05-01T16:43:05.462354+00:00 Etherscan historical endpoints: dailytx: Sorry, it looks like you are trying to access an API Pro endpoint. Contact us to upgrade to API Pro.; dailyavgblocksize: Sorry, it looks like you are trying to acce
- _logs/gamma/stage13_supplemental_gaps.md - - Stage: 1.3 Free Data Acquisition
- economic_calendar/release_surprises/stage13_consensus_gap.md - FRED release actuals and a historical release-date proxy are present under `economic_calendar/release_actuals/` and `economic_calendar/scheduled_events/fred_release_date_proxy/`.
- economic_calendar/scheduled_events/stage13_scheduled_events_gap.md - FRED release actuals and a historical release-date proxy are present under `economic_calendar/release_actuals/` and `economic_calendar/scheduled_events/fred_release_date_proxy/`.

## Active Dispatch Context

- omega: Stage 1.3 Free Data Acquisition | completed_idle | market_data/equities, commodities, forex, HistData-derived parquet/csv
- omega: Stage 1.3 Free Data Acquisition | completed_idle | CFTC, holidays, trading calendars, reference provenance
- omega: Stage 1.3 Task 1.3.P Economic calendar | completed_idle | economic_calendar/release_actuals with FRED actuals and scheduled-events gap note
- omega: Stage 1.3 follow-up: yfinance coverage and economic calendar proxy | completed_idle | additional yfinance indices/ETFs/EM FX/agriculture plus FRED-derived scheduled-event proxy and consensus gap note
- omega: Stage 1.3 documentation, deliverable validation, inventory, and dispatch context refresh | started | missing-doc backfills, _metadata/STAGE_1_3_INVENTORY.json, _metadata/STAGE_1_3_DELIVERABLE_VALIDATION.json, and validation reports
- dragon: Stage 1.3 Task 1.3.F Binance crypto comprehensive | completed_idle | market_data/crypto spot/perpetual/funding outputs
- dragon: Stage 1.3 validation follow-up: crypto quality audit | completed_idle | _logs/dragon/stage13_crypto_quality_report.md and JSON anomaly inventory
- dragon: Stage 1.3 Task 1.3.M FINRA short interest follow-up | completed_idle | alternative_data/short_interest/finra_consolidated_short_interest/2025.parquet
- gamma: Stage 1.3 macro/on-chain public acquisition | completed_idle | FRED, CoinMetrics attempts, Blockchain.com, mempool, SEC, DeFiLlama
- gamma: Stage 1.3 supplemental public macro | completed_idle | Treasury FiscalData, BLS public series, gap notes
- gamma: Stage 1.3 Tasks 1.3.I/1.3.M/1.3.Q/1.3.R remaining free-source follow-up | completed_idle | Etherscan free snapshots, FINRA Reg SHO daily short-volume, OECD CLI, BEA gap note
- gamma: Stage 1.3 follow-up: FRED expansion, CoinMetrics repair, SEC metadata | completed_idle | expanded FRED series, per-metric CoinMetrics community files, S&P 500 SEC filing metadata
- gamma: Stage 1.3 Task 1.3.F Binance crypto acceleration | completed_idle | market_data/crypto/perpetuals and funding_rates fetched on Gamma, then synced to Dragon/Omega
- gamma->omega: Stage 1.3 canonical sync | ok | Gamma completed macro/on-chain outputs copied to Omega
- gamma->dragon: Stage 1.3 crypto acceleration sync | ok | Gamma perpetual/funding outputs copied to Dragon so Dragon skips duplicated work
- dragon->omega: Stage 1.3 canonical sync | ok | Dragon crypto outputs copied to Omega after worker completion

## Improvement Suggestions

- Review non-ok acquisition_log rows and convert true provider limitations into Tier 4 handoffs.
- Treat completed_idle as available capacity and dispatch non-overlapping validation, sync, or acquisition slices.
- Every agent handoff should pass current stage, task, deliverable, evidence, anomalies, confidence, and context_to_pass_forward.
