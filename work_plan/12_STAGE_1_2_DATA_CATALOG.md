# Stage 1.2 — Data Catalog

**Stage goal:** Document EXHAUSTIVELY every data source we will acquire, organized by category. This is the master inventory. Stages 1.3 (free) and 1.5 (paid) execute against this catalog.

**Inputs:** Stage 1.1 complete (folder structure exists).

**Outputs:**
- `/home/harveybc/Documents/GitHub/financial-data/_metadata/data_catalog.json` — machine-readable
- `STAGE_1.2_DELIVERABLE.md` — human-readable
- User-approved acquisition list (subscription decisions deferred to after Stage 1.3)

**Machine:** Omega (catalog construction is reading + writing, no compute).

---

<!-- AGENT_INFRA_NOTE_v2 -->
## Agent Infrastructure Note

This stage is executed by the multi-tier agent system defined in `01_AGENT_INFRASTRUCTURE.md` (architecture v2). Read that document before executing this stage. Key rules:

- **Tier 2 (OpenCode Go on Omega) dispatches** the per-machine tasks listed below; you (the user) do not run them by hand.
- **Tier 1 supervisors** (Hermes + Gemma 3 31B on Dragon and Gamma, cron-invoked, GPU-lockfile-aware) watch worker logs and produce status reports.
- **Heavy GPU jobs MUST acquire `/tmp/gpu_busy.lock`** via `_scripts/lib/gpu_lock.py` before starting. See infrastructure doc §4.
- **Auto-validation is full auto** (master plan Rule M.15). When you confirm a manual prerequisite is done, the agents proceed through validation, deliverable generation, and downstream prep automatically. Only blockers ping you.
- **Escalation routing (v2 simplified — no automated frontier API):**
  - Code/data anomalies, scope ≤2 files, severity ≤ high → Tier 3 (local Hermes + Gemma 31B, bounded: max 3 attempts, max 2 files, 30 min/attempt). If Tier 3 confidence <0.7 or attempts exhausted → hands off to Tier 4.
  - Plan decisions, synthesis, final-report writing, blocker severity, or scope >2 files → Tier 4 (you, with ChatGPT 5.5 Pro via Codex / Copilot Opus 4.7 / Claude Pro Max as your tools).
  - **No automated frontier API calls anywhere.** Frontier models are human-driven only.

The "machine assignment" tables below describe which machine runs which workers. The dispatcher (Tier 2) handles SSH, conda activation, and result collection.
---

## 1. Catalog Categories

The catalog is organized by data category. Each entry specifies:
- Data type
- Source provider
- Cost (free / subscription with $/mo)
- Coverage period
- **Periodicity** (5m, 15m, 1h, 4h for simulation; daily/monthly for forward-fill)
- Acquisition method
- Target folder
- Priority (HIGH / MEDIUM / LOW)
- Justification (why we want this — RL agent value, not predictive value)
- **Redundancy status** (PRIMARY / VALIDATION-ONLY-IF-GAPS / EXCLUDED-DUPLICATE)
- **Use case in Project 3:** trading_asset / feature_input / both / reference

---

## 2. Periodicities Used (Reminder)

For trading asset price data (used as simulation env data):
- 5m, 15m, 1h, 4h ONLY

For forward-fill feature inputs (NOT used as simulation data):
- Daily, weekly, monthly (only when source provides at that frequency natively)

NEVER acquired:
- 1-minute bars (too noisy, microstructure-dominated)

---

## 3. EQUITIES

### 3.1 US Equity Indices

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case | Redundancy |
|--------|----------|------|-------------|----------|--------|----------|----------|------------|
| S&P 500 | yfinance | Free | daily (forward-fill) | 1993-2025 | `market_data/equities/us_indices/spx/` | HIGH | feature_input | PRIMARY |
| NASDAQ-100 | yfinance | Free | daily | 1985-2025 | `market_data/equities/us_indices/ndx/` | HIGH | feature_input | PRIMARY |
| Dow Jones | yfinance | Free | daily | 1992-2025 | `market_data/equities/us_indices/dji/` | MEDIUM | feature_input | PRIMARY |
| Russell 2000 | yfinance | Free | daily | 1987-2025 | `market_data/equities/us_indices/rut/` | MEDIUM | feature_input | PRIMARY |
| VIX | yfinance + FRED | Free | daily | 1990-2025 | `market_data/equities/us_indices/vix/` | HIGH | feature_input | PRIMARY |
| SPX intraday | Polygon.io Developer | $79/mo | 5m, 15m, 1h, 4h | 5+ years | `market_data/equities/us_indices/spx_intraday/` | MEDIUM | trading_asset / feature_input | PRIMARY for intraday |

