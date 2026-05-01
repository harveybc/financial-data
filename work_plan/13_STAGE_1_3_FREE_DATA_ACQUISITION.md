# Stage 1.3 — Free Data Acquisition

**Stage goal:** Acquire ALL free data sources from the catalog. Validate, document, organize. AFTER Stage 1.3 completes, agent produces inventory enabling informed Stage 1.4 subscription decisions.

**Inputs:** Stages 1.1 + 1.2 complete. User has approved catalog.

**Outputs:** All free data sources downloaded. Comprehensive inventory enabling Stage 1.4 subscription decisions.

**Machine assignment:**
- **Omega:** Light tasks (FRED, yfinance equity indices/commodities/ETFs, HistData processing, CFTC, calendars)
- **Dragon:** Heavy crypto fetches (top 50 spot + perpetuals across multiple timeframes 5m/15m/1h/4h)
- **Gamma:** Macro + on-chain (FRED comprehensive, OECD, CoinMetrics, Blockchain.com, SEC EDGAR, FINRA, DeFiLlama)

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

**Autonomy rule for Stage 1.3:** Tier 2 must not wait for Codex or the user to manually assign the next safe acquisition slice. On every 12-minute Omega cron tick, `_scripts/workers/stage13_autonomous_orchestrator.py` checks Omega, Dragon, and Gamma worker PID files, GPU locks, completion markers, and sync state. It then:

- keeps active workers running;
- starts any safe pending worker on an idle eligible machine;
- leaves GPU-heavy work alone when `/tmp/gpu_busy.lock` is present;
- treats completed idempotent workers as `completed_idle`;
- syncs completed Dragon/Gamma outputs back to the canonical Omega repo;
- writes `_logs/supervisor_reports/autonomous_dispatch_report.md` and updates `global_status.md`.
---

## 1. Pre-Flight Checks

For each machine, verify env active (per Rule M.8):

```bash
ssh <host> "echo \$CONDA_DEFAULT_ENV"
# Expected: tensorflow
```

If active (interactive SSH expected to be), run commands without re-activation. If not active, prepend `source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && ` to each command.

Install required libraries:

```bash
pip install --quiet yfinance fredapi requests pandas numpy pyarrow \
                    sec-edgar-downloader exchange_calendars python-holidays \
                    nasdaqdatalink
```

Verify:

```bash
python -c "import yfinance, fredapi, pandas as pd, requests; print('OK')"
```

---

## 2. Acquisition Procedure (per source)

For each source:

1. Build acquisition script at `/home/harveybc/Documents/GitHub/financial-data/_scripts/fetch_<source>.py`
2. Execute acquisition with progress logging
3. Validate (Stage II-0b 6-test battery for time-series price data; appropriate variants otherwise)
4. Write README.md, data_dictionary.md, provenance.json using Stage 1.1 templates
5. Append row to acquisition_log.csv
6. Compute SHA-256 checksum of files, record in provenance.json

---

## 3. Task Decomposition

### Task 1.3.A: Setup (Omega)

```bash
mkdir -p /home/harveybc/Documents/GitHub/financial-data/_scripts/lib
```

Create shared utilities at `/home/harveybc/Documents/GitHub/financial-data/_scripts/lib/`:
- `validation.py` — Stage II-0b 6-test battery as reusable functions
- `provenance.py` — provenance.json builder
- `documentation.py` — README + data_dictionary writer
- `acquisition_log.py` — appends to acquisition_log.csv

### Task 1.3.B: FRED comprehensive macro pull (Gamma)

Script: `_scripts/fetch_fred_comprehensive.py`

Fetches all FRED series listed in catalog Section 8.1 (~150 series across 12 categories).

