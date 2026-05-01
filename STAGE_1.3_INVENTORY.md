# Stage 1.3 Inventory

Generated: 2026-05-01

## Summary

- Total inventory files: 1,530
- Data directories with standard documentation: 319
- Directories missing standard docs: 0
- Approximate total disk use: 2.5 GB

| Root | Files | Approx. size | Main coverage |
| --- | ---: | ---: | --- |
| `market_data` | 728 | 2.1 GB | Equities, ETFs, commodities, FX, crypto OHLCV/funding |
| `macro_economic` | 580 | 8.3 MB | FRED, BLS, BEA, Treasury, OECD |
| `alternative_data` | 140 | 385 MB | On-chain, SEC, FINRA, CFTC, DeFiLlama |
| `reference_data` | 33 | 852 KB | Trading calendars and holidays |
| `economic_calendar` | 49 | 516 KB | FRED actuals and release-date proxy |

## Coverage By Category

### Equities And ETFs

Daily index, ETF, and related yfinance coverage is present under `market_data/equities`. The current free acquisition does not include reliable long-history intraday US equities.

Potential paid gap: Polygon or another intraday equity provider only if Stage 2 experiments require equity 5m/15m/1h bars.

### FX

G10 FX pairs from HistData were processed into the canonical 5m, 15m, 1h, and 4h timeframes under `market_data/forex/g10`. Emerging-market FX daily yfinance series were added under `market_data/forex/emerging_markets`.

No immediate paid FX gap was found for the current Project 3 plan.

### Crypto Market Data

Binance spot, perpetual, and funding-rate outputs are present under `market_data/crypto`. Dragon quality validation checked 170 crypto files and found 0 current anomalies after replacing `USDSUSDT` and `XAUTUSDT` empty files with documented no-data exclusions.

No paid OHLCV subscription is needed for Stage 1.3 crypto market data.

### On-Chain Data

Community/free on-chain data is present from CoinMetrics, Blockchain.com, mempool.space, Etherscan snapshots, and DeFiLlama.

Remaining paid-value gap: advanced BTC/ETH metrics such as SOPR, MVRV, NUPL, NVT, richer exchange-flow metrics, and broader historical ETH endpoint coverage.

### Macro Data

FRED, BLS, BEA, Treasury, and OECD outputs are present. FRED coverage was expanded during follow-up work and is ready for Stage 1.6 catalog-level validation.

No immediate paid macro series subscription is required.

### SEC And Fundamentals

SEC EDGAR S&P 500 metadata is present under `alternative_data/sec_filings/edgar_sp500_metadata` with 365,003 rows across 503 tickers. This is parseable metadata for 10-K, 10-Q, 8-K, and Form 4 workflows.

Potential paid gap: FMP or another fundamentals provider only if experiments require normalized financial ratios rather than SEC-derived data.

### FINRA Short Interest

FINRA consolidated short interest for 2025 is present under `alternative_data/short_interest/finra_consolidated_short_interest` with 493,428 rows, 24 settlement dates, and 26,046 symbols. This supersedes the earlier Reg SHO-only gap for Stage 1.3.M.

### Economic Calendar

FRED release actuals and a FRED-derived release-date proxy are present. Consensus and surprise fields remain incomplete because Trading Economics free guest API access is discontinued and FXStreet API access requires OAuth2 credentials.

Potential paid/credential gap: Trading Economics or FXStreet if consensus/surprise features are important.

## Subscription Decision Matrix

| Service | Need | Recommendation |
| --- | --- | --- |
| Advanced on-chain provider such as Glassnode | SOPR, MVRV, NUPL, NVT, richer BTC/ETH metrics | Highest-value optional subscription |
| Trading Economics or FXStreet | Economic calendar consensus/surprise and scheduled event API | Subscribe only if event-surprise features matter |
| Etherscan Pro | Historical ETH daily endpoint access | Consider only if not covered by the on-chain provider |
| Polygon | Intraday equities/options | Defer unless equity/options experiments are selected |
| FMP | Normalized fundamentals/estimates | Defer unless SEC parsing is insufficient |
| CryptoQuant | Exchange-flow metrics | Evaluate after comparing advanced on-chain provider coverage |

## Next Step

Proceed to Stage 1.4 only for subscriptions that support selected experiment designs. In parallel, Stage 1.6 can start validating the completed free data lake for schema consistency, missing periods, and feature-readiness.

