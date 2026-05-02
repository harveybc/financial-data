# Stage 1.5 — Paid Data Acquisition

**Stage goal:** Acquire ONLY the paid subscription data sources approved at Stage 1.3 user gate. Use Stage 1.3 inventory to ensure no redundancy with already-acquired free data.

**Inputs:** Stage 1.4 complete with credentials validated. Stage 1.3 inventory enumerates exactly what gaps the paid subscriptions are filling.

**Outputs:** Approved paid sources downloaded to target folders with full documentation. Subscriptions found mediocre during acquisition are flagged for cancellation.

## 2026-05-01 Execution Status

- **FXMacroData:** approved and acquired. Deliverables are `economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet` and `economic_calendar/release_actuals/fxmacrodata/announcements.parquet`; summary is `_logs/supervisor_reports/stage15_fxmacrodata_acquisition.md`.
- **CryptoQuant Professional:** approved and acquired. Deliverable is `alternative_data/cryptoquant/`; summary is `_logs/supervisor_reports/stage15_cryptoquant_acquisition.md`. Treat coverage as recent-window daily data because older explicit historical ranges returned `Out of allowed request range` during validation. Follow-up value probe is `_logs/supervisor_reports/stage15_cryptoquant_value_probe.md`; current recommendation is cancel unless historical export/API coverage is enabled.
- **FXStreet/Trading Economics:** not purchased; defer unless user later approves a sales/API credential for consensus-surprise fields.
- **Massive/Polygon:** deferred unless Phase 3 explicitly needs US equity intraday/tick data.

**Machine assignment:**
- **Dragon:** Glassnode + CryptoQuant (crypto-focused, high data volume)
- **Gamma:** Polygon (US equities + options) IF approved
- **Omega:** FXMacroData macro calendar/announcements; FMP fundamentals IF approved

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

## 1. Pre-Flight Checks

```bash
source /home/harveybc/Documents/GitHub/financial-data/_metadata/.env

# Verify only approved paid credentials present
# (some may be empty if user didn't approve those subscriptions)

[[ -n "$GLASSNODE_API_KEY" ]] && echo "Glassnode active"
[[ -n "$CRYPTOQUANT_API_KEY" ]] && echo "CryptoQuant active"
[[ -n "$POLYGON_API_KEY" ]] && echo "Polygon active"
[[ -n "$FMP_API_KEY" ]] && echo "FMP active"
```

---

## 2. Anti-Redundancy Check (NEW per TODO 8)

Before fetching any paid data, agent reads Stage 1.3 inventory and verifies what's missing:

```python
import json

inventory = json.load(open("/home/harveybc/Documents/GitHub/financial-data/_metadata/STAGE_1.3_INVENTORY.json"))

# For each paid subscription approved, identify SPECIFIC metrics/data NOT in free
gaps_to_fill = []

if "glassnode" in approved_subscriptions:
    free_metrics = inventory["onchain_btc"]["coinmetrics_community"]["metrics_acquired"]
    glassnode_metrics_to_fetch = [
        m for m in GLASSNODE_STANDARD_METRICS
        if m not in free_metrics
    ]
    gaps_to_fill.append({
        "subscription": "glassnode",
        "metrics_to_fetch": glassnode_metrics_to_fetch,
    })

# Similar for other subscriptions
# Output: scripts will fetch ONLY these gap metrics
```

This prevents fetching, e.g., `addresses/active_count` from Glassnode when already acquired free from CoinMetrics.

---

## 3. Task 1.5.A: Glassnode (Dragon) — only metrics not in CoinMetrics

Script: `_scripts/fetch_glassnode_paid.py`

The script fetches ONLY Glassnode metrics not already in CoinMetrics Community tier.

