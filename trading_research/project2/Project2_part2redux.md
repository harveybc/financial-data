# Project 2 — Part II-Redux Execution Plan (FINAL, Credentials Embedded)

**Supersedes:** Original Part II execution plan (results invalidated by synthetic GBM data fallback)

**Status:** Ready for agent execution. Most credentials provided. OANDA pending (non-blocking).

**Temporal scope:** 2005-2025 (21 years). In-sample: 2005-2019. Held-out: 2020-2025.

---

## 0. CRITICAL: Security and Handling of Credentials

This plan contains live credentials. Agent MUST observe these rules:

1. **Do NOT commit this file or any file containing these credentials to git.** Add to `.gitignore` immediately.
2. **Do NOT echo credentials into logs, stdout, stderr, or any file visible in git.** Scripts load credentials from environment variables, not hardcoded strings.
3. **Do NOT reproduce credentials in deliverable markdown documents.** Reference "TrueFX credentials from plan" not actual username.
4. **After Part II-Redux completes, user will rotate credentials.** TrueFX password changeable, FRED key regeneratable.
5. **This plan file should have restrictive permissions:** `chmod 600` on any machine where copied.

### 0.1 Credentials (for agent use only)

**TrueFX:**
- Username: `<set via TRUEFX_USER>`
- Password: `[REDACTED_COMPROMISED_PASSWORD]`

**FRED API:**
- API Key: `[REDACTED_COMPROMISED_KEY]`

**OANDA:** PENDING (user email not received yet). Non-blocking. Agent proceeds without it.

### 0.2 Secure credential loading pattern

Agent creates `trading_research/project2/part_II_redux/.env` (gitignored):

```
# DO NOT COMMIT - credentials for Part II-Redux
export TRUEFX_USER="<set locally>"
export TRUEFX_PASS="[REDACTED_COMPROMISED_PASSWORD]"
export FRED_API_KEY="[REDACTED_COMPROMISED_KEY]"
# OANDA_TOKEN="<pending>"
# OANDA_ACCOUNT_ID="<pending>"
# OANDA_ENV="practice"
```

Python scripts load via `os.environ.get()`. Never hardcode.

---

## 1. CRITICAL: SSH Conda Environment Activation

The auto-activation in `.bashrc` does NOT fire for non-interactive SSH sessions because `.bashrc` has early-exit for non-interactive shells. Every SSH command must explicitly source conda.sh and activate env.

### 1.1 Standard command prefix

Every SSH command must start with:

```bash
source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && <command>
```

### 1.2 Agent SSH helper

Agent creates helper function to ensure all remote commands activate env:

```python
import subprocess

def run_on_machine(host: str, command: str, cwd: str = None, pythonpath: list = None) -> subprocess.CompletedProcess:
    """Execute command on remote machine with conda env activated."""
    prefix = "source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow"
    if pythonpath:
        paths = ":".join(pythonpath) + ":$PYTHONPATH"
        prefix += f" && export PYTHONPATH={paths}"
    if cwd:
        prefix += f" && cd {cwd}"
    full_command = f"{prefix} && {command}"
    return subprocess.run(
        ["ssh", host, full_command],
        capture_output=True,
        text=True,
        timeout=None,
    )
```

All remote execution goes through this helper. No exceptions.

### 1.3 PYTHONPATH per script

Scripts using project repos need PYTHONPATH set. Common bases:

```
/home/harveybc/Documents/GitHub/feature-eng
/home/harveybc/Documents/GitHub/heuristic-strategy
/home/harveybc/Documents/GitHub/preprocessor
/home/harveybc/Documents/GitHub/predictor
/home/harveybc/Documents/GitHub/lts
/home/harveybc/Documents/GitHub/causal-inference
```

Agent sets per-script based on imports needed.

### 1.4 Machine verification at II-0 start

Agent verifies SSH + conda activation on all 3 machines before any stage work:

