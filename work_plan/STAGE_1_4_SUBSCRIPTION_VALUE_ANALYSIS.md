# Stage 1.4 Subscription Value Analysis

Generated: 2026-05-01

## Context

Stage 1.3 free acquisition is complete. Stage 1.6 preflight found no data-quality blockers, but formal Phase 1 completion is gated by three partial Stage 1.3 items:

- `1.3.G CoinMetrics Community on-chain`: community coverage is useful but incomplete for advanced on-chain features.
- `1.3.I Etherscan ETH supplementary`: free Etherscan coverage does not include historical Pro endpoints.
- `1.3.P Economic calendar`: FRED actuals and release-date proxy exist, but consensus/surprise and robust scheduled-event data require a credentialed provider.

This document scores subscription candidates by marginal value to Project 3, not by general popularity.

## Scoring Method

Project value score is 0-100:

- Unique gap fill: 35
- Relevance to Phase 2/3 features and RL experiments: 25
- API/automation fit: 15
- Cost/value: 15
- Data quality/provenance confidence: 10

Scores assume private research use, no redistribution, and monthly cost target below the Project 3 data budget.

## Recommendation Summary

| Rank | Provider | Decision | Score | Why |
| ---: | --- | --- | ---: | --- |
| 1 | Trading Economics Calendar API or FXStreet Calendar API | Get trial/quote; subscribe to one calendar provider | 88 / 80 | Only clear fix for consensus, surprise, scheduled events, and event-time macro features. |
| 2 | CryptoQuant Professional/Premium API | Trial or one-month subscription if API tier is affordable | 84 | Best cost/value candidate for exchange flows, miner flows, whale ratios, stablecoin flows, and crypto market structure. |
| 3 | Glassnode Professional + API add-on | Quote first; subscribe only if API price is acceptable | 72 feature score, cost-risk adjusted to 55 | Excellent SOPR/MVRV/NUPL/realized-cap style features, but current docs say API requires Professional plus add-on. |
| 4 | Polygon/Massive Stocks Developer | Conditional | 69 if equity intraday becomes required; 35 otherwise | Adds 10y US equity minute aggregates, but not needed for current Stage 1.3 gaps. |
| 5 | Etherscan Pro | Defer | 48 | Good ETH/account/token historical endpoints, but mostly narrower than advanced on-chain providers. |
| 6 | FMP Premium/Ultimate | Defer | 44 | Useful fundamentals, ratios, transcripts, and intraday charts, but current project gap is macro/on-chain/calendar. |
| 7 | Coin Metrics Pro | Defer unless academic/institutional access is cheap | 42 cost-adjusted | Excellent data quality and API, but paid tier is institutional/contact-sales; community data already acquired. |
| 8 | CoinMarketCap paid | Skip | 25 | Mostly redundant with Binance/CoinMetrics/free market data for this project. |

## Current Cost Snapshot

Checked on 2026-05-01. Prices can change; contact-sales entries must be confirmed before purchase.