```python
import requests, os
import pandas as pd
import json

GLASSNODE_KEY = os.environ['GLASSNODE_API_KEY']
BASE = "https://api.glassnode.com/v1/metrics"

# Load gap analysis from Stage 1.5 anti-redundancy check
gap_analysis = json.load(open("_metadata/glassnode_gap_analysis.json"))

# Glassnode-exclusive valuable metrics (NOT in CoinMetrics free)
GLASSNODE_EXCLUSIVE = [
    # Indicators (advanced, not in Community tier)
    "indicators/sopr",
    "indicators/sopr_adjusted",
    "indicators/cdd",
    "indicators/cyd",
    "indicators/asol",
    "indicators/msol",
    "indicators/nvts",
    "indicators/velocity",
    "indicators/stock_to_flow_ratio",
    "indicators/mayer_multiple",
    "indicators/realized_profit",
    "indicators/realized_loss",
    "indicators/net_unrealized_profit_loss",  # NUPL
    
    # Market (subset not in Community)
    "market/marketcap_realized_usd",
    "market/mvrv",
    "market/mvrv_z_score",
    
    # Supply (advanced)
    "supply/active_more_1y_percent",
    "supply/loss_sum",
    "supply/profit_sum",
    "supply/profit_relative",
    
    # Addresses (advanced — Community tier only has basic)
    "addresses/min_1k_count",
    "addresses/min_10k_count",
    "addresses/min_100k_count",
    "addresses/sending_to_exchanges_count",
    "addresses/receiving_from_exchanges_count",
    
    # Transactions (advanced)
    "transactions/transfers_to_exchanges_count",
    "transactions/transfers_from_exchanges_count",
    "transactions/transfers_volume_to_exchanges_sum",
    "transactions/transfers_volume_from_exchanges_sum",
    
    # Derivatives
    "derivatives/futures_open_interest_sum",
    "derivatives/futures_volume_daily_sum",
    "derivatives/futures_funding_rate_perpetual",
    
    # Institutions
    "institutions/grayscale_holdings_sum",
    "institutions/microstrategy_holdings_sum",
]

# ETH-specific extras
ETH_EXCLUSIVE = [
    "supply/eth/burned",
    "supply/eth/issued_pos",
    "eth2/staking_total_volume_sum",
    "eth2/staking_validators_count",
]

ASSETS = ["BTC", "ETH"]

for asset in ASSETS:
    target_dir = f"/home/harveybc/Documents/GitHub/financial-data/alternative_data/onchain_{asset.lower()}/glassnode/"
    
    metrics_for_asset = GLASSNODE_EXCLUSIVE + (ETH_EXCLUSIVE if asset == "ETH" else [])
    
    failed_metrics = []
    successful_metrics = []
    
    for metric_path in metrics_for_asset:
        url = f"{BASE}/{metric_path}"
        params = {"a": asset, "i": "24h", "api_key": GLASSNODE_KEY,
                  "s": 1230768000,  # 2009-01-01
                  "u": 1767139200}  # 2026-01-01 (covers through end 2025)
        
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                data = r.json()
                if data:
                    df = pd.DataFrame(data)
                    df["t"] = pd.to_datetime(df["t"], unit="s")
                    save_csv(df, f"{target_dir}/{metric_path.replace('/', '_')}.csv")
                    successful_metrics.append(metric_path)
            else:
                # Some metrics not available in Standard tier
                failed_metrics.append((metric_path, r.status_code))
        except Exception as e:
            failed_metrics.append((metric_path, str(e)))
    
    # Document results
    with open(f"{target_dir}/glassnode_acquisition_summary.json", "w") as f:
        json.dump({
            "asset": asset,
            "successful_metrics": successful_metrics,
            "failed_metrics": failed_metrics,
            "tier_confirmed_metrics": len(successful_metrics),
            "tier_promised_count": len(metrics_for_asset),
            "coverage_pct": 100 * len(successful_metrics) / len(metrics_for_asset),
        }, f, indent=2)

# Mediocrity check
if coverage_pct < 80:
    flag_for_cancellation_review("Glassnode")
```

If Glassnode returns <80% of expected metrics for our tier, flag for cancellation review.

---

## 4. Task 1.5.B: CryptoQuant (Dragon) — IF approved

Script: `_scripts/fetch_cryptoquant_paid.py`

If user approved CryptoQuant subscription, fetch exchange flows + miner flows + whale data. If user opted to skip CryptoQuant (Glassnode covers enough), this task is N/A.

```python
CQ_KEY = os.environ['CRYPTOQUANT_API_KEY']
BASE = "https://api.cryptoquant.com/v1"

# Focus on metrics NOT covered by Glassnode (assuming Glassnode subscribed)
# CryptoQuant unique value: exchange flows by specific exchange, miner detail

CRYPTOQUANT_UNIQUE = {
    "btc/exchange-flows/inflow": "exchange_flows",
    "btc/exchange-flows/outflow": "exchange_flows",
    "btc/exchange-flows/netflow": "exchange_flows",
    "btc/miner-flows/all-miners-inflow": "miner_flows",
    "btc/miner-flows/all-miners-outflow": "miner_flows",
    "btc/miner-flows/all-miners-reserve": "miner_flows",
    # ... more
}

# Stable coins specific
STABLECOIN_FLOWS = [
    "usdt-erc20/exchange-flows/inflow",
    "usdt-erc20/exchange-flows/outflow",
    "usdc/exchange-flows/inflow",
    "usdc/exchange-flows/outflow",
]

# Fetch all
# ...
```

---

## 5. Task 1.5.C: Polygon (Gamma) — IF approved

Script: `_scripts/fetch_polygon.py`

ONLY runs if user approved Polygon subscription. If user decided no equity intraday/options needed, this task is N/A.