```bash
# Test per machine:
ssh <host> "source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && python -c 'import sys; print(sys.executable)'"
# Expected: prints path ending in /anaconda3/envs/tensorflow/bin/python
```

If any machine fails, agent produces `ESCALATION_machine_access.md` and halts.

---

## 2. Agent Contract

### 2.1 Agent executes autonomously

- All code (scripts, orchestrator, analysis)
- APIs without credentials (yfinance, Binance public, CFTC bulk)
- Credentialed APIs using env vars (TrueFX, FRED)
- Data validation, preprocessing, feature engineering
- Model training, evaluation, reporting
- Document writing

### 2.2 Agent MUST request via `REQUEST_USER_[item].md`

- HistData paths (user already downloaded; agent needs paths)
- OANDA credentials (if/when user receives email)
- Asset selection decision at Stage II-0.6
- Any scope decision affecting multiple stages
- Any situation not covered by this plan

### 2.3 Agent MUST escalate via `ESCALATION_[stage].md`

- Any synthetic data fallback consideration — PROHIBITED, halt and escalate
- SSH access or conda activation failure
- Credential authentication failure
- Data validation test failure at Stage II-0b
- Unexpected result contradicting prior findings

### 2.4 Absolute prohibitions

- **No synthetic data. Ever.** If real data unavailable, HALT and escalate.
- **No silent fallback.** All deviations from plan are escalations.
- **No stage advancement without user gate.** Each stage reports and waits.
- **No committing credentials to git.**
- **No touching held-out data (2020-2025) during tuning.** Only at final eval per experiment.

### 2.5 Progress logging

Each machine maintains `logs/[machine]_progress_redux.log`:

```
[timestamp] [stage] [action]
[timestamp] REQUEST_USER: [item] - waiting
[timestamp] RESUMED: [item] received
[timestamp] COMPLETED: [deliverable]
[timestamp] ESCALATION: [reason]
```

---

## 3. Temporal Scope

- **In-sample (IS):** 2005-01-01 to 2019-12-31 (15 years). Training and validation windows.
- **Held-out (HO):** 2020-01-01 to 2025-12-31 (6 years). Touched exactly once per experiment at final eval.

**Rationale:** User downloaded 2005-2025. Held-out extended to include 2025 for additional stress test year (post-inflation cycle FX regime). In-sample matches Project 1.

---

## 4. Stage Structure

| Stage | Focus | Primary Machines | Gate |
|-------|-------|------------------|------|
| **II-0** | Data acquisition and processing | Omega | Real data consolidated |
| **II-0b** | Data validation gate (6 tests) | Omega | All tests pass |
| **II-0.5** | Cross-asset causal comparison | Dragon | 14 PCMCI+ runs documented |
| **II-0.6** | User asset selection | (User) | Primary asset chosen |
| **II-1** | Infrastructure validation on real data | Omega | Pilot validated |
| **II-2** | Static baseline replay (2 strategies) | Omega | Baselines established |
| **II-3** | Path A execution | Omega + Gamma | Path A classified |
| **II-4** | CI-2 refinement | Dragon | Path B go/no-go |
| **II-5** | Path B execution (conditional) | Dragon + Gamma | Path B classified |

---

## 5. Stage II-0: Data Acquisition

### 5.1 Directory setup

Agent creates:

```
trading_research/project2/part_II_redux/
├── .env                    # credentials (gitignored)
├── .gitignore
├── infrastructure/         # copied from part_II
├── scripts/
├── data/
│   ├── raw/
│   │   ├── histdata/
│   │   ├── truefx/
│   │   ├── oanda/
│   │   ├── binance/
│   │   ├── yfinance/
│   │   ├── fred/
│   │   └── cftc/
│   └── processed/
├── deliverables/
├── logs/
└── requests/
```

`.gitignore` includes:

```
.env
data/raw/**
logs/
__pycache__/
*.pyc
```

### 5.2 REQUEST_USER_histdata_paths.md

Agent produces at II-0 start:

