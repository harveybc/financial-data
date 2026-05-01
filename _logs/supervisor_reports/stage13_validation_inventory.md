# Stage 1.3 Validation Inventory

Generated: 2026-05-01T18:48:09.074045+00:00

## File Counts

| Root | Exists | Files | Size MB | Top suffixes |
| --- | --- | ---: | ---: | --- |
| market_data | True | 565 | 2050.1 | .json:98, .md:196, .parquet:251, <none>:20 |
| macro_economic | True | 288 | 3.9 | .csv:1, .json:69, .md:139, .parquet:68, .xml:1, <none>:10 |
| alternative_data | True | 115 | 364.6 | .csv:1, .json:19, .md:36, .parquet:14, .txt:16, .zip:16, <none>:13 |
| reference_data | True | 33 | 0.7 | .json:7, .md:14, .parquet:7, <none>:5 |
| economic_calendar | True | 44 | 0.3 | .json:10, .md:21, .parquet:10, <none>:3 |

## Documentation Coverage

- Data directories checked: 201
- Directories missing docs: 0

## Acquisition Log

- Rows: 144
- Latest timestamp: 2026-05-01T17:57:22.404021+00:00
- Status counts: {"ok": 99, "schema_shifted_or_malformed": 45}

## Known Gaps And Handoffs

- _logs/gamma/stage13_macro_onchain_escalation.md - - Stage: 1.3 Free Data Acquisition
- _logs/gamma/stage13_remaining_free_gaps.md - - 2026-05-01T16:43:05.462354+00:00 Etherscan historical endpoints: dailytx: Sorry, it looks like you are trying to access an API Pro endpoint. Contact us to upgrade to API Pro.; dailyavgblocksize: Sorry, it looks like you are trying to acce
- _logs/gamma/stage13_supplemental_gaps.md - - Stage: 1.3 Free Data Acquisition
- economic_calendar/scheduled_events/stage13_scheduled_events_gap.md - Stage: 1.3 Free Data Acquisition
- macro_economic/bea/stage13_bea_gap.md - Stage: 1.3 Free Data Acquisition

## Active Dispatch Context

- omega: Stage 1.3 Free Data Acquisition | completed_idle | market_data/equities, commodities, forex, HistData-derived parquet/csv
- omega: Stage 1.3 Free Data Acquisition | completed_idle | CFTC, holidays, trading calendars, reference provenance
- omega: Stage 1.3 Task 1.3.P Economic calendar | completed_idle | economic_calendar/release_actuals with FRED actuals and scheduled-events gap note
- omega: Stage 1.3 documentation, deliverable validation, inventory, and dispatch context refresh | started | missing-doc backfills, _metadata/STAGE_1_3_INVENTORY.json, _metadata/STAGE_1_3_DELIVERABLE_VALIDATION.json, and validation reports
- dragon: Stage 1.3 Task 1.3.F Binance crypto comprehensive | started | market_data/crypto spot/perpetual/funding outputs
- gamma: Stage 1.3 macro/on-chain public acquisition | completed_idle | FRED, CoinMetrics attempts, Blockchain.com, mempool, SEC, DeFiLlama
- gamma: Stage 1.3 supplemental public macro | completed_idle | Treasury FiscalData, BLS public series, gap notes
- gamma: Stage 1.3 Tasks 1.3.I/1.3.M/1.3.Q/1.3.R remaining free-source follow-up | completed_idle | Etherscan free snapshots, FINRA Reg SHO daily short-volume, OECD CLI, BEA gap note
- gamma: Stage 1.3 Task 1.3.F Binance crypto acceleration | completed_idle | market_data/crypto/perpetuals and funding_rates fetched on Gamma, then synced to Dragon/Omega
- gamma->omega: Stage 1.3 canonical sync | ok | Gamma completed macro/on-chain outputs copied to Omega
- gamma->dragon: Stage 1.3 crypto acceleration sync | ok | Gamma perpetual/funding outputs copied to Dragon so Dragon skips duplicated work
- dragon->omega: Stage 1.3 canonical sync | ok | Dragon crypto outputs copied to Omega after worker completion

## Improvement Suggestions

- Review non-ok acquisition_log rows and convert true provider limitations into Tier 4 handoffs.
- Treat completed_idle as available capacity and dispatch non-overlapping validation, sync, or acquisition slices.
- Every agent handoff should pass current stage, task, deliverable, evidence, anomalies, confidence, and context_to_pass_forward.
