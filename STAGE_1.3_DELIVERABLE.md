# Stage 1.3 Deliverable

Generated: 2026-05-01

## Status Summary

Stage 1.3 free data acquisition is complete enough to support the Stage 1.4 subscription decision gate.

- Validated tasks: 15
- Partial tasks with documented source/subscription limits: 3
- Failed tasks: 0
- Data/documentation inventory: 1,530 files, 319 documented data directories, 0 missing standard docs
- Approximate disk use: 2.5 GB across `market_data`, `macro_economic`, `alternative_data`, `reference_data`, and `economic_calendar`

Canonical validation evidence:

- `_metadata/STAGE_1_3_DELIVERABLE_VALIDATION.json`
- `_logs/supervisor_reports/stage13_deliverable_validation.md`
- `_metadata/STAGE_1_3_INVENTORY.json`
- `_logs/supervisor_reports/stage13_validation_inventory.md`

## Task Results

| Task | Status | Deliverable evidence |
| --- | --- | --- |
| 1.3.A Shared utilities | Validated | `_scripts/lib`, worker common utilities |
| 1.3.B FRED macro | Validated | `macro_economic/fred` |
| 1.3.C Yahoo Finance equity indices | Validated | `market_data/equities` |
| 1.3.D Commodities, ETFs, EM FX, bonds | Validated | `market_data/commodities`, `market_data/forex/emerging_markets`, `market_data/equities/etfs` |
| 1.3.E HistData FX | Validated | `market_data/forex/g10`, sourced from `/home/harveybc/Downloads/histdata` |
| 1.3.F Binance crypto | Validated | `market_data/crypto`, plus `_logs/dragon/stage13_crypto_quality_summary.json` |
| 1.3.G CoinMetrics Community | Partial | Community metrics acquired; advanced metrics remain subscription candidates |
| 1.3.H Blockchain.com BTC | Validated | `alternative_data/onchain_btc/blockchain_com` |
| 1.3.I Etherscan ETH | Partial | Free snapshots acquired; historical daily endpoints are Pro-gated |
| 1.3.J mempool.space | Validated | `alternative_data/onchain_btc/mempool_space` |
| 1.3.K SEC EDGAR | Validated | `alternative_data/sec_filings/edgar_sp500_metadata` with 365,003 rows across 503 tickers |
| 1.3.L CFTC COT | Validated | `alternative_data/cot_reports` |
| 1.3.M FINRA short interest | Validated | `alternative_data/short_interest/finra_consolidated_short_interest` with 493,428 rows across 24 settlement dates |
| 1.3.N DeFiLlama | Validated | `alternative_data/defi_metrics` |
| 1.3.O Calendars and holidays | Validated | `reference_data/trading_calendars`, `reference_data/holidays` |
| 1.3.P Economic calendar | Partial | FRED actuals and release-date proxy acquired; consensus/surprise needs API credentials |
| 1.3.Q BLS, BEA, Treasury | Validated | `macro_economic/bls`, `macro_economic/bea`, `macro_economic/yield_curves` |
| 1.3.R OECD | Validated | `macro_economic/oecd` |

## Important Validation Notes

Binance returned HTTP 200 with empty kline payloads for `USDSUSDT` and `XAUTUSDT`. Those eight zero-row files were removed and replaced with documented no-data exclusions in `_logs/dragon/stage13_crypto_exclusions.json`.

Trading Economics `guest:guest` access is discontinued, and FXStreet Economic Calendar API access requires OAuth2. Therefore, economic-calendar consensus/surprise is not a free-source deliverable unless credentials are provided.

CoinMetrics Community and Etherscan free endpoints are useful but incomplete for advanced on-chain history. Those gaps are documented as Stage 1.4 subscription inputs, not acquisition failures.

## Machine Contributions

| Machine | Model policy | Completed work |
| --- | --- | --- |
| Omega | OpenCode supervisor plus DeepSeek Flash cloud worker lane | yfinance, HistData processing, CFTC, calendars, economic release actuals, validation, inventory, sync, Telegram gateway |
| Dragon | DeepSeek Flash cloud worker, Gemma cloud fallback | Binance crypto, crypto quality validation, FINRA consolidated short interest |
| Gamma | DeepSeek Flash cloud worker, Gemma cloud fallback | FRED, CoinMetrics, Blockchain.com, mempool.space, SEC EDGAR, DeFiLlama, OECD, BLS/BEA/Treasury |

## Stage 1.4 Gate

No paid subscription is required to consider Stage 1.3 complete. The paid decisions are now value/risk decisions:

- Highest value: Glassnode or comparable advanced on-chain provider if SOPR, MVRV, NUPL, NVT, and richer BTC/ETH metrics are desired.
- Conditional: Trading Economics or FXStreet if historical consensus/surprise economic-calendar features are required.
- Conditional: Etherscan Pro only if ETH historical endpoint coverage is preferred over another on-chain provider.
- Lower priority: Polygon/FMP/CryptoQuant depending on whether Stage 2 experiments emphasize equities, fundamentals, options, or exchange-flow features.