```
# REQUEST_USER: HistData Path Confirmation

User has downloaded HistData 1-minute ASCII zips for 2005-2025 (EUR/USD and USD/JPY).
Agent needs exact directory paths.

## What user provides (reply in chat):

- EUR/USD zips directory path: [full path]
- USD/JPY zips directory path: [full path]
- Number of EUR/USD zips: [should be ~21 for 2005-2025]
- Number of USD/JPY zips: [should be ~21]

## Status: WAITING
```

Agent HALTS on this REQUEST until user responds with paths.

### 5.3 HistData processing

Once paths received, `scripts/process_histdata.py` executes:

```
For each asset (eurusd, usdjpy):
  1. List zips in provided directory
  2. Verify count matches years 2005-2025 (expect 21)
  3. Unzip all to temp directory
  4. Parse each CSV (HistData ASCII format: YYYYMMDD HHMMSS;O;H;L;C;V)
  5. Concatenate all years, sort by timestamp
  6. Verify monotonic, no duplicates
  7. Resample 1min → 1h (OHLCV aggregation: O=first, H=max, L=min, C=last, V=sum)
  8. Validate: bar count realistic, no gaps >1h during trading hours
  9. Output: data/raw/histdata/{asset}_1h_2005_2025.csv
```

Runtime estimate (IO-bound): ~15 min per asset on Omega.

### 5.4 TrueFX download

`scripts/download_truefx.py` uses env vars:

```python
import os
import requests
# ...
username = os.environ['TRUEFX_USER']
password = os.environ['TRUEFX_PASS']

for asset in ['EURUSD', 'USDJPY']:
    for year in range(2009, 2026):
        for month in range(1, 13):
            # Authenticate + download monthly zip
            # Based on github.com/Sebastiaan76/truefx-downloader pattern
            pass

# Parse tick CSVs (asset,timestamp,bid,ask)
# Resample to 1h bars (use bid mid)
# Output: data/raw/truefx/{asset}_1h_2009_2025.csv
```

### 5.5 Cross-validation HistData vs TrueFX

After both downloaded, `scripts/validate_histdata_truefx.py`:

```
For overlap period 2009-01 to 2025-12 per asset:
  Align 1h bars by timestamp
  For each bar:
    diff = |histdata_close - truefx_close|
  Report:
    - Mean absolute diff
    - Max diff
    - % bars agreeing within 1 pip
    - % bars agreeing within 2 pips
    - % bars agreeing within 5 pips
  PASS threshold: >95% agree within 2 pips
  FAIL: produce ESCALATION_cross_validation.md
```

### 5.6 Other sources (no credentials)

**Binance (BTC/USD):**

```python
# scripts/fetch_binance.py
# Public REST API, no auth
# Fetch BTC/USDT 4h and daily from 2017-08-17 (Binance BTCUSDT launch) to present
```

Output: `data/raw/binance/btcusd_{4h,daily}_2017_2025.csv`

**yfinance (SPY):**

```python
# scripts/fetch_yfinance_spy.py
import yfinance as yf
spy = yf.download('SPY', start='1993-01-29', end='2025-12-31', interval='1d')
```

Output: `data/raw/yfinance/spy_daily_1993_2025.csv`

**CFTC:**

```python
# scripts/fetch_cftc.py
# CFTC publishes annual bulk CSV zips at cftc.gov/files/dea/history/
# Extract EUR FX + JPY FX non-commercial net positioning
```

Output: `data/raw/cftc/{eur,jpy}_weekly_2000_2025.csv`

**FRED:**

```python
# scripts/fetch_fred_macro.py
from fredapi import Fred
fred = Fred(api_key=os.environ['FRED_API_KEY'])
series = {
    'DGS10': 'us_10y_yield',
    'DTWEXBGS': 'dxy_proxy',
    'VIXCLS': 'vix',
    'CPIAUCSL': 'cpi',
    'UNRATE': 'unemployment',
    'IRLTLT01EZM156N': 'eu_long_term_rate',
}
# Fetch each, forward-fill to daily
```