```python
import os
from fredapi import Fred

FRED_API_KEY = os.environ['FRED_API_KEY']
fred = Fred(api_key=FRED_API_KEY)

SERIES_BY_CATEGORY = {
    "inflation": ["CPIAUCSL", "CPILFESL", "PPIACO", "PCEPILFE", "PCECTPI",
                  "MEDCPIM158SFRBCLE", "TRMMEANCPIM159SFRBCLE", "FPCPITOTLZGUSA"],
    "employment": ["UNRATE", "PAYEMS", "CIVPART", "U6RATE", "EMRATIO",
                   "AHETPI", "ICSA", "CCSA"],
    "gdp": ["GDP", "GDPC1", "A191RL1Q225SBEA", "GDPNOW", "GDPPOT"],
    "money": ["M1SL", "M2SL", "BOGMBASE", "WALCL", "WTREGEN"],
    "rates": ["DFF", "FEDFUNDS", "DPRIME", "DGS10", "DGS2", "DGS5", "DGS30",
              "DGS3MO", "TB3MS", "DTB3", "T10Y2Y", "T10Y3M"],
    "consumer": ["UMCSENT", "RSAFS", "PCEC", "PSAVERT", "DSPI"],
    "housing": ["HOUST", "EXHOSLUSM495S", "CSUSHPISA", "MORTGAGE30US", "PERMIT"],
    "industrial": ["INDPRO", "CAPUTLB50001SQ", "NAPM", "NAPMNOI", "BUSINV"],
    "trade": ["BOPGSTB", "IEAMTNQ"],
    "fx_indices": ["DTWEXBGS", "DTWEXAFEGS", "DTWEXEMEGS"],
    "stress": ["STLFSI4", "NFCI", "ANFCI", "TEDRATE"],
    "recession": ["USREC", "USRECP", "USRECQ", "USRECDM"],
    "inflation_expectations": ["T5YIE", "T5YIFR", "T10YIE", "MICH"],
}

# Fetch each series, save to category folder, write documentation
```

Estimated: ~30-60 min (rate-limited).

### Task 1.3.C: Yahoo Finance equity indices (Omega)

Script: `_scripts/fetch_yfinance_equities.py`

For each ticker in catalog Section 3.1, 3.3, 3.4, 3.5:

```python
import yfinance as yf

# Fetch maximum available history through end of 2025
ticker_obj = yf.Ticker(symbol)
data = ticker_obj.history(period="max", interval="1d", end="2025-12-31")

data.to_csv(f"market_data/equities/{region}/{symbol_slug}/daily.csv")
```

Total: ~25 indices across regions.

### Task 1.3.D: Yahoo Finance commodities + ETFs + EM FX + bonds (Omega)

Script: `_scripts/fetch_yfinance_extras.py`

Catalog Sections 3.6, 4.2, 6, 12.3, 12.4 — all yfinance daily data.

### Task 1.3.E: HistData FX processing (Omega + USER manual)

User has already manually downloaded EUR/USD and USD/JPY through November 2025 (5m).

User must additionally download missing pairs (per catalog Section 4.1):
- GBP/USD, USD/CHF, AUD/USD, USD/CAD, NZD/USD, EUR/GBP, EUR/JPY, GBP/JPY (and optionally NZD/USD)

REQUEST_USER document:

```
# REQUEST_USER: Additional HistData FX pairs

User has previously downloaded:
- EUR/USD (5m, through Nov 2025)
- USD/JPY (5m, through Nov 2025)

Now agent needs additional pairs of HistData 1-minute ASCII data covering 2005 through 2025.

Pairs to download:
1. GBP/USD
2. USD/CHF
3. AUD/USD
4. USD/CAD
5. NZD/USD
6. EUR/GBP
7. EUR/JPY
8. GBP/JPY

Per pair:
1. Visit https://www.histdata.com/download-free-forex-data/
2. Click pair, select "1 Minute Bar Quotes" + "Generic ASCII"
3. Download each year 2005 through 2025 (21 zips per pair)
4. Place in: /home/harveybc/Downloads/histdata/<pair>/
   (e.g., /home/harveybc/Downloads/histdata/gbpusd/)

Total: 168 zip files across 8 directories.

Reply when complete:
"Completed: histdata additional pairs - <pair>: <count> zips"
```

Agent's processing script: `_scripts/fetch_histdata_process.py`

