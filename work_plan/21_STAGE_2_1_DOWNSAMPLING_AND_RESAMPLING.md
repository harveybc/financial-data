# Stage 2.1 — Downsampling and Resampling

**Stage goal:** Take all raw data acquired in Phase 1 and produce a unified multi-timeframe aligned dataset structure ready for feature computation.

**Inputs:** Phase 1 complete with all raw data acquired and validated.

**Outputs:**
- For each trading asset candidate: 5m, 15m, 1h, 4h OHLCV files (downsampled or upsampled as needed)
- For each cross-source feature input: forward-filled to each simulation timeframe (5m, 15m, 1h, 4h)
- Manifest documenting all aligned datasets

**Machine assignment:**
- **Omega:** Light tasks (FX resampling, equity index forward-fill)
- **Dragon:** Heavy tasks (top 50 crypto across timeframes)
- **Gamma:** Cross-source forward-fill (FRED + on-chain + others to all 4 sim timeframes)

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

## 1. Resampling Rules (Strict)

### Rule R.1: Downsampling (lower frequency from higher)

Going from 5m → 15m: aggregate 3 consecutive 5m bars
- Open: first bar's open
- High: max across 3 bars' highs
- Low: min across 3 bars' lows
- Close: last bar's close
- Volume: sum across 3 bars

Going 5m → 1h: aggregate 12 consecutive 5m bars (same logic)
Going 5m → 4h: aggregate 48 consecutive 5m bars
Going 1h → 4h: aggregate 4 consecutive 1h bars

### Rule R.2: Upsampling (higher frequency from lower) — for forward-fill of cross-source features

Going from daily → 1h: forward-fill (carry last value)
Going from monthly → daily → 1h: chain of forward-fills

NEVER interpolate. Always forward-fill (no look-ahead via interpolation).

### Rule R.3: Native frequency preferred

If source provides data at requested timeframe natively, use native. Don't downsample 5m to make 1h if the source has 1h directly (e.g., Binance API can fetch 1h directly).

### Rule R.4: Timezone alignment

All timestamps in UTC. Bars are right-aligned (close time).

For session-based assets (FX, equities), preserve session boundaries:
- FX week starts Sunday 22:00 UTC, ends Friday 22:00 UTC
- US equities session 14:30 UTC to 21:00 UTC weekdays
- Crypto: 24/7 no boundaries

---

## 2. Task 2.1.A: Trading asset multi-timeframe (Omega/Dragon parallel)

For each trading asset candidate identified in Phase 1 INVENTORY.md:

```python
ASSETS_TO_PROCESS = [
    # FX (10 G10 pairs)
    {"name": "eurusd", "raw_path": "market_data/forex/g10/eurusd/", "raw_periodicity": "5m"},
    {"name": "usdjpy", "raw_path": "market_data/forex/g10/usdjpy/", "raw_periodicity": "5m"},
    # ... all 10 G10 pairs
    
    # Crypto top 50
    {"name": "btcusdt", "raw_path": "market_data/crypto/spot_top50/btcusdt/", "raw_periodicity": "5m"},
    {"name": "ethusdt", "raw_path": "market_data/crypto/spot_top50/ethusdt/", "raw_periodicity": "5m"},
    # ... all top 50 crypto
    
    # Crypto perpetuals (top 10)
    {"name": "btcusdt_perp", "raw_path": "market_data/crypto/perpetuals/btcusdt_perp/", "raw_periodicity": "5m"},
    # ...
]

TARGET_TIMEFRAMES = ["5m", "15m", "1h", "4h"]

for asset in ASSETS_TO_PROCESS:
    raw_5m = load_parquet(asset["raw_path"] + "5m.parquet")
    
    # Already have 5m
    save_parquet(raw_5m, f"trading_asset_data/{asset['name']}/5m.parquet")
    
    # Resample to 15m, 1h, 4h
    for tf in ["15m", "1h", "4h"]:
        resampled = resample_ohlcv(raw_5m, target_freq=tf)
        validate_resampled(resampled, expected_freq=tf)
        save_parquet(resampled, f"trading_asset_data/{asset['name']}/{tf}.parquet")
```

**Important:** The script does NOT just save resampled OHLCV. It also produces metadata:
- Bar count actual vs expected
- Coverage start/end matches input
- Timezone confirmed UTC

---

## 3. Task 2.1.B: Cross-source forward-fill (Gamma)

For each cross-source feature input from Phase 1, forward-fill to all 4 simulation timeframes.