Output: `data/raw/fred/macro_{daily,monthly}_1990_2025.csv`

### 5.7 OANDA topup (pending, non-blocking)

Agent proceeds without. If user provides OANDA credentials mid-execution:

```python
# scripts/oanda_topup.py (executes only when OANDA_TOKEN set)
from oandapyV20 import API
api = API(access_token=os.environ['OANDA_TOKEN'], environment=os.environ['OANDA_ENV'])
# Fetch EUR/USD and USD/JPY 1h for held-out 2020-2025
# Cross-validate against HistData held-out
```

### 5.8 Consolidation

`scripts/consolidate_data.py`:

```
Primary source per asset:
  EUR/USD: HistData 2005-2025
  USD/JPY: HistData 2005-2025
  SPY: yfinance 1993-2025
  BTC/USD: Binance 2017-2025

Validation/secondary (where available):
  EUR/USD: TrueFX 2009-2025 (overlap validation)
  USD/JPY: TrueFX 2009-2025
  OANDA: 2020-2025 (if credentials arrived)

Resample to:
  FX: 4h, daily, weekly from 1h
  Crypto: 4h, daily, weekly from 4h base
  Equity: daily, weekly from daily base

Output:
  data/processed/{asset}_{timeframe}_{start}_2025.csv
```

### 5.9 Deliverable II-0

`STAGE_II-0_DATA_ACQUISITION_REPORT.md`:

- HistData paths, bar counts per asset per timeframe
- TrueFX download results, cross-validation agreement rates
- Binance, yfinance, CFTC, FRED results
- OANDA status (pending or integrated)
- Final consolidated file inventory
- Any escalations

### 5.10 Gate to II-0b

Expected consolidated bar counts:

- EUR/USD 1h: ~130,000 bars (2005-2025)
- EUR/USD 4h: ~33,000
- EUR/USD daily: ~5,500
- EUR/USD weekly: ~1,100
- USD/JPY: similar
- SPY daily: ~8,000
- BTC/USD 4h: ~18,000 (2017-2025)
- BTC/USD daily: ~3,000

User confirms, agent proceeds.

---

## 6. Stage II-0b: Data Validation Gate

### 6.1 Six tests per asset × timeframe

**Test 1: Bar count realistic.** ±10% of expected.

**Test 2: Weekend gap (FX + equity only).** Zero weekend bars for FX/SPY; Friday-Monday gap ~65h. BTC exempt (24/7).

**Test 3: Fat-tail kurtosis.**
- Real FX/equity/crypto: kurtosis > 4 on returns
- GBM: kurtosis = 3
- PASS: kurtosis > 4
- FAIL: kurtosis ∈ [2.5, 3.5]

**Test 4: Volatility clustering.**
- ACF(1) of squared returns
- PASS: > 0.05
- FAIL: < 0.02

**Test 5: Tiny nonzero return autocorrelation.**
- ACF(1) of raw returns
- PASS: |ACF| > 0.005
- FAIL: |ACF| < 0.001

**Test 6: Combined no-GBM fingerprint.**
- Ljung-Box on r² → reject at p < 0.01
- Jarque-Bera on r → reject at p < 0.01
- Runs test on sign(r) → reject at p < 0.05
- PASS: ≥2 of 3 reject null

### 6.2 Action on failure

Any failure → `ESCALATION_II-0b.md` with asset×timeframe, test, actual vs expected values. HALT. No retry.

### 6.3 Deliverable

`STAGE_II-0b_DATA_VALIDATION_REPORT.md`: pass/fail matrix with actual values, distribution plots.

### 6.4 Gate

All tests pass. User approves.

---

## 7. Stage II-0.5: Cross-Asset Causal Comparison

### 7.1 Analysis matrix (14 runs)

