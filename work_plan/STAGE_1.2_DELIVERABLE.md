# Stage 1.2 Deliverable — Data Catalog

## Status: READY FOR USER REVIEW

## Date: 2026-04-28

## Summary

Comprehensive data catalog produced documenting every source we will (or evaluated) acquire in Phase 1. Catalog organized by 9 top-level categories with explicit redundancy analysis and subscription evaluation framework.

## Key Decisions Reflected in Catalog

1. **News/sentiment data EXCLUDED upfront** (per Rule P1.7). No GDELT, NewsAPI, Polygon News, Twitter, Reddit, StockTwits, Google Trends, Wikipedia.

2. **Economic calendar IS acquired** as separate top-level category. Includes scheduled events, release actuals (CPI, NFP, GDP, etc.), and computed surprise values (actual - estimate). No NLP processing required — direct numerical features.

3. **FX redundancy eliminated** (per TODO 7). HistData sole primary FX source. OANDA, TrueFX, Dukascopy NOT acquired unless HistData has documented gaps.

4. **Subscription decisions DEFERRED** (per TODO 8). All paid subscriptions are listed as "EVALUATE_AFTER_1.3" — final decisions made after free data inventory shows actual gaps.

5. **Periodicities limited to 5m/15m/1h/4h** for trading-asset and intraday feature use (Rule M.11). Daily and lower frequencies acquired only as forward-fill inputs.

6. **No 1-minute bars stored as primary** (Rule M.11). HistData yearly 1m zips are processed but final outputs are 5m/15m/1h/4h only.

## Catalog Statistics

| Category | Source count | Free | Paid (eval after 1.3) | Excluded |
|----------|-------------|------|----------------------|----------|
| Equities (US/EU/Asia/EM/ETFs) | 50+ tickers | All daily free via yfinance | Polygon for intraday IF approved | — |
| Forex (G10 + EM) | 16 pairs | All free via HistData + yfinance | None | OANDA/TrueFX/Dukascopy as redundant primaries |
| Crypto (spot + perp + funding) | 60+ symbols | All free via Binance public | None | Cross-exchange OHLCV redundant |
| Commodities | 14 instruments | All free via yfinance + EIA | None | — |
| Bonds | ~20 instruments | All free via FRED | None | — |
| Macro economic | ~150 series | All free via FRED | None | OECD/IMF/WB only for non-FRED gaps |
| Economic calendar | ~30 events | Free via TradingEconomics + FRED actuals | None | News headlines |
| Alternative data — onchain/COT/insider/etc | ~40 sources | CoinMetrics Community, FINRA, CFTC, SEC EDGAR, DeFiLlama, Etherscan, Blockchain.com, Mempool.space all free | Glassnode + CryptoQuant evaluate | Twitter/Reddit/news sentiment, exotic alt-data |
| Microstructure | 2 sources | Binance trades free | Polygon trades IF Polygon approved | Order book snapshots |
| Derivatives — options/futures/IV | ~10 instruments | yfinance + CBOE settlements | Polygon options IF approved | — |
| Fundamental | ~3 sources | yfinance + EDGAR XBRL | FMP IF approved | — |
| Reference data | ~5 sources | All free | None | — |

## Subscription Evaluation Framework (NOT decisions)

Per TODO 8, decisions made after Stage 1.3 inventory.

| Service | Cost | Provisional category | Decision criteria for Stage 1.4 |
|---------|------|---------------------|--------------------------------|
| FMP Starter | $14/mo | EVALUATE | Approve IF: equity-trading experiments planned in Phase 3 AND fundamentals deemed valuable |
| Glassnode Standard | $30/mo | EVALUATE (likely YES) | Approve IF: SOPR, MVRV, NUPL, advanced indicators not in CoinMetrics Community |
| CryptoQuant Standard | $39/mo | EVALUATE (conditional) | Approve IF: exchange flows + miner data not adequately covered by Glassnode |
| Polygon.io Developer | $79/mo | EVALUATE (skeptical) | Approve IF: equity intraday OR options data deemed essential AND no free workaround |
| **Maximum if all approved** | **$162/mo** | | Well under $500/mo cap |