### 3.2 US Individual Stocks

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case | Redundancy |
|--------|----------|------|-------------|----------|--------|----------|----------|------------|
| S&P 500 components daily | yfinance | Free | daily | Variable per stock, 2000-2025 | `market_data/equities/us_individual/sp500/daily/` | HIGH | feature_input (cross-sectional, sector rotation) | PRIMARY |
| Top 100 by market cap intraday | Polygon.io Developer | (incl in $79/mo) | 5m, 15m, 1h, 4h | 5+ years | `market_data/equities/us_individual/top100_intraday/` | LOW | feature_input | PRIMARY (paid only) |

### 3.3 European Equity Indices

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case | Redundancy |
|--------|----------|------|-------------|----------|--------|----------|----------|------------|
| FTSE 100 | yfinance | Free | daily | 1984-2025 | `market_data/equities/eu_indices/ftse100/` | HIGH | feature_input | PRIMARY |
| DAX | yfinance | Free | daily | 1990-2025 | `market_data/equities/eu_indices/dax/` | HIGH | feature_input | PRIMARY |
| CAC 40 | yfinance | Free | daily | 1990-2025 | `market_data/equities/eu_indices/cac40/` | HIGH | feature_input | PRIMARY |
| EURO STOXX 50 | yfinance | Free | daily | 1986-2025 | `market_data/equities/eu_indices/stoxx50/` | HIGH | feature_input | PRIMARY |
| IBEX 35 | yfinance | Free | daily | 1993-2025 | `market_data/equities/eu_indices/ibex35/` | LOW | feature_input | PRIMARY |
| FTSE MIB | yfinance | Free | daily | 1997-2025 | `market_data/equities/eu_indices/ftse_mib/` | LOW | feature_input | PRIMARY |

### 3.4 Asia Equity Indices

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case | Redundancy |
|--------|----------|------|-------------|----------|--------|----------|----------|------------|
| Nikkei 225 | yfinance | Free | daily | 1965-2025 | `market_data/equities/asia_indices/nikkei225/` | HIGH | feature_input | PRIMARY |
| Hang Seng | yfinance | Free | daily | 1986-2025 | `market_data/equities/asia_indices/hsi/` | HIGH | feature_input | PRIMARY |
| Shanghai Composite | yfinance | Free | daily | 1990-2025 | `market_data/equities/asia_indices/sse_comp/` | HIGH | feature_input | PRIMARY |
| KOSPI | yfinance | Free | daily | 1996-2025 | `market_data/equities/asia_indices/kospi/` | MEDIUM | feature_input | PRIMARY |
| Nifty 50 | yfinance | Free | daily | 2007-2025 | `market_data/equities/asia_indices/nifty50/` | MEDIUM | feature_input | PRIMARY |
| ASX 200 | yfinance | Free | daily | 1992-2025 | `market_data/equities/asia_indices/asx200/` | LOW | feature_input | PRIMARY |
| Taiwan TWII | yfinance | Free | daily | 1997-2025 | `market_data/equities/asia_indices/twii/` | LOW | feature_input | PRIMARY |

### 3.5 Emerging Markets

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case | Redundancy |
|--------|----------|------|-------------|----------|--------|----------|----------|------------|
| Bovespa (Brazil) | yfinance | Free | daily | 1993-2025 | `market_data/equities/emerging/bvsp/` | MEDIUM | feature_input | PRIMARY |
| Mexico IPC | yfinance | Free | daily | 1991-2025 | `market_data/equities/emerging/ipc_mx/` | LOW | feature_input | PRIMARY |
| Turkey BIST 100 | yfinance | Free | daily | 1990-2025 | `market_data/equities/emerging/bist100/` | LOW | feature_input | PRIMARY |
| South Africa JSE 40 | yfinance | Free | daily | 1995-2025 | `market_data/equities/emerging/jse40/` | LOW | feature_input | PRIMARY |

### 3.6 ETFs

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case | Redundancy |
|--------|----------|------|-------------|----------|--------|----------|----------|------------|
| Sector SPDRs (XLF, XLK, XLE, XLV, XLI, XLP, XLY, XLU, XLB, XLRE, XLC) | yfinance | Free | daily | 1998-2025 | `market_data/equities/etfs/sector_spdrs/` | HIGH | feature_input (sector rotation) | PRIMARY |
| Country ETFs (EWJ, EWZ, FXI, EEM, EFA, EWG, EWU, INDA, EWY) | yfinance | Free | daily | Variable | `market_data/equities/etfs/country/` | MEDIUM | feature_input | PRIMARY |
| Theme ETFs (ARKK, SOXX, ICLN, JETS, GDX) | yfinance | Free | daily | Variable | `market_data/equities/etfs/themes/` | LOW | feature_input | PRIMARY |
| Bond ETFs (TLT, IEF, SHY, HYG, LQD, EMB, BND, AGG) | yfinance | Free | daily | Variable | `market_data/equities/etfs/bonds/` | HIGH | feature_input (cross-asset) | PRIMARY |
| Commodity ETFs (GLD, SLV, USO, UNG, DBA, DBC) | yfinance | Free | daily | Variable | `market_data/equities/etfs/commodities/` | HIGH | feature_input | PRIMARY |