| Provider | Public cost | Subscription / pricing page | Project 3 action |
| --- | ---: | --- | --- |
| Trading Economics Calendar API | API/calendar pricing is quote/contact-sales. Visible member plans are Basic $29/mo, Standard $199/mo, Professional $399/mo, but Calendar API is shown under Enterprise/API access. | https://tradingeconomics.com/api/pricing.aspx?source=basic-pricing-list and https://tradingeconomics.com/analytics/pricing.aspx?source=nav | Request API/calendar quote; do not assume the $199 or $399 plans unlock the required calendar API. |
| FXStreet Economic Calendar API | Not publicly priced; OAuth/API docs are public. | https://docs.fxstreet.com/api/calendar/ | Contact for API access/quote; use as fallback if Trading Economics quote is too high. |
| CryptoQuant API | Advanced $29/mo billed annually, Professional $99/mo billed annually with limited API access, Premium $799/mo listed/contact for full API access. Current checkout page should confirm monthly-vs-annual terms. | https://cryptoquant.com/pricing | Prefer Professional first if API endpoints cover the required metrics; Premium only if block-level/full API is truly needed. |
| Glassnode Studio Professional + API add-on | Studio Professional $999/mo billed yearly, VAT not included; API access is an add-on/contact-sales and is excluded from display-only plans. | https://glassnode.com/pricing/studio | Quote only; high value but too expensive unless API add-on cost is acceptable. |
| Etherscan API Pro | Standard $199/mo minimum tier with Pro endpoints; Advanced $299/mo, Professional $399/mo, Pro Plus $899/mo. | https://etherscan.io/apis?id=10 | Defer; buy Standard only if Etherscan historical Pro endpoints become uniquely necessary. |
| Polygon/Massive Stocks | Basic free, Starter $29/mo, Developer $79/mo, Advanced $199/mo. | https://polygon.io/pricing | Defer unless equity intraday becomes a Phase 3 requirement; Developer is the likely historical-data tier. |
| FMP | Basic free, Starter $22/mo, Premium $59/mo, Ultimate $149/mo when billed annually. | https://intelligence.financialmodelingprep.com/pricing-plans?direct=true | Defer; useful later for fundamentals but not a current Stage 1.4 blocker. |
| Coin Metrics Pro | Contact-sales/institutional. Community API is free for non-commercial use. | https://docs.coinmetrics.io/access-our-data/api | Defer unless research/academic pricing is cheap. |
| CoinMarketCap API | Basic free, Hobbyist $29/mo, Startup $79/mo, Standard $299/mo, Professional $699/mo, Enterprise contact. | https://coinmarketcap.com/api/pricing/ | Skip for now; redundant with acquired/free data for Project 3. |

## 2026-05-01 Decision Update

- **CryptoQuant Professional:** User subscribed monthly and supplied a private token. Stage 1.5 acquisition succeeded after adding a normal Project 3 user-agent to API requests. Deliverable: `alternative_data/cryptoquant/`. Observed limitation: Professional API pulls returned recent/default daily windows of up to 100 rows per endpoint; explicit older historical ranges returned `Out of allowed request range` during validation, so treat this as recent-window on-chain coverage unless CryptoQuant support confirms a historical export path.
- **FXStreet Premium:** Do not purchase for Project 3 automation. FXStreet's public API documentation says Economic Calendar API credentials are provided by the sales department and all Calendar API endpoints require OAuth2 authentication. The Premium retail/news plan should not be assumed to include API credentials.
- **FXMacroData Individual:** User supplied a private key and Stage 1.5 acquisition succeeded. Deliverables: `economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet` and `economic_calendar/release_actuals/fxmacrodata/announcements.parquet`. It improves no-lookahead macro features through announcement timestamps, but acquired payloads do not include consensus/forecast/surprise fields, so it does not fully replace FXStreet/Trading Economics consensus-surprise data.
- **Massive/Polygon:** Defer. If later needed for US equity intraday/tick research, choose Stocks Developer at $79/month; Starter is only a cheap aggregate-data test, and Advanced is only justified for real-time/quotes/financials.

## Detailed Analysis

### Trading Economics Calendar API

**Gap filled:** `1.3.P` macro scheduled events, actual/previous/revised/forecast/consensus, release timing, and potentially point-in-time calendar history.

**Pros**

- Directly targets the exact missing feature family: economic calendar consensus/surprise.
- Useful across FX, rates, equities, commodities, and crypto risk regimes.
- Broad macro coverage and streaming/websocket support.
- Can generate event-surprise features for Phase 2 and event-window experiments for Phase 3.

**Cons**

- Pricing is not transparent on static pages; must request/confirm quote.
- Could be overkill if all we need is US high-impact releases.
- Redistribution terms must be respected.

**Numerical value:** 88 if calendar-only access is reasonably priced; 72 if the only available plan is expensive.

**Decision rule:** Subscribe if monthly price is acceptable for research use and includes historical events with consensus/forecast fields. Prefer it over FXStreet if point-in-time or broad-country macro coverage is included.

### FXStreet Calendar API