For each pair (existing EUR/USD, USD/JPY + 8 new):
1. Unzip all yearly files
2. Concatenate to single 1-minute DataFrame
3. Resample to 5m, 15m, 1h, 4h ONLY (per Rule M.11 — no daily/weekly stored as primary, no 1m kept long-term)
4. Save to `market_data/forex/g10/<pair>/{5m,15m,1h,4h}.parquet`
5. Validate (Stage II-0b 6 tests)
6. Write README + data_dictionary + provenance

Note: 1-minute raw data is processed but only 5m/15m/1h/4h are saved as final. The 1m intermediate files can optionally be retained at `<pair>/1m_raw/` for reproducibility but are NOT used as simulation data.

### Task 1.3.F: Binance crypto comprehensive (Dragon)

Script: `_scripts/fetch_binance_crypto.py`

Phase 1: Get top 50 by current market cap dynamically:

```python
import requests

r = requests.get("https://api.coingecko.com/api/v3/coins/markets",
                 params={"vs_currency": "usd", "order": "market_cap_desc",
                         "per_page": 50, "page": 1})
top50_coins = r.json()
top50_symbols = [coin["symbol"].upper() + "USDT" for coin in top50_coins]
# Filter to those actually traded on Binance
binance_top50 = filter_to_binance_traded(top50_symbols)
```

Phase 2: For each Binance-traded symbol in top 50, fetch klines at 5m, 15m, 1h, 4h:

```python
TIMEFRAMES = ["5m", "15m", "1h", "4h"]  # NO 1m, NO 1d, NO 1w (per Rule M.11)

for symbol in binance_top50:
    for tf in TIMEFRAMES:
        # Paginated fetch (Binance returns max 1000 bars per request)
        all_klines = fetch_full_history(symbol, tf, end_date="2025-12-31")
        save_to_parquet(all_klines, f"market_data/crypto/spot_top50/{symbol_slug}/{tf}.parquet")
```

Estimated volume: 50 symbols × 4 timeframes = 200 files.

Phase 3: Perpetual futures + funding rates for top 10 perpetuals:

```python
PERP_SYMBOLS = TOP_10_PERPETUALS  # BTCUSDT, ETHUSDT, etc.
PERP_TIMEFRAMES = ["5m", "15m", "1h", "4h"]

for symbol in PERP_SYMBOLS:
    for tf in PERP_TIMEFRAMES:
        save_to_parquet(...)

# Funding rates (8h native frequency)
for symbol in PERP_SYMBOLS:
    save_funding_rate_history(symbol, end="2025-12-31")
```

### Task 1.3.G: CoinMetrics Community on-chain (Gamma)

Script: `_scripts/fetch_coinmetrics_community.py`

Free metrics for BTC, ETH, top 20:

```python
ASSETS = ["btc", "eth", "ltc", "bch", "xmr", "doge", "ada", "dot", "sol", "atom",
          "near", "matic", "avax", "trx", "xlm", "fil", "icp", "uni", "link", "etc"]

# Probe community-tier metrics (free, no key)
COMMUNITY_METRICS = ["AdrActCnt", "TxCnt", "HashRate", "DiffMean", "BlkCnt",
                     "FeeMeanUSD", "TxTfrCnt", "TxTfrValAdjUSD"]

for asset in ASSETS:
    for metric in COMMUNITY_METRICS:
        url = f"https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets={asset}&metrics={metric}&start_time=2009-01-01&end_time=2025-12-31"
        data = fetch_paginated(url)
        save_csv(data, f"alternative_data/onchain_{asset_normalized}/coinmetrics_community/{metric}.csv")
```

### Task 1.3.H: Blockchain.com BTC supplementary (Gamma)

Script: `_scripts/fetch_blockchain_com.py`

Specific BTC metrics not in CoinMetrics:
- Mempool size
- Confirmed transactions per block
- Various network stats

### Task 1.3.I: Etherscan ETH supplementary (Gamma) — requires free API key

Script: `_scripts/fetch_etherscan.py`

Requires free Etherscan API key (Stage 1.4 acquires).