If approved, focus is intraday equities (5m, 15m, 1h, 4h) which is Polygon's unique value:

```python
POLYGON_KEY = os.environ['POLYGON_API_KEY']

# S&P 500 components — intraday
sp500_tickers = load_sp500_constituents()

TIMEFRAMES = [(5, "minute"), (15, "minute"), (60, "minute"), (240, "minute")]
# 240 min = 4h (Polygon doesn't have native 4h, fetch 1h and aggregate)

for ticker in sp500_tickers:
    for multiplier, timespan in TIMEFRAMES:
        # Polygon paginated fetch
        url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/2019-01-01/2025-12-31"
        # Save as parquet
```

Plus options chains for major underlyings (SPY, QQQ, AAPL, MSFT, etc.).

---

## 6. Task 1.5.D: FMP fundamentals (Omega) — IF approved

If user approved FMP subscription, fetch comprehensive fundamentals.

If user opted to skip FMP (using SEC EDGAR XBRL parsing instead), this task is N/A.

If approved:

```python
FMP_KEY = os.environ['FMP_API_KEY']
BASE = "https://financialmodelingprep.com/api/v3"

# For each S&P 500 ticker
for ticker in SP500_TICKERS:
    # Income, balance, cashflow, ratios — quarterly + annual
    income_q = requests.get(f"{BASE}/income-statement/{ticker}?period=quarter&limit=120&apikey={FMP_KEY}").json()
    income_a = requests.get(f"{BASE}/income-statement/{ticker}?period=annual&limit=30&apikey={FMP_KEY}").json()
    balance_q = requests.get(f"{BASE}/balance-sheet-statement/{ticker}?period=quarter&limit=120&apikey={FMP_KEY}").json()
    cashflow_q = requests.get(f"{BASE}/cash-flow-statement/{ticker}?period=quarter&limit=120&apikey={FMP_KEY}").json()
    ratios = requests.get(f"{BASE}/ratios/{ticker}?limit=120&apikey={FMP_KEY}").json()
    
    save_per_ticker(...)
```

---

## 7. Validation

Same approach as Stage 1.3. Validate each acquired dataset.

For paid sources specifically, verify:
- Coverage matches subscription tier promised
- No 401/403 errors during fetches
- Sample data sanity-check

---

## 8. Mediocrity Evaluation (per Rule M.10)

After each paid subscription's data acquired:

```python
def evaluate_subscription_quality(subscription_name, acquired_data):
    issues = []
    
    # Coverage check
    expected_metrics_count = TIER_PROMISED_METRIC_COUNT[subscription_name]
    actual_metrics_count = len(acquired_data["successful_metrics"])
    if actual_metrics_count / expected_metrics_count < 0.8:
        issues.append(f"Only {actual_metrics_count}/{expected_metrics_count} metrics acquired")
    
    # Validation pass rate
    validation_pass_rate = compute_validation_pass_rate(acquired_data)
    if validation_pass_rate < 0.9:
        issues.append(f"Only {validation_pass_rate*100}% datasets pass validation")
    
    # API reliability during acquisition
    error_rate = acquired_data["http_5xx_errors"] / acquired_data["total_requests"]
    if error_rate > 0.05:
        issues.append(f"High error rate: {error_rate*100}%")
    
    return issues
```

If issues found, agent flags subscription for user review:

```markdown
# SUBSCRIPTION_REVIEW: <service>

Issues identified during acquisition:
- [issue 1]
- [issue 2]

Recommendation: cancel / keep / monitor
User decides.
```

---

## 9. Stage 1.5 Deliverable

`STAGE_1.5_DELIVERABLE.md`:

```markdown
# Stage 1.5 Deliverable — Paid Data Acquisition

## Subscriptions executed

| Service | Cost | Data acquired | Quality | Recommendation |
|---------|------|---------------|---------|----------------|
| Glassnode | $30/mo | X metrics covering BTC + ETH advanced indicators | PASS | KEEP |
| CryptoQuant | $39/mo | Exchange flows + miner flows | PASS/MEDIOCRE | KEEP/CANCEL |
| Polygon | $79/mo | (only if approved) | | |
| FMP | $14/mo | (only if approved) | | |

## Total monthly cost (active)

$[X]/month (out of $500/month cap)

## Anti-redundancy verification

For each paid source, verified that data acquired is NOT in free Stage 1.3 inventory.

[Section listing exact metrics acquired per paid source, with note "not in free inventory"]

## Cancellation flags

[List any subscriptions flagged for cancellation review with reasons]

## User Gate

User reviews. Confirms keep / cancel decisions per flagged subscriptions.
Approves Stage 1.6.
```

---

## 10. User Gate

User reviews. Decides on any flagged subscriptions. Approves Stage 1.6.