**Gap filled:** `1.3.P` economic event occurrences with actual/consensus values and webhooks.

**Pros**

- Calendar-specific provider; likely less broad but tightly aligned with scheduled macro-event features.
- OAuth-protected API and webhooks are documented.
- Good fallback if Trading Economics quote is too high.

**Cons**

- Pricing/approval may require contacting provider.
- Likely narrower than Trading Economics for broad historical indicators and forecasts.

**Numerical value:** 80.

**Decision rule:** Choose FXStreet if it is meaningfully cheaper or easier to get than Trading Economics while still providing actual, consensus, previous/revised, event time, importance, country, and currency.

### CryptoQuant API

**Gap filled:** `1.3.G` advanced on-chain/exchange-flow features.

**Pros**

- Strong fit for crypto trading features: exchange inflow/outflow/netflow, miner flows, whale ratio, stablecoin flows, leverage and market indicators.
- Official docs list broad categories for BTC, ETH, stablecoins, ERC20, and exchange/miner/entity flows.
- More likely than Glassnode to be immediately useful for short/medium horizon crypto market structure.

**Cons**

- API access requires upgraded plan; current price should be confirmed at checkout.
- May overlap some CoinMetrics/network/free data, so acquisition must be gap-driven.
- Some deeper resolution may require expensive Premium tier.

**Numerical value:** 84 if Professional API access is near the observed ~$99/mo annual tier; 65 if API access requires much higher spend.

**Decision rule:** Best first advanced on-chain subscription if API access is affordable. Validate by fetching exchange flows, miner flows, whale ratio, stablecoin exchange flows, and BTC/ETH market indicators for 2017-2025.

### Glassnode Professional + API Add-On

**Gap filled:** `1.3.G` cycle and investor-behavior metrics: SOPR, MVRV, NUPL, realized cap/profit/loss, age/coin-day metrics.

**Pros**

- Very strong feature family for crypto cycle/regime modeling.
- Great complement to price, funding, and Binance market data.
- Known useful metrics for BTC/ETH regime features.

**Cons**

- Current docs say API access is only available to Professional subscribers who buy the API add-on; older "$30 Standard" assumption is not sufficient for automated agents.
- Price is likely quote/plan dependent and may exceed our marginal value threshold.
- Many features are slower-moving daily metrics, not direct execution signals.

**Numerical value:** feature value 72; cost-adjusted score 55 until quote is known.

**Decision rule:** Do not buy Standard/Advanced just for Project 3 automation. Request API quote. Subscribe only if API access is priced within the project budget and gives historical BTC/ETH SOPR/MVRV/NUPL/realized-cap metrics.

### Etherscan Pro

**Gap filled:** `1.3.I` historical ETH/token/account endpoints and daily Ethereum stats/gas endpoints.

**Pros**

- Direct Pro endpoint list includes historical native balances, token balances/supply, token holder lists/counts, daily stats, gas, and historical ETH price.
- Useful for targeted ETH token/account studies.
- Narrow, deterministic, easy to validate.

**Cons**

- Less useful for broad investor behavior than CryptoQuant/Glassnode.
- Etherscan Pro endpoints are Ethereum-mainnet focused.
- Not a substitute for robust advanced on-chain aggregate metrics.

**Numerical value:** 48.

**Decision rule:** Defer unless we specifically need historical token holder/account balance features. Do not treat it as the primary on-chain subscription.

### Polygon/Massive Stocks Developer

**Gap filled:** Not a current blocker, but it would add US equities intraday history.

**Pros**

- Stocks Developer page lists 10 years historical data, unlimited API calls, minute aggregates, second aggregates, trades, reference data, corporate actions, snapshots, and websockets.
- Good if Phase 3 needs S&P 500 intraday trading assets or equity intraday features.

**Cons**

- Current Stage 1.3 gaps are not equity intraday.
- We already have daily equities/ETFs and rich FX/crypto intraday.
- Equity intraday for hundreds of tickers can become storage/validation heavy.

**Numerical value:** 69 if equity intraday is approved; 35 otherwise.