| Service | Cost | Decision | Reason |
|---------|------|---------|--------|
| Twitter/X API Basic | $100/mo | REJECTED upfront | News/sentiment excluded per Rule P1.7 |
| NewsAPI / Polygon News | various | REJECTED upfront | News data excluded per Rule P1.7 |
| Bloomberg Terminal | $24K/yr | REJECTED upfront | Cost-prohibitive vs alternatives sufficient |
| Refinitiv Eikon | $22K/yr | REJECTED upfront | Same |
| LOBSTER NASDAQ tick | $$$ | REJECTED upfront | HFT scope, not our research |
| TokenTerminal | $200/mo | REJECTED upfront | DeFi metrics nice-to-have but DeFiLlama free covers core needs |

## Trading Asset Candidates (5m/15m/1h/4h price data planned)

The following are candidates for the "trading_asset" role in Phase 3 RL experiments. Each will have OHLCV at 5m, 15m, 1h, 4h after Stage 2.1:

**Forex (10 G10 pairs):**
EUR/USD, USD/JPY, GBP/USD, USD/CHF, AUD/USD, USD/CAD, NZD/USD, EUR/GBP, EUR/JPY, GBP/JPY

**Crypto spot top 50:**
BTC/USDT, ETH/USDT, BNB/USDT, SOL/USDT, XRP/USDT, ADA/USDT, AVAX/USDT, DOGE/USDT, DOT/USDT, MATIC/USDT (top 10 highest priority) + 40 more

**Crypto perpetuals top 10:**
BTCUSDT perp, ETHUSDT perp, etc.

**Equities (only if Polygon approved):**
SPY intraday, QQQ intraday, top 100 individual stocks intraday

## Feature Input Sources (varied periodicities, forward-filled to sim timeframe)

These are NOT trading assets but feature inputs to observation space:

- ~150 FRED macro series (daily/monthly/quarterly)
- All equity indices daily (SPX, NASDAQ, DAX, Nikkei, etc.)
- VIX + VIX term structure (daily)
- Yield curves (daily, full term structure)
- BTC + ETH on-chain metrics (daily)
- Funding rates (8h native, forward-filled)
- COT positioning (weekly)
- Economic calendar release values (event-based)
- Commodities daily (gold, oil, copper, etc.)
- Bond spreads daily (IG OAS, HY OAS, breakeven inflation)
- Sector ETFs daily (XLF, XLK, etc.)

## Excluded Sources (with reasons)

| Source | Reason for exclusion |
|--------|---------------------|
| Bloomberg Terminal ($24K/yr) | Cost-prohibitive, alternatives sufficient |
| Refinitiv Eikon ($22K/yr) | Same |
| LOBSTER NASDAQ tick | HFT scope, our timeframes don't need order book |
| GDELT, NewsAPI, Polygon News headlines | Rule P1.7 — news/sentiment is separate project |
| Twitter/X, Reddit, StockTwits | Rule P1.7 — sentiment-adjacent |
| Google Trends, Wikipedia traffic | Rule P1.7 — sentiment-adjacent |
| 1-minute bars | Rule M.11 — too noisy for our research |
| Daily/weekly as primary simulation | Rule M.11 — sample count too low for RL |
| Order book snapshots | HFT scope |
| OANDA/TrueFX/Dukascopy as primary FX | TODO 7 — HistData sufficient |
| Cross-exchange crypto OHLCV redundant | Binance comprehensive enough |
| BIS, IMF, World Bank as primary | OECD + FRED cover most needs |
| Citi/Bloomberg Economic Surprise indices | We compute equivalent from FRED + estimates |
| TokenTerminal ($200/mo) | DeFiLlama free covers core DeFi needs |

## User Approval Items

User reviews catalog. Confirms:

1. **Catalog completeness:** Any sources missing that user wants added? (e.g., specific exotic alt-data, additional FX pairs, particular regional indices)

2. **Excluded sources:** Anything in the EXCLUDED list user wants to challenge and include? Examples to consider:
   - 1m crypto data (excluded but available free from Binance)
   - Specific OECD series not in FRED
   - Particular country bond yields not currently included
   - LBMA precious metals fixings (could add if user wants)

3. **Trading asset universe:** Approve current candidate list of 10 FX + ~10 top crypto + perpetuals? Or expand/restrict?

4. **Subscription evaluation framework:** Confirm decisions DEFERRED to after Stage 1.3, OR pre-approve any subscriptions (e.g., Glassnode if confident on value).

5. **Approval to proceed:** Approve Stage 1.3 (Free Data Acquisition) start with this catalog.

## User Gate

Awaiting user response on items 1-5 above before Stage 1.3 begins.