| Asset | Timeframe | Features |
|-------|-----------|----------|
| EUR/USD | 4h | 12 tech |
| EUR/USD | daily | 12 tech |
| EUR/USD | daily | 12 tech + 4 macro |
| EUR/USD | weekly | 12 tech |
| USD/JPY | 4h | 12 tech |
| USD/JPY | daily | 12 tech |
| USD/JPY | daily | 12 tech + 4 macro |
| USD/JPY | weekly | 12 tech |
| SPY | daily | 12 tech |
| SPY | daily | 12 tech + 4 macro |
| SPY | weekly | 12 tech |
| BTC/USD | 4h | 12 tech |
| BTC/USD | daily | 12 tech |
| BTC/USD | weekly | 12 tech |

### 7.2 Method

Per original Stage II-4:
- PCMCI+ with RobustParCorr
- τ_max = 10
- pc_alpha = 0.01
- alpha_level = 0.05
- Target: 6-bar forward log return

### 7.3 Features

**Technical (12, from F-6 set):** adx, di_spread, atr_pct, atr_ratio, bb_width_pct, bb_position, rsi, roc_12, price_vs_ema50, ema_alignment, stoch_k, macd_hist.

**Macro (4, FX + SPY only):**
- EUR/USD: us_eu_rate_diff, dxy, vix, eur_net_pos
- USD/JPY: us_jp_rate_diff, dxy, vix, jpy_net_pos
- SPY: us_10y_yield, dxy, vix, spy_fund_flow (if available, else skip)

BTC: technical only (no conventional macro linkage).

### 7.4 Classification per run

- **α:** ≥1 lagged link with MCI > 0.10 and p < 0.01
- **β:** ≥1 lagged link with MCI ∈ [0.05, 0.10] and p < 0.05
- **γ:** no lagged links with MCI > 0.05

### 7.5 Parallelization

Dragon runs PCMCI+ serially (each ~4-8 min).

Optional distribution if agent implements:
- Omega: EUR/USD 4 runs
- Dragon: USD/JPY + SPY 7 runs
- Gamma: BTC/USD 3 runs

### 7.6 Deliverable

`STAGE_II-0.5_CROSS_ASSET_CAUSAL.md`: ranked summary table + detailed appendix + interpretation (which combos support Path B vs Path A only).

### 7.7 Gate

14 runs complete and documented.

---

## 8. Stage II-0.6: User Asset Selection

Agent produces `REQUEST_USER_asset_selection.md` with II-0.5 summary + scenario template (A/B/C/D from Part II-Redux earlier plan).

User responds with:
- Primary asset + timeframe
- Secondary asset + timeframe (or "none")
- Path B enablement (enabled/disabled/conditional)
- Feature set (technical only / technical + macro)

Agent documents in `STAGE_II-0.6_ASSET_SELECTION.md`.

---

## 9. Stage II-1: Infrastructure Validation on Real Data

Re-use rolling orchestrator from original Part II. Validate on real chosen asset × timeframe.

Tasks:
- Load real data for chosen primary
- Generate window manifest for 2005-2019 IS
- Pilot single-window end-to-end with fixed params
- Verify: slicing, no look-ahead, embargo, metrics, F-5 §7 CSV format

Deliverable: `STAGE_II-1_REDUX_INFRASTRUCTURE_REPORT.md`

Gate: pilot runs clean on real data.

---

## 10. Stage II-2: Static Baselines (Two Strategies)

### 10.1 Two baselines

1. **`regime_adaptive` fixed defaults** — from heuristic-strategy
2. **`eurusd_mr` from LTS** (or equivalent for chosen asset) — real P1 strategy

### 10.2 Integration note

`eurusd_mr` is at `lts/plugins_strategy/eurusd_mr_strategy.py`. Agent integrates LTS plugin loading into rolling orchestrator (not in original Part II).

If primary asset is not EUR/USD:
- USD/JPY: find equivalent LTS TSMOM or DM strategy
- SPY: create simple MR baseline (z-score)
- BTC: create simple momentum baseline