---

## 4. FOREX

### 4.1 G10 Major Pairs (PRIMARY for FX trading_asset use case)

For ALL of the following, acquire 5m, 15m, 1h, 4h:

| Pair | Source | Cost | Coverage | Folder | Priority | Use case | Redundancy |
|------|--------|------|----------|--------|----------|----------|------------|
| EUR/USD | HistData | Free | 2005-11/2025 (already downloaded) | `market_data/forex/g10/eurusd/` | HIGH | trading_asset / feature_input | PRIMARY |
| USD/JPY | HistData | Free | 2005-11/2025 (already downloaded) | `market_data/forex/g10/usdjpy/` | HIGH | trading_asset / feature_input | PRIMARY |
| GBP/USD | HistData | Free | 2005-2025 | `market_data/forex/g10/gbpusd/` | HIGH | trading_asset / feature_input | PRIMARY |
| USD/CHF | HistData | Free | 2005-2025 | `market_data/forex/g10/usdchf/` | HIGH | trading_asset / feature_input | PRIMARY |
| AUD/USD | HistData | Free | 2005-2025 | `market_data/forex/g10/audusd/` | HIGH | trading_asset / feature_input | PRIMARY |
| USD/CAD | HistData | Free | 2005-2025 | `market_data/forex/g10/usdcad/` | HIGH | trading_asset / feature_input | PRIMARY |
| NZD/USD | HistData | Free | 2005-2025 | `market_data/forex/g10/nzdusd/` | MEDIUM | trading_asset / feature_input | PRIMARY |
| EUR/GBP | HistData | Free | 2005-2025 | `market_data/forex/g10/eurgbp/` | MEDIUM | trading_asset / feature_input | PRIMARY |
| EUR/JPY | HistData | Free | 2005-2025 | `market_data/forex/g10/eurjpy/` | MEDIUM | trading_asset / feature_input | PRIMARY |
| GBP/JPY | HistData | Free | 2005-2025 | `market_data/forex/g10/gbpjpy/` | MEDIUM | trading_asset / feature_input | PRIMARY |

**Note on what's already downloaded:** User has manually downloaded EUR/USD and USD/JPY from HistData covering through approximately November 2025. Stage 1.3 will:
1. Process existing downloads
2. Verify date coverage
3. Download remaining pairs (GBP/USD, USD/CHF, AUD/USD, USD/CAD, NZD/USD, EUR/GBP, EUR/JPY, GBP/JPY)
4. Top up EUR/USD and USD/JPY with December 2025 data if available

**FX cross-validation sources EXCLUDED (per TODO 7):**

OANDA, TrueFX, Dukascopy are NOT acquired as separate primary sources for the same pairs. HistData is sole primary. Cross-validation only triggered if:
- HistData has documented gaps for specific period
- HistData validation tests fail and we need to identify root cause

If those conditions arise, we acquire ONLY the period needed from one cross-validation source. No comprehensive parallel downloads.

### 4.2 Emerging Market FX

| Pair | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|------|--------|------|-------------|----------|--------|----------|----------|
| USD/MXN | yfinance | Free | daily | 1996-2025 | `market_data/forex/emerging_markets/usdmxn/` | LOW | feature_input |
| USD/BRL | yfinance | Free | daily | 2003-2025 | `market_data/forex/emerging_markets/usdbrl/` | LOW | feature_input |
| USD/ZAR | yfinance | Free | daily | 2003-2025 | `market_data/forex/emerging_markets/usdzar/` | LOW | feature_input |
| USD/TRY | yfinance | Free | daily | 2003-2025 | `market_data/forex/emerging_markets/usdtry/` | LOW | feature_input |
| USD/INR | yfinance | Free | daily | 2003-2025 | `market_data/forex/emerging_markets/usdinr/` | LOW | feature_input |
| USD/CNY | yfinance | Free | daily | 1981-2025 | `market_data/forex/emerging_markets/usdcny/` | LOW | feature_input |

EM FX at daily only — used for forward-fill cross-asset features. Not for trading.

---

## 5. CRYPTO

### 5.1 Spot Top 50 by Market Cap

For top 20: acquire 5m, 15m, 1h, 4h. For #21-50: acquire 1h, 4h only (lower priority).