**Decision rule:** Defer unless we explicitly want equity intraday RL/trading assets in Phase 3.

### FMP

**Gap filled:** Fundamentals, ratios, corporate calendars, transcripts/holdings at higher tiers.

**Pros**

- Premium tier has 30 years history, full fundamentals/ratios, intraday charts, technical indicators, and corporate calendars.
- Ultimate includes transcripts, ETF/mutual fund holdings, 13F, 1-minute intraday, full history, and bulk delivery.

**Cons**

- Not a direct fix for the current blockers.
- Fundamentals are lower-frequency and more useful for medium/long horizon models than the current multi-frequency market-data pipeline.
- Some licensing restrictions apply for display/redistribution.

**Numerical value:** 44 now; higher later if Project 3 expands into fundamental factor models.

**Decision rule:** Defer.

### Coin Metrics Pro

**Gap filled:** Could fill advanced network metrics beyond community data.

**Pros**

- High-quality API conventions, strong rate limit on paid tier, institutional-grade data.
- Community data already proved useful in Stage 1.3.

**Cons**

- Paid tier is contact-sales/institutional.
- Community offering already acquired 24h-resolution data for many metrics/assets.
- Marginal value per dollar is uncertain until quote/academic access is known.

**Numerical value:** 42 cost-adjusted; feature value would be higher if affordable.

**Decision rule:** Defer unless academic/research access is available at low cost.

## Purchase Order Recommendation

1. **First purchase/quote:** Economic calendar provider.
   - Prefer Trading Economics if it includes historical calendar, consensus/forecast, revised/previous, importance, and point-in-time fields at acceptable cost.
   - Use FXStreet if Trading Economics is too expensive and FXStreet gives the required event occurrence fields.

2. **Second purchase/trial:** CryptoQuant API.
   - Buy or trial the minimum plan that includes API access.
   - Validate with a short acquisition: BTC/ETH exchange netflow, miner flows, whale ratio, stablecoin exchange flows, leverage/market indicators.

3. **Quote only:** Glassnode Professional API add-on.
   - Valuable, but only if API cost is not excessive.
   - Do not buy non-API Studio tiers for automated acquisition.

4. **Defer:** Etherscan Pro, Polygon, FMP, Coin Metrics Pro, CoinMarketCap paid.

## Practical Budget Proposal

| Scenario | Monthly spend target | Expected value |
| --- | ---: | --- |
| Minimal blocker unlock | Calendar provider only | Unblocks macro-event features and formal Stage 1.6 decision. |
| Recommended | Calendar provider + CryptoQuant API | Best balance of macro surprise + crypto on-chain market structure. |
| Aggressive | Calendar + CryptoQuant + Glassnode API quote if reasonable | Highest crypto feature quality, but only worth it if Glassnode API pricing is sane. |

Do not exceed the budget on opaque subscriptions before one-month validation. Every paid source should be cancelled if its Stage 1.5 acquisition covers less than 80% of promised metrics or produces weak documentation/quality evidence.

## Sources Checked

- Glassnode API docs: https://docs.glassnode.com/basic-api/api
- Glassnode API key docs: https://docs.glassnode.com/basic-api/api-key
- Coin Metrics API docs: https://docs.coinmetrics.io/access-our-data/api
- Coin Metrics community resources: https://www.talos.com/our-solutions/data/community-resources
- CryptoQuant API docs: https://userguide.cryptoquant.com/api/introduction
- CryptoQuant endpoint/auth docs: https://userguide.cryptoquant.com/api/available-endpoints
- Trading Economics Calendar API: https://tr.tradingeconomics.com/api/calendar.aspx
- Trading Economics pricing/features: https://tradingeconomics.com/api/pricing.aspx?source=basic-pricing-list
- FXStreet Calendar API: https://docs.fxstreet.com/api/calendar/
- Etherscan Pro endpoints: https://docs.etherscan.io/resources/pro-endpoints
- Polygon/Massive pricing: https://polygon.io/pricing
- FMP pricing: https://intelligence.financialmodelingprep.com/pricing-plans?direct=true