### Task 1.3.J: Mempool.space (Gamma)

Free public API for BTC mempool detail.

### Task 1.3.K: SEC EDGAR (Gamma)

Script: `_scripts/fetch_sec_edgar.py`

Per catalog Section 10.1:

```python
from sec_edgar_downloader import Downloader

dl = Downloader("ProjectName", "harveybc@example.com",
                "/home/harveybc/Documents/GitHub/financial-data/alternative_data/sec_filings/edgar/")

# For each S&P 500 ticker
for ticker in SP500_TICKERS:
    dl.get("10-K", ticker, after="2003-01-01", before="2025-12-31")
    dl.get("10-Q", ticker, after="2003-01-01", before="2025-12-31")
    dl.get("8-K", ticker, after="2003-01-01", before="2025-12-31")
    dl.get("4", ticker, after="2003-01-01", before="2025-12-31")
```

We acquire metadata (filing type, timestamp, ticker) — NOT full text bodies for sentiment processing (Rule P1.7).

### Task 1.3.L: CFTC COT Reports (Omega)

Script: `_scripts/fetch_cftc_cot.py`

```python
for year in range(2000, 2026):
    url = f"https://www.cftc.gov/files/dea/history/deacot{year}.zip"
    download_and_extract(url, target=f"alternative_data/cot_reports/cftc/{year}/")
```

### Task 1.3.M: FINRA short interest (Gamma)

Script: `_scripts/fetch_finra_short_interest.py`

Bi-weekly bulk reports. Free.

### Task 1.3.N: DeFiLlama (Gamma)

Script: `_scripts/fetch_defillama.py`

Free public API. TVL per chain, per protocol, historical.

### Task 1.3.O: Trading calendars + holidays (Omega)

Script: `_scripts/fetch_calendars.py`

Use `exchange_calendars` and `python-holidays` libraries:

```python
import exchange_calendars as xcals

EXCHANGES = ["NYSE", "NASDAQ", "LSE", "XTKS", "XSHG", "XHKG", "XPAR", "XFRA"]

for exch in EXCHANGES:
    cal = xcals.get_calendar(exch)
    sessions = cal.sessions_in_range("1990-01-01", "2025-12-31")
    save_csv(sessions, f"reference_data/calendars/exchange_calendars/{exch}.csv")
```

### Task 1.3.P: Economic calendar — scheduled events + actuals (Omega)

Per catalog Section 9 (NEW):

Script: `_scripts/fetch_economic_calendar.py`

Sources:
- TradingEconomics free tier or FXStreet for scheduled events with consensus estimates
- FRED for release actuals (CPI, NFP, GDP, etc.)
- Computed surprise = actual - estimate

```python
# Example: CPI release
# Each CPI release date from FRED's CPIAUCSL has actual value
# Estimate from consensus surveys (free from TradingEconomics or scrapable)

EVENTS_TO_TRACK = [
    {"name": "CPI YoY", "fred_series": "CPIAUCSL", "release_freq": "monthly",
     "transform": "yoy_pct_change"},
    {"name": "Core CPI YoY", "fred_series": "CPILFESL", "release_freq": "monthly",
     "transform": "yoy_pct_change"},
    {"name": "Nonfarm Payrolls", "fred_series": "PAYEMS", "release_freq": "monthly",
     "transform": "month_over_month_diff"},
    {"name": "Unemployment Rate", "fred_series": "UNRATE", "release_freq": "monthly"},
    {"name": "GDP QoQ", "fred_series": "GDPC1", "release_freq": "quarterly"},
    {"name": "FOMC rate decision", "fred_series": "FEDFUNDS", "release_freq": "irregular"},
    {"name": "Eurozone HICP", "fred_series": "CP0000EZ19M086NEST", "release_freq": "monthly"},
    {"name": "ECB rate decision", "fred_series": "ECBDFR", "release_freq": "irregular"},
    # ... ~30 high-impact events
]

# For each event:
# 1. Fetch actual values from FRED
# 2. Match release dates to ICalendar of scheduled events (free TE/FXStreet)
# 3. Where consensus estimates available, compute surprise
# 4. Save to economic_calendar/release_actuals/<event>.csv
# 5. Save scheduled events forward-looking to economic_calendar/scheduled_events/
```