### 10.3 Deliverable

`STAGE_II-2_REDUX_BASELINE_VALIDATION.md`: per-window results for both baselines + buy-and-hold + random + zero benchmarks.

### 10.4 Gate

Both baselines documented.

---

## 11. Stage II-3: Path A Execution

### 11.1 Configuration matrix

| Exp | Strategy | Optimizer | Trigger | Priority |
|-----|----------|-----------|---------|----------|
| A1 | strategy_1 (primary) | DEAP GA | Yearly | HIGH |
| A2 | strategy_1 | DEAP GA | Monthly | HIGH |
| A3 | strategy_1 | DEAP GA | Change-point (UL-2) | MEDIUM |
| A4 | regime_adaptive | DEAP GA | Yearly + rolling GMM (UL-1) | HIGH |
| A5 | regime_wfo | DEAP GA | Yearly | MEDIUM |
| A6 | strategy_1 | NEAT-HPO | Yearly | MEDIUM |
| A7 | regime_adaptive | DEAP GA | Weekly | LOW |

### 11.2 Procedure

Per original Part II §4.3.

### 11.3 Evaluation

F-10 kill criteria K-1 through K-7. Deflated Sharpe accounts for 7 configs.

### 11.4 Deliverable

`STAGE_II-3_REDUX_PATH_A_SYNTHESIS.md`.

### 11.5 Decision

PA-α / PA-β / PA-γ. On real data, so valid.

---

## 12. Stage II-4: CI-2 Refinement

Reduced scope because II-0.5 already covered multi-asset multi-timeframe.

Tasks:
- Install ortools on Dragon: `pip install ortools`
- Attempt RPCMCI on primary asset (time-boxed)
- Asset-specific deeper analysis if warranted

Deliverable: `STAGE_II-4_REDUX_CI_REFINEMENT.md`

Decision: CI-α / CI-β / CI-γ for primary asset.

---

## 13. Stage II-5: Path B (Conditional)

Entry: II-0.6 Path B enabled AND II-4 α or β.

Config matrix per original Part II §6.3 (Ridge, LightGBM, TFT, CNN, LSTM, TCN, Phase 1/2, binary).

Procedure per original §6.4.

Evaluation per original §6.5.

Deliverable: `STAGE_II-5_REDUX_PATH_B_SYNTHESIS.md`.

---

## 14. Part II-Redux Final Synthesis

`PART_II_REDUX_FINAL_SYNTHESIS.md`:
- Stage summaries
- II-0.5 cross-asset findings
- Chosen asset rationale
- Best Path A with real-data metrics
- Best Path B with real-data metrics (if executed)
- Hypothesis verdict
- Part III scope recommendation

---

## 15. Transition from Failed Part II

Agent before II-0:

1. Archive `part_II/` to `part_II_invalidated/`
2. Create `INVALIDATION_NOTE.md` in archive: "Results invalidated — operated on synthetic GBM data via silent fallback. See Part II-Redux."
3. Create fresh `part_II_redux/` per §5.1
4. Copy reusable code: `part_II/infrastructure/` → `part_II_redux/infrastructure/`
5. Do NOT copy `part_II/data/` (synthetic).

---

## 16. Machine Assignment

| Stage | Omega | Dragon | Gamma |
|-------|-------|--------|-------|
| II-0 | HistData, TrueFX, others, consolidation | idle | idle |
| II-0b | validation | idle | idle |
| II-0.5 | optional parallel | 14 PCMCI+ | optional parallel |
| II-0.6 | (waiting for user) | idle | idle |
| II-1 | orchestrator validation | idle | idle |
| II-2 | baselines | idle | idle |
| II-3 | A1-A3 serial | CI-2 prep | A4-A7 parallel |
| II-4 | idle | RPCMCI + refinement | idle |
| II-5 | B1-B2 linear/tree | B3-B6 neural | B7-B8-B9 |

---