| Asset | Source | Cost | Coverage | Folder | Priority | Use case |
|-------|--------|------|----------|--------|----------|----------|
| BTC/USDT | Binance public | Free | 2017-2025 | `market_data/crypto/spot_top50/btc_usdt/` | HIGH | trading_asset / feature_input |
| ETH/USDT | Binance public | Free | 2017-2025 | `market_data/crypto/spot_top50/eth_usdt/` | HIGH | trading_asset / feature_input |
| BNB/USDT | Binance public | Free | 2017-2025 | `market_data/crypto/spot_top50/bnb_usdt/` | MEDIUM | trading_asset / feature_input |
| SOL/USDT | Binance public | Free | 2020-2025 | `market_data/crypto/spot_top50/sol_usdt/` | MEDIUM | trading_asset / feature_input |
| XRP/USDT | Binance public | Free | 2018-2025 | `market_data/crypto/spot_top50/xrp_usdt/` | MEDIUM | trading_asset / feature_input |
| ADA/USDT | Binance public | Free | 2018-2025 | `market_data/crypto/spot_top50/ada_usdt/` | MEDIUM | trading_asset / feature_input |
| AVAX/USDT | Binance public | Free | 2020-2025 | `market_data/crypto/spot_top50/avax_usdt/` | MEDIUM | trading_asset / feature_input |
| DOGE/USDT | Binance public | Free | 2019-2025 | `market_data/crypto/spot_top50/doge_usdt/` | MEDIUM | trading_asset / feature_input |
| DOT/USDT | Binance public | Free | 2020-2025 | `market_data/crypto/spot_top50/dot_usdt/` | MEDIUM | trading_asset / feature_input |
| MATIC/USDT | Binance public | Free | 2019-2025 | `market_data/crypto/spot_top50/matic_usdt/` | MEDIUM | trading_asset / feature_input |
| ... (top 11-50 by market cap) | Binance | Free | Variable | `market_data/crypto/spot_top50/<symbol>/` | LOW | feature_input |

Agent fetches list of top 50 by current market cap dynamically via CoinGecko free API at acquisition time.

### 5.2 Perpetual Futures

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| BTCUSDT perp | Binance Futures public | Free | 5m, 15m, 1h, 4h | 2019-09 to 2025 | `market_data/crypto/perpetuals/btcusdt_perp/` | HIGH | trading_asset / feature_input |
| ETHUSDT perp | Binance Futures public | Free | 5m, 15m, 1h, 4h | 2019-11 to 2025 | `market_data/crypto/perpetuals/ethusdt_perp/` | HIGH | trading_asset / feature_input |
| Top 10 perpetuals | Binance Futures | Free | 1h, 4h | Variable | `market_data/crypto/perpetuals/<symbol>_perp/` | MEDIUM | feature_input |

### 5.3 Funding Rates

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| Funding rates Binance perpetuals | Binance Futures public | Free | 8h native | 2019-09 to 2025 | `market_data/crypto/funding_rates/binance/` | HIGH | feature_input (forward-fill to 5m/15m/1h/4h) |

**Cross-exchange funding (Bybit, OKX) EXCLUDED:** Binance is sufficient. Adding others is redundancy without clear value.

---

## 6. COMMODITIES