```python
CROSS_SOURCES = [
    # FRED macro (daily and monthly)
    {"name": "fred_inflation_cpi", "path": "macro_economic/fred/inflation/CPIAUCSL.csv", "native_freq": "monthly"},
    {"name": "fred_unrate", "path": "macro_economic/fred/employment/UNRATE.csv", "native_freq": "monthly"},
    {"name": "fred_dgs10", "path": "macro_economic/fred/rates/DGS10.csv", "native_freq": "daily"},
    # ... ~150 FRED series
    
    # Equity indices (daily)
    {"name": "spx", "path": "market_data/equities/us_indices/spx/daily.csv", "native_freq": "daily"},
    {"name": "vix", "path": "market_data/equities/us_indices/vix/daily.csv", "native_freq": "daily"},
    # ... all indices
    
    # On-chain (daily)
    {"name": "btc_addr_active", "path": "alternative_data/onchain_btc/coinmetrics_community/AdrActCnt.csv", "native_freq": "daily"},
    # ... on-chain metrics
    
    # Funding rates (8h)
    {"name": "funding_btc", "path": "market_data/crypto/funding_rates/binance/funding_btcusdt.csv", "native_freq": "8h"},
    # ...
    
    # COT (weekly)
    {"name": "cot_eur", "path": "alternative_data/cot_reports/cftc/eur_weekly.csv", "native_freq": "weekly"},
    # ...
    
    # Economic calendar release values (event-based)
    {"name": "cpi_releases", "path": "economic_calendar/release_actuals/cpi_yoy.csv", "native_freq": "monthly"},
    # ...
]

TARGET_TIMEFRAMES = ["5m", "15m", "1h", "4h"]

for source in CROSS_SOURCES:
    native_data = load_csv(source["path"])
    
    # Validate timestamps in UTC, sorted, no duplicates
    validate_timestamps(native_data)
    
    for tf in TARGET_TIMEFRAMES:
        # Generate timestamp grid at target frequency for full coverage
        target_index = generate_timestamp_grid(tf, start=earliest, end="2025-12-31")
        
        # Forward-fill source data onto target grid (no look-ahead)
        ffilled = forward_fill_to_grid(native_data, target_index)
        
        # Validate no look-ahead: at any time t, value should equal last known value at <= t
        validate_no_lookahead(ffilled, native_data)
        
        save_parquet(ffilled, f"features/cross_source_features/{tf}/{source['name']}.parquet")
```

---

## 4. Task 2.1.C: Generate manifest (Omega)

Script: `_scripts/generate_manifest.py`

After Tasks 2.1.A and 2.1.B complete, produce manifest documenting all aligned data:

`features/MANIFEST.json`:

```json
{
  "trading_assets": {
    "eurusd": {
      "timeframes": {
        "5m": {
          "path": "trading_asset_data/eurusd/5m.parquet",
          "bars": 2150400,
          "coverage": ["2005-01-03 00:00", "2025-12-31 22:00"],
          "validation_status": "PASS"
        },
        "15m": {...},
        "1h": {...},
        "4h": {...}
      }
    },
    "btcusdt": {...},
    ...
  },
  "cross_source_features": {
    "5m": {
      "fred_inflation_cpi": {
        "path": "features/cross_source_features/5m/fred_inflation_cpi.parquet",
        "native_freq": "monthly",
        "ffill_method": "forward_fill_no_interpolation",
        "coverage": ["2005-01-03 00:00", "2025-12-31 22:00"],
        "missing_pct": 0.0
      },
      ...
    },
    "15m": {...},
    "1h": {...},
    "4h": {...}
  }
}
```

This manifest is used by all subsequent Phase 2 stages and Phase 3 experiments.

---

## 5. Validation per Resampled/Forward-Filled Dataset

For each output, run:

1. **Continuity check:** No unexpected gaps in timestamps
2. **No look-ahead:** Forward-fill values are last known at each timestamp
3. **Volume conservation (downsampled OHLCV):** Sum of finer-frequency volumes equals coarser-frequency volume
4. **High/Low integrity:** High >= max(O, C), Low <= min(O, C) for all bars

If any test fails: ESCALATION + halt.

---

## 6. Stage 2.1 Deliverable

`STAGE_2.1_DELIVERABLE.md`:

```markdown
# Stage 2.1 Deliverable — Downsampling and Resampling

## Trading Assets Processed

| Asset | 5m | 15m | 1h | 4h | Coverage |
|-------|----|----|----|----|----------|
| EUR/USD | ✓ | ✓ | ✓ | ✓ | 2005-2025 |
| USD/JPY | ✓ | ✓ | ✓ | ✓ | 2005-2025 |
| ... | | | | | |

Total trading assets: [N]

## Cross-Source Features Forward-Filled

| Source | 5m | 15m | 1h | 4h | Native freq |
|--------|----|----|----|----|-------------|
| FRED CPI | ✓ | ✓ | ✓ | ✓ | monthly |
| FRED Unemployment | ✓ | ✓ | ✓ | ✓ | monthly |
| ... | | | | | |

Total cross-source features: [N]

## Manifest

Generated at `features/MANIFEST.json`
[stats]

## Validation

All datasets pass continuity + look-ahead + integrity checks.

## User Gate

User reviews manifest. Approves Stage 2.2 start.
```

---

## 7. User Gate

User approves Stage 2.2.