## 17. Immediate Next Actions

**For user (you):**

1. Review this plan
2. Start agent. Tell agent: "Execute work plan at path. Begin Stage II-0 setup. Produce REQUEST_USER_histdata_paths.md and wait for my response."
3. When agent produces the HistData paths request, reply in chat with actual paths and zip counts.
4. Monitor `logs/*_progress_redux.log` as needed.
5. When OANDA email arrives, respond with token + account ID + environment "practice".
6. Review each stage deliverable before approving next stage gate.

**For agent at II-0 start:**

1. `git status` — verify clean working directory
2. Create redux directory tree per §5.1
3. Write `.gitignore` with .env, data/raw/**, logs/, __pycache__/
4. Write `.env` with TrueFX + FRED credentials from §0.2
5. Archive original Part II per §15
6. Copy reusable infrastructure
7. Verify SSH + conda activation on all 3 machines per §1.4
8. Build data processing scripts: process_histdata, download_truefx, fetch_binance, fetch_yfinance_spy, fetch_cftc, fetch_fred_macro, consolidate_data, validate_data
9. Produce `REQUEST_USER_histdata_paths.md`
10. HALT waiting for user HistData paths
11. Upon receipt: run process_histdata.py on Omega
12. Run download_truefx.py using env var credentials
13. Run Binance + yfinance + CFTC + FRED in parallel (non-blocking on each other)
14. Run consolidation
15. Run cross-validation (HistData vs TrueFX)
16. Produce STAGE_II-0_DATA_ACQUISITION_REPORT.md
17. HALT at user gate before II-0b

---

## 18. Honest Acknowledgments

1. **Original Part II invalidated.** This plan explicitly prohibits synthetic fallback.

2. **II-0.5 corrects F-4 error.** Asset selection now evidence-based.

3. **All-γ possibility.** If all 4 assets return null at II-0.5, that is strong evidence about retail-accessible markets. Path A still viable (regime adaptation, no prediction needed), Path B likely disabled.

4. **Credentials embedded for efficiency.** User rotates after completion.

5. **OANDA non-blocking.** Cross-validation from HistData + TrueFX sufficient if OANDA absent.

6. **SSH conda activation critical.** §1 helper is mandatory. Env not auto-activates in non-interactive SSH.

7. **21 years instead of 20.** Extra 2025 data used, held-out extended to 2020-2025.

---

## 19. Dependency Graph

```
START
  │
  ▼
Agent setup (directory, .env, .gitignore, archive, infrastructure copy, SSH verify)
  │
  ▼
Agent builds scripts + produces REQUEST_USER_histdata_paths.md
  │
  ▼ (user responds with paths)
HistData processing + TrueFX download + Binance + yfinance + CFTC + FRED (parallel where possible)
  │
  ▼
Cross-validation HistData vs TrueFX + Consolidation
  │
  ▼
STAGE_II-0 deliverable → USER GATE
  │
  ▼
II-0b Data Validation (6 tests per asset × timeframe)
  │
  ├── ANY FAIL → ESCALATION, HALT
  └── ALL PASS → USER GATE
  │
  ▼
II-0.5 Cross-Asset Causal (14 PCMCI+ on Dragon)
  │
  ▼
STAGE_II-0.5 deliverable → USER GATE
  │
  ▼
II-0.6 REQUEST_USER_asset_selection
  │
  ▼ (user chooses)
II-1 Infrastructure Validation → USER GATE
  │
  ▼
II-2 Baselines → USER GATE
  │
  ▼
II-3 Path A → USER GATE
  │
  ▼
II-4 CI-2 Refinement
  │
  ├── CI-α/β + Path B enabled → II-5 Path B → USER GATE
  └── CI-γ OR Path B disabled → skip II-5
  │
  ▼
PART_II_REDUX_FINAL_SYNTHESIS → USER reviews, decides Part III
```

---

## 20. Approval

User approves and starts agent. Agent begins §17 action list.