### 6.1 Precious Metals

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| Gold (GC=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/precious_metals/gold/` | HIGH | feature_input |
| Silver (SI=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/precious_metals/silver/` | MEDIUM | feature_input |
| Platinum (PL=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/precious_metals/platinum/` | LOW | feature_input |
| Palladium (PA=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/precious_metals/palladium/` | LOW | feature_input |

### 6.2 Energy

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| WTI Crude (CL=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/energy/wti_crude/` | HIGH | feature_input |
| Brent Crude (BZ=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/energy/brent_crude/` | MEDIUM | feature_input |
| Natural Gas (NG=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/energy/natural_gas/` | MEDIUM | feature_input |
| EIA inventories | EIA API | Free | weekly | 1982-2025 | `market_data/commodities/energy/eia_inventories/` | MEDIUM | feature_input (forward-fill) |

### 6.3 Agriculture, Industrial Metals

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| Corn, Wheat, Soybeans | yfinance | Free | daily | 2000-2025 | `market_data/commodities/agriculture/<commodity>/` | LOW | feature_input |
| Copper (HG=F) | yfinance | Free | daily | 2000-2025 | `market_data/commodities/industrial_metals/copper/` | MEDIUM | feature_input |

---

## 7. BONDS

### 7.1 US Treasuries

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| US 10Y Yield | FRED | Free | daily | 1962-2025 | `market_data/bonds/us_treasuries/dgs10/` | HIGH | feature_input |
| US 2Y Yield | FRED | Free | daily | 1976-2025 | `market_data/bonds/us_treasuries/dgs2/` | HIGH | feature_input |
| US 5Y Yield | FRED | Free | daily | 1962-2025 | `market_data/bonds/us_treasuries/dgs5/` | HIGH | feature_input |
| US 30Y Yield | FRED | Free | daily | 1977-2025 | `market_data/bonds/us_treasuries/dgs30/` | MEDIUM | feature_input |
| US 3M T-Bill | FRED | Free | daily | 1934-2025 | `market_data/bonds/us_treasuries/tb3ms/` | HIGH | feature_input |
| Yield curve full term structure | FRED | Free | daily | 1990-2025 | `market_data/bonds/us_treasuries/yield_curve/` | HIGH | feature_input |
| TIPS yields | FRED | Free | daily | 2003-2025 | `market_data/bonds/us_treasuries/tips/` | MEDIUM | feature_input |
| Breakeven inflation | FRED | Free | daily | 2003-2025 | `market_data/bonds/us_treasuries/breakeven/` | HIGH | feature_input |

### 7.2 Sovereign Global

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| German 10Y Bund | FRED | Free | daily | 1990-2025 | `market_data/bonds/sovereign_global/de_10y/` | HIGH | feature_input |
| UK 10Y Gilt | FRED | Free | daily | 1980-2025 | `market_data/bonds/sovereign_global/uk_10y/` | MEDIUM | feature_input |
| Japan 10Y JGB | FRED | Free | daily | 1989-2025 | `market_data/bonds/sovereign_global/jp_10y/` | MEDIUM | feature_input |
| France 10Y, Italy 10Y, Spain 10Y | OECD | Free | monthly | 1990-2025 | `market_data/bonds/sovereign_global/<country>/` | LOW | feature_input |

### 7.3 Corporate Spreads

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|-------|--------|------|-------------|----------|--------|----------|----------|
| US Investment Grade OAS | FRED (BAMLC0A0CM) | Free | daily | 1996-2025 | `market_data/bonds/corporate/ig_oas/` | HIGH | feature_input |
| US High Yield OAS | FRED (BAMLH0A0HYM2) | Free | daily | 1996-2025 | `market_data/bonds/corporate/hy_oas/` | HIGH | feature_input |
| AAA-BAA spread | FRED | Free | daily | 1919-2025 | `market_data/bonds/corporate/aaa_baa_spread/` | MEDIUM | feature_input |

---

## 8. MACRO ECONOMIC DATA

### 8.1 FRED (Federal Reserve Economic Data)

Primary macro source. Free, comprehensive, gold-standard. No paid alternative needed.

| Series Group | Series IDs (examples) | Coverage | Folder | Priority |
|--------------|----------------------|----------|--------|----------|
| Inflation | CPIAUCSL, CPILFESL, PPIACO, PCEPILFE | 1947-2025 | `macro_economic/fred/inflation/` | HIGH |
| Employment | UNRATE, PAYEMS, CIVPART, U6RATE, ICSA | Variable | `macro_economic/fred/employment/` | HIGH |
| GDP | GDP, GDPC1, GDPNOW | 1947-2025 | `macro_economic/fred/gdp/` | HIGH |
| Money supply | M1SL, M2SL, BOGMBASE | Variable | `macro_economic/fred/money/` | MEDIUM |
| Interest rates | DFF, FEDFUNDS, DPRIME | 1954-2025 | `macro_economic/fred/rates/` | HIGH |
| Consumer | UMCSENT, RSAFS | Variable | `macro_economic/fred/consumer/` | MEDIUM |
| Housing | HOUST, CSUSHPISA | Variable | `macro_economic/fred/housing/` | MEDIUM |
| Industrial | INDPRO, NAPM | Variable | `macro_economic/fred/industrial/` | MEDIUM |
| FX indices | DTWEXBGS, DTWEXAFEGS | Variable | `macro_economic/fred/fx_indices/` | HIGH |
| Stress indices | STLFSI4, NFCI, ANFCI | Variable | `macro_economic/fred/stress/` | HIGH |
| Recession indicators | USREC, USRECP | Variable | `macro_economic/fred/recession/` | HIGH |
| Inflation expectations | T5YIE, T5YIFR, T10YIE | 2003-2025 | `macro_economic/fred/inflation_expectations/` | HIGH |

Comprehensive FRED pull: agent gets ALL series in above categories. Approximate count: ~150 individual series.

All FRED series at native frequency (daily for daily-published, monthly for monthly, etc.). Used as feature inputs via forward-fill to simulation timeframe.

### 8.2 OECD, ECB, BoJ — only for series NOT in FRED

If a series is available in FRED, do NOT also acquire from OECD/ECB/BoJ. Redundancy.

Series NOT in FRED that we acquire:
- OECD Composite Leading Indicators (multi-country)
- ECB main rate (high-frequency intraday changes if available)
- BoJ Tankan survey

---

## 9. ECONOMIC CALENDAR (NEW — replaces news)

**This is a separate top-level category, distinct from "alternative_data."**

Per TODO 9: We do NOT acquire news. We DO acquire economic calendar with release values.

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| Scheduled events calendar | TradingEconomics free / FXStreet | Free | Forward-looking + historical | `economic_calendar/scheduled_events/` | HIGH | feature_input (event proximity flags) |
| Release actuals (CPI, NFP, GDP, FOMC, etc.) | FRED + bulk pulls | Free | Historical, 1990-2025 | `economic_calendar/release_actuals/` | HIGH | feature_input (raw release values) |
| Release surprise (actual - estimate) | Computed from estimates + actuals | Free | Where estimates available | `economic_calendar/release_surprises/` | HIGH | feature_input (surprise magnitude) |

**How this is used:** Each major economic release has a scheduled timestamp. The agent's observation includes:
- Boolean flag: "is high-impact release scheduled in next N hours?"
- Boolean flag: "did high-impact release just happen in last N hours?"
- Numerical: "release surprise" (actual minus consensus estimate, normalized)
- Numerical: "release actual value" (e.g., CPI YoY %, normalized)

These are direct numerical features, no NLP required.

---

## 10. ALTERNATIVE DATA (NO news/sentiment)

### 10.1 SEC Filings

| Source | Provider | Cost | Periodicity | Coverage | Folder | Priority | Use case |
|--------|----------|------|-------------|----------|--------|----------|----------|
| EDGAR all filings | SEC EDGAR | Free | event-based | 1993-2025 | `alternative_data/sec_filings/edgar/` | MEDIUM | feature_input (filing event flags) |
| 10-K, 10-Q metadata | SEC | Free | event-based | 1993-2025 | `alternative_data/sec_filings/parsed/` | MEDIUM | feature_input (announcement effects) |
| 8-K filings | SEC EDGAR | Free | event-based | 1993-2025 | `alternative_data/sec_filings/8k/` | LOW | feature_input |

Use case clarification: We use FILING TIMESTAMPS and metadata (filing type, company), NOT the filing text body. Agent gets boolean/numerical features like "10-K filed in last X days for asset X."

### 10.2 Insider Trading

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| SEC Form 4 | SEC EDGAR | Free | 2003-2025 | `alternative_data/insider_trading/form4/` | MEDIUM | feature_input (insider buy/sell aggregates) |

### 10.3 Earnings Estimates and Recommendations

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| FMP earnings + analyst recommendations | FMP Starter | $14/mo | 30+ years for major | `alternative_data/earnings_estimates/fmp/` | MEDIUM | feature_input (estimate revisions) |

### 10.4 Short Interest

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| FINRA short interest | FINRA | Free | 2007-2025, biweekly | `alternative_data/short_interest/finra/` | MEDIUM | feature_input |

### 10.5 ETF Flows

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| ETF.com daily flow | ETF.com | Free (delayed) | Recent | `alternative_data/etf_flows/etfcom/` | LOW | feature_input |

### 10.6 COT Reports

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| CFTC Commitments of Traders | CFTC | Free | 2000-2025, weekly | `alternative_data/cot_reports/cftc/` | HIGH | feature_input (positioning) |

### 10.7 Crypto On-Chain BTC

**Critical redundancy decision:** CoinMetrics Community (free) overlaps significantly with Glassnode Standard (paid $30/mo). Stage 1.3 acquires CoinMetrics first, then Stage 1.5 evaluates whether Glassnode adds enough beyond what's already free.

| Source | Provider | Cost | Coverage | Folder | Priority | Redundancy Status |
|--------|----------|------|----------|--------|----------|-------------------|
| CoinMetrics Community | CoinMetrics | Free | 2009-2025 | `alternative_data/onchain_btc/coinmetrics_community/` | HIGH | PRIMARY (free metrics) |
| Glassnode Standard | Glassnode | $30/mo | 2009-2025 | `alternative_data/onchain_btc/glassnode/` | HIGH | EVALUATE AFTER 1.3 — only acquire metrics NOT in CoinMetrics Community |
| Blockchain.com API | Blockchain.com | Free | 2009-2025 | `alternative_data/onchain_btc/blockchain_com/` | MEDIUM | PRIMARY (specific metrics: mempool, hash rate) |
| Mempool.space | Mempool.space | Free | 2014-2025 | `alternative_data/onchain_btc/mempool_space/` | LOW | PRIMARY (mempool detail) |

### 10.8 Crypto On-Chain ETH

| Source | Provider | Cost | Coverage | Folder | Priority | Redundancy |
|--------|----------|------|----------|--------|----------|------------|
| Etherscan API | Etherscan | Free | 2015-2025 | `alternative_data/onchain_eth/etherscan/` | HIGH | PRIMARY |
| Glassnode ETH | Glassnode | (incl in $30/mo) | 2015-2025 | `alternative_data/onchain_eth/glassnode/` | HIGH | EVALUATE AFTER 1.3 |

### 10.9 Crypto Exchange Flows

| Source | Provider | Cost | Coverage | Folder | Priority | Redundancy |
|--------|----------|------|----------|--------|----------|------------|
| CryptoQuant Standard | CryptoQuant | $39/mo | 2017-2025 | `alternative_data/exchange_flows/cryptoquant/` | HIGH | EVALUATE AFTER 1.3 — see if Glassnode covers exchange flows already |

### 10.10 DeFi Metrics

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| DeFiLlama | DeFiLlama | Free | 2019-2025 | `alternative_data/defi_metrics/defillama/` | LOW | feature_input |

---

## 11. MICROSTRUCTURE (limited scope)

| Source | Provider | Cost | Coverage | Folder | Priority | Use case |
|--------|----------|------|----------|--------|----------|----------|
| Binance trade history (recent 12mo) | Binance public | Free | recent | `microstructure/trade_volume_profile/binance/` | LOW | feature_input |
| Polygon trade ticks | Polygon Developer | (incl $79/mo IF subscribed) | 5 years | `microstructure/trade_volume_profile/polygon/` | LOW | feature_input |

**Order book snapshots EXCLUDED.** Real-time capture infrastructure overhead not justified for our research scope.

---

## 12. DERIVATIVES

### 12.1 Options Chains

| Source | Provider | Cost | Coverage | Folder | Priority | Redundancy |
|--------|----------|------|----------|--------|----------|------------|
| Polygon options | Polygon Developer | $79/mo | 2015-2025 | `derivatives/options_chains/polygon/` | MEDIUM | PRIMARY (only paid source for historical options) |
| CBOE settlement values | CBOE | Free | 2010-2025 | `derivatives/options_chains/cboe_settlements/` | LOW | PRIMARY (settlement only) |

### 12.2 Options Greeks (computed)

Computed from options chains. Free (computation only). `derivatives/options_greeks/computed/`.

### 12.3 Futures Curves

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority |
|-------|--------|------|-------------|----------|--------|----------|
| WTI futures curve | yfinance | Free | daily | 2000-2025 | `derivatives/futures_curves/wti/` | MEDIUM |
| Treasury futures curve (ZN, ZB, ZF, ZT) | yfinance | Free | daily | 2000-2025 | `derivatives/futures_curves/treasuries/` | HIGH |

### 12.4 VIX Term Structure

| Asset | Source | Cost | Periodicity | Coverage | Folder | Priority |
|-------|--------|------|-------------|----------|--------|----------|
| VIX, VIX9D, VIX3M, VIX6M | yfinance | Free | daily | Variable | `derivatives/vix_term_structure/cboe/` | HIGH |
| VVIX | yfinance | Free | daily | 2007-2025 | `derivatives/vix_term_structure/vvix/` | MEDIUM |

### 12.5 Implied Volatility Surfaces

Computed from Polygon options chains if subscribed. Free (computation only). `derivatives/implied_volatility_surfaces/computed/`.

---

## 13. FUNDAMENTAL DATA

| Source | Provider | Cost | Coverage | Folder | Priority | Redundancy |
|--------|----------|------|----------|--------|----------|------------|
| Financial Modeling Prep Starter | FMP | $14/mo | 30+ years for major | `fundamental/fmp/` | MEDIUM | PRIMARY (paid; comprehensive) |
| yfinance fundamentals | yfinance | Free | Recent quarters | `fundamental/yfinance/` | LOW | VALIDATION (verify FMP not introducing errors) |
| SEC EDGAR XBRL | SEC | Free | 2009-2025 | `fundamental/edgar_xbrl/` | LOW | FALLBACK (if FMP cancelled, parse EDGAR ourselves) |

---

## 14. REFERENCE DATA

| Source | Provider | Cost | Folder | Priority |
|--------|----------|------|--------|----------|
| Trading calendars | exchange_calendars Python lib | Free | `reference_data/calendars/exchange_calendars/` | HIGH |
| Holidays per country | python-holidays | Free | `reference_data/holidays/python_holidays/` | HIGH |
| S&P 500 historical constituents | Wikipedia | Free | `reference_data/index_constituents/sp500_historical/` | MEDIUM |
| GICS sector classifications | yfinance / FMP | Free | `reference_data/sector_classifications/gics/` | HIGH |
| ISIN/CUSIP/Ticker mappings | OpenFIGI | Free | `reference_data/symbol_mappings/openfigi/` | LOW |

---

## 15. SUBSCRIPTION DECISION FRAMEWORK

Per TODO 8: subscription decisions DEFERRED until after Stage 1.3 (free data acquisition complete).

After Stage 1.3 completes, agent produces inventory of what was acquired free. Then subscription evaluation happens with actual gap knowledge.

### Provisional subscriptions to evaluate:

| Service | Cost | Provisional decision | Final decision after 1.3 |
|---------|------|----------------------|--------------------------|
| FMP Starter | $14/mo | LIKELY YES — fundamentals not adequately free | TBD |
| Glassnode Standard | $30/mo | EVALUATE — depends on which metrics in Standard tier are NOT in CoinMetrics Community | TBD |
| CryptoQuant Standard | $39/mo | EVALUATE — depends on whether Glassnode covers exchange flows | TBD |
| Polygon.io Developer | $79/mo | EVALUATE — only needed if intraday equities or options data deemed necessary; expensive vs use case | TBD |
| Twitter/X API | $100/mo | NO — sentiment data excluded per Rule P1.7 |  REJECTED |
| NewsAPI Pro | various | NO — news data excluded per Rule P1.7 | REJECTED |

**Maximum possible subscription cost (all approved): $14 + $30 + $39 + $79 = $162/month**, well under $500 cap.

**Minimum likely (cancel mediocre after evaluation): $14 + maybe $30 = $14-$44/month.**

### Subscription evaluation criteria after Stage 1.3:

For each potential subscription:
1. List specific metrics/data NOT acquired free in Stage 1.3
2. Estimate value of those specific metrics for RL agent observation space
3. Compare to alternative free workarounds
4. Decide subscribe / skip

### Subscription cancellation criteria (per Rule M.10):

After acquiring paid data and using in Phase 3 experiments:
- If data quality fails validation → cancel
- If RL agents using this data perform no better than agents without → cancel
- If equivalent data found free elsewhere → cancel

Cancellation documented in `_metadata/subscriptions.json` field `cancelled_due_to_mediocrity`.

---

## 16. EXCLUDED SOURCES (with reasons)

| Source | Reason for exclusion |
|--------|---------------------|
| Bloomberg Terminal ($24K/yr) | Cost-prohibitive vs alternatives sufficient |
| Refinitiv Eikon ($22K/yr) | Same |
| LOBSTER NASDAQ tick | HFT scope, our timeframes don't need order book |
| News data (GDELT, NewsAPI, Polygon News) | Per Rule P1.7 — sentiment processing is separate project scope |
| Social sentiment (Twitter, Reddit, StockTwits) | Per Rule P1.7 |
| Google Trends, Wikipedia traffic | Sentiment-adjacent, excluded per Rule P1.7 |
| 1-minute bars | Per Rule M.11 — too noisy |
| Order book snapshots | HFT scope |
| OANDA / TrueFX / Dukascopy as primary FX | Per TODO 7 — HistData sufficient as primary |
| Cross-exchange crypto OHLCV (Coinbase, Kraken on top of Binance) | Redundant — Binance comprehensive enough |
| BIS, IMF, World Bank | OECD + FRED cover most needs; only specific gaps if any |
| Custom economic surprise indices (Citi, Bloomberg) | We compute our own from FRED + estimates |

---

## 17. Stage 1.2 Deliverable

File: `STAGE_1.2_DELIVERABLE.md`

Content:

```markdown
# Stage 1.2 Deliverable — Data Catalog

## Summary

- **Total data sources cataloged:** [N] sources across [M] categories
- **Free sources:** [N_free]
- **Paid subscriptions to evaluate after Stage 1.3:** [N_paid_eval]
- **Excluded sources:** [N_excluded] (with reasons)

## Catalog by Priority

- HIGH priority: [count]
- MEDIUM priority: [count]
- LOW priority: [count]
- EXCLUDED: [count]

## Estimated Subscription Cost (worst case)

If ALL evaluated subscriptions approved: $[X]/month (still well under $500 cap)

## User Approval Items

User reviews catalog. Confirms:
1. Catalog completeness (any missing sources to add?)
2. Excluded sources list (anything wrongly excluded?)
3. Approves Stage 1.3 (free data acquisition) start

Subscription decisions are NOT made yet. They are made after Stage 1.3.

## User Gate

Awaiting user approval to proceed to Stage 1.3.
```

The catalog itself (this entire document) is also written to `/home/harveybc/Documents/GitHub/financial-data/_metadata/data_catalog.json` (machine-readable) and referenced from deliverable.

---

## 18. User Gate

User reviews catalog. Decides:
1. Any sources to add or remove
2. Any exclusions to challenge
3. Approves Stage 1.3 start
4. Subscription decisions deferred to after Stage 1.3