### Task 1.3.Q: BLS, BEA, Treasury supplementary (Gamma)

Government series not wrapped by FRED. Limited scope.

### Task 1.3.R: OECD selected indicators (Gamma)

Only series NOT in FRED. Composite Leading Indicators main use case.

---

## 4. Validation per Dataset

After each acquisition, run validation per Stage II-0b methodology adapted to data type:

```python
def validate_timeseries(df, asset_type):
    tests = {}
    if asset_type in ["fx", "equity_intraday", "crypto", "commodity_futures"]:
        # Full battery
        tests["bar_count"] = check_bar_count_realistic(df, asset_type)
        tests["weekend_gaps"] = check_weekend_gaps(df) if asset_type != "crypto" else "N/A"
        tests["fat_tails"] = check_kurtosis(df) > 4
        tests["vol_clustering"] = check_squared_returns_acf(df) > 0.05
        tests["return_acf"] = abs(check_return_acf(df)) > 0.001
        tests["no_gbm"] = check_no_gbm_fingerprint(df)
    elif asset_type == "macro_monthly":
        tests["non_empty"] = len(df) > 0
        tests["no_extreme_outliers"] = check_outliers(df)
        tests["coverage_complete"] = check_no_long_gaps(df)
    elif asset_type == "alternative_event":
        tests["non_empty"] = len(df) > 0
        tests["expected_columns"] = check_expected_columns(df)
    # Update provenance.json
    return tests
```

---

## 5. Stage 1.3 Inventory Checkpoint (NEW per TODO 8)

After all acquisition tasks complete, agent produces:

`STAGE_1.3_INVENTORY.md` — comprehensive inventory enabling Stage 1.4 subscription decisions:

```markdown
# Stage 1.3 Inventory — Free Data Acquired

## Summary

- Total free datasets acquired: [N]
- Total disk usage: [X] GB
- Total folders documented: [N]

## Coverage by Category

### Equities — daily prices
- US indices: ALL 5 acquired (S&P, NASDAQ, DJI, Russell, VIX)
- US individual: 500 S&P 500 components daily
- EU indices: 6 acquired
- Asia indices: 7 acquired
- Emerging: 4 acquired
- ETFs: 50+ acquired

### Equities — intraday
- NONE acquired free (yfinance does not provide reliable historical intraday)
- GAP: SPY 5m/15m/1h/4h, individual stocks intraday
- POTENTIAL SUBSCRIPTION: Polygon.io Developer ($79/mo) covers this gap

### FX
- 10 G10 pairs at 5m, 15m, 1h, 4h (all from HistData) — COMPLETE
- 6 EM pairs at daily — COMPLETE
- NO GAP requiring subscription

### Crypto
- BTC, ETH at 5m, 15m, 1h, 4h: COMPLETE
- Top 50 spot at 5m/15m/1h/4h: COMPLETE
- Top 10 perpetuals at 5m/15m/1h/4h + funding: COMPLETE
- NO GAP requiring subscription for OHLCV

### On-chain BTC (CoinMetrics Community)
- AdrActCnt, TxCnt, HashRate, DiffMean, BlkCnt, FeeMeanUSD: ACQUIRED
- POTENTIAL GAPS: SOPR, MVRV, NUPL, NVT, advanced indicators
- POTENTIAL SUBSCRIPTION: Glassnode Standard ($30/mo) — covers advanced metrics

### On-chain ETH
- Etherscan basic metrics: ACQUIRED
- Glassnode ETH metrics: SAME GAP as BTC
- Single Glassnode subscription covers both

### Crypto exchange flows
- NOT acquired free (no public API for exchange-specific flows)
- POTENTIAL SUBSCRIPTION: CryptoQuant Standard ($39/mo)
- NOTE: Glassnode also has some exchange flow data — evaluate overlap

### Macro (FRED)
- ~150 series across 12 categories: ACQUIRED
- NO GAP requiring subscription

### Economic calendar
- Release actuals: ACQUIRED via FRED
- Scheduled events: ACQUIRED via TradingEconomics free
- Surprise values (actual - estimate): COMPUTED where estimates available

### Fundamentals
- yfinance recent quarters: ACQUIRED (limited historical)
- SEC EDGAR XBRL: ACQUIRED (parseable)
- POTENTIAL GAP: Pre-2009 fundamentals, comprehensive ratios
- POTENTIAL SUBSCRIPTION: FMP Starter ($14/mo)
- NOTE: SEC EDGAR XBRL parsing is feasible alternative if cost concern

### Options
- NOT acquired free (yfinance only current snapshot)
- POTENTIAL SUBSCRIPTION: Polygon.io Developer ($79/mo) for options chains
- LOW PRIORITY for our research scope (focus is on price-based features primarily)

### News / Sentiment
- NONE acquired (excluded per Rule P1.7)

## Subscription Recommendation Matrix (informed by inventory)

| Service | Cost | Coverage gap addressed | Recommendation |
|---------|------|------------------------|----------------|
| FMP Starter | $14/mo | Comprehensive fundamentals + estimates | YES if fundamentals matter for selected experiments. EVALUATE: do we plan equity-trading experiments needing this? |
| Glassnode Standard | $30/mo | Advanced BTC/ETH on-chain (SOPR, MVRV, NUPL, etc.) | YES — these metrics consistently cited in literature as RL features. Worth $30/mo. |
| CryptoQuant Standard | $39/mo | Exchange flows | EVALUATE — partial overlap with Glassnode. May skip if Glassnode covers enough. |
| Polygon.io Developer | $79/mo | Intraday US equities + options | EVALUATE — only if we plan equity-trading experiments. May skip if focus is FX/crypto. |
| Twitter API | $100/mo | Sentiment | NO (excluded per Rule P1.7) |

## Recommended subscription set:

**Minimum (highest confidence): Glassnode Standard** ($30/mo) — clear value for crypto research

**Conditional (need user decision): FMP** ($14/mo) — if equity fundamentals planned

**Conditional: CryptoQuant** ($39/mo) — only if Glassnode insufficient for exchange flows

**Conditional: Polygon** ($79/mo) — only if equity intraday or options needed

**Likely skip: All others**

Total min: $30/mo
Total max: $30 + $14 + $39 + $79 = $162/mo

## User Gate

User reviews inventory and decides which subscriptions to pursue. Stage 1.4 executes user-approved subset only.
```

This is the critical TODO 8 deliverable: Subscription decisions are informed by what we have, not by general catalog speculation.

---

## 6. Compute Distribution

| Machine | Tasks |
|---------|-------|
| **Omega** | 1.3.A (setup), 1.3.C (yfinance equities), 1.3.D (yfinance extras), 1.3.E (HistData processing), 1.3.L (CFTC), 1.3.O (calendars), 1.3.P (economic calendar) |
| **Dragon** | 1.3.F (Binance crypto comprehensive — heaviest task) |
| **Gamma** | 1.3.B (FRED comprehensive), 1.3.G (CoinMetrics), 1.3.H (Blockchain.com), 1.3.I (Etherscan, after 1.4 key acquired), 1.3.J (Mempool.space), 1.3.K (SEC EDGAR), 1.3.M (FINRA), 1.3.N (DeFiLlama), 1.3.Q (BLS/BEA/Treasury), 1.3.R (OECD) |

---

## 7. Stage 1.3 Deliverables

Two deliverables:

1. `STAGE_1.3_DELIVERABLE.md` — task-by-task status report
2. `STAGE_1.3_INVENTORY.md` — comprehensive inventory (Section 5 above) enabling Stage 1.4 subscription decisions

User reviews both. Approves Stage 1.4 with specific subscription list.

---

## 8. User Gate

User reviews inventory. Decides:
1. Which subscriptions to pursue (informed by gaps)
2. Approves Stage 1.4 with specific list
