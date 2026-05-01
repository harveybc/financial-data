# Stage 1.3 — Manual Tasks for User

**Project:** Project 3 — Comprehensive Data Acquisition for RL Trading Research
**Stage:** 1.3 (Free Data Acquisition)
**Date:** 2026-04-28
**Owner:** harveybc

---

## Overview

This document contains ALL manual tasks user must complete for Stage 1.3 to proceed. Agent automates the rest.

**Estimated total time:** 2-4 hours, mostly waiting for HistData downloads.

**You can do these tasks in parallel** while agent runs automated acquisition tasks on the 3 machines.

---

## Task Checklist

- [ok] **Task M1:** Download HistData FX additional pairs (8 pairs, 168 zips)
- [ ] **Task M2:** Verify FRED API key still valid
- [ ] **Task M3:** Register free Etherscan API key
- [ ] **Task M4 (optional):** Register CoinMarketCap free key
- [ ] **Task M5 (optional):** Register Alpha Vantage free key
- [ ] **Task M6:** Verify `.gitignore` setup for `.env` credentials
- [ ] **Task M7:** Confirm machine availability (Omega, Dragon, Gamma)

---

## Task M1: HistData FX Additional Pairs (BIGGEST TASK)

### Context

You already manually downloaded EUR/USD and USD/JPY 5m data through approximately November 2025. Stage 1.3 needs 8 additional G10 pairs at 1-minute granularity (which agent will resample to 5m, 15m, 1h, 4h after acquisition).

### What to download

For each of these **8 pairs**, download yearly 1-minute ASCII zips for **2005 through 2025** (21 zips per pair):

| # ok| Pair | Folder destination |
|-----|------|---------------------|
| 1 ok | GBP/USD | `~/Downloads/histdata/gbpusd/` |
| 2 ok | USD/CHF | `~/Downloads/histdata/usdchf/` |
| 3 ok | AUD/USD | `~/Downloads/histdata/audusd/` |
| 4 ok | USD/CAD | `~/Downloads/histdata/usdcad/` |
| 5 ok | NZD/USD | `~/Downloads/histdata/nzdusd/` |
| 6 ok | EUR/GBP | `~/Downloads/histdata/eurgbp/` |
| 7 ok | EUR/JPY | `~/Downloads/histdata/eurjpy/` |
| 8 ok | GBP/JPY | `~/Downloads/histdata/gbpjpy/` |

**Total: 168 zip files**

### Procedure (per pair)

1. Visit https://www.histdata.com/download-free-forex-data/
2. Click the pair name (e.g., "GBP/USD")
3. On the pair page, find **"1 Minute Bar Quotes"** section
4. Format: select **"Generic ASCII"**
5. Download each year from **2005 through 2025** (21 zips total)
6. Move all downloaded zips to the destination folder above
7. Verify count: `ls ~/Downloads/histdata/<pair>/ | wc -l` should return ~21

### Pre-create folders

```bash
mkdir -p ~/Downloads/histdata/{gbpusd,usdchf,audusd,usdcad,nzdusd,eurgbp,eurjpy,gbpjpy}
```

### Verify EUR/USD and USD/JPY existing downloads

Before proceeding, verify your existing EUR/USD and USD/JPY downloads:

```bash
ls ~/Downloads/eurusd/  # or wherever they are
ls ~/Downloads/usdjpy/
```

Confirm:
- (a) Date coverage extends through approximately November/December 2025
- (b) Periodicity is 5m or 1m

If your existing data only covers through October 2025 or earlier, download the missing months to complete through end of 2025.

### When complete, reply to chat

```
Completed histdata:
- gbpusd: <N> zips
- usdchf: <N> zips
- audusd: <N> zips
- usdcad: <N> zips
- nzdusd: <N> zips
- eurgbp: <N> zips
- eurjpy: <N> zips
- gbpjpy: <N> zips
- eurusd existing through: <YYYY-MM>
- usdjpy existing through: <YYYY-MM>
- existing data location: <path>
```

---

## Task M2: Verify FRED API Key

### Context

FRED API key from Project 2 was: `[REDACTED_COMPROMISED_KEY]`

This key is used for the comprehensive FRED macro pull (~150 series). Need to verify it's still valid before agent starts acquisition.

### Procedure

1. Visit https://fred.stlouisfed.org/docs/api/api_key.html
2. Login if needed
3. Confirm the key `[REDACTED_COMPROMISED_KEY]` is still listed in your account

If still valid:
- Reply: `FRED key valid: yes`

i dont want: If revoked or you want to regenerate:
1. Generate new key on the FRED page
2. Reply: `FRED key valid: no, new key: <NEW_KEY_HERE>`

---

## Task M3: Etherscan API Key (Required, Free)

### Context

Etherscan provides ETH on-chain metrics (transactions, gas, contracts). Free tier: 5 calls/sec, sufficient for our historical pulls.

### Procedure

1. Visit https://etherscan.io/myapikey
2. If you don't have account: register (free, email verification only)
3. Click "Add" button to generate API key
4. Copy the generated key
5. Reply: `Etherscan key: <key>`

**Note:** The API key looks like a long alphanumeric string. Keep it private — do not paste in any public location.

---

## Task M4 (Optional): CoinMarketCap Free Key

### Context

CoinMarketCap provides crypto market cap rankings. Free tier: 333 calls/day. Used as backup verification for top 50 list (CoinGecko free is primary).

### Decision

This is **optional**. Skip if you want to minimize setup time — CoinGecko free covers our needs.

### Procedure (if doing)

1. Visit https://pro.coinmarketcap.com/account
2. Sign up free
3. Generate API key
4. Reply: `CoinMarketCap key: <key>`

OR reply: `skip CMC`

---

## Task M5 (Optional): Alpha Vantage Free Key

### Context

Alpha Vantage provides backup commodities + FX daily data if yfinance fails. Free tier: 5 calls/min (very limited, backup only).

### Decision

Optional. Skip if minimizing setup. yfinance is reliable for our use cases.

### Procedure (if doing)

1. Visit https://www.alphavantage.co/support/#api-key
2. Instant key generation (just enter email)
3. Reply: `AlphaVantage key: <key>`

OR reply: `skip AV`

---

## Task M6: Verify `.gitignore` for Credentials

### Context

The `.env` file storing API keys must NEVER be committed to git. Verify `.gitignore` is set up correctly.

### Procedure

```bash
cat ~/Documents/financial_data/.gitignore
```

If file does not exist OR does not include `.env` patterns, create/update:

```bash
cat > ~/Documents/financial_data/.gitignore << 'EOF'
# Credentials - NEVER commit
_metadata/.env
_metadata/credential_validation.json
*.env
.env

# Large data files (optional - depends if you want to commit data lake)
*.parquet
*.csv
EOF
```

Reply: `gitignore configured: yes`

---

## Task M7: Confirm Machine Availability

### Context

Stage 1.3 distributes acquisition tasks across 3 machines for parallelism:
- **Omega** (RTX 4070, local) — light tasks
- **Dragon** (RTX 4090, 192.0.2.14) — heavy crypto fetches
- **Gamma** (RTX 5070 Ti, 192.0.2.13) — macro + on-chain

If only Omega is available, agent runs everything serial on Omega (slower but works).

### Procedure

Confirm which machines are powered on and SSH-accessible right now:

```bash
ssh dragon "echo Dragon UP"
ssh gamma "echo Gamma UP"
```

Reply with one of:

- `All 3 machines up: Omega + Dragon + Gamma` (preferred, full parallelism)
- `Only Omega + <other>` (partial parallelism)
- `Only Omega` (serial execution, slower but functional)

If Dragon or Gamma not currently powered on but available to power on, please power on now if possible (parallelism saves significant time on Binance crypto comprehensive pull).

---

## What Agent Does Automatically (NO action from you)

While you complete the manual tasks above, agent runs in parallel:

### On Omega:
- Setup `_scripts/lib/` shared utilities (validation, provenance, documentation, acquisition log)
- yfinance equity indices (~25 indices daily, US/EU/Asia/EM)
- yfinance commodities + ETFs + EM FX + bonds
- CFTC COT reports (bulk historical 2000-2025)
- Trading calendars + holidays
- Economic calendar (FRED actuals + scheduled events)

### On Dragon:
- Binance crypto comprehensive (top 50 spot + top 10 perpetuals + funding rates) at 5m/15m/1h/4h

### On Gamma:
- FRED comprehensive (~150 macro series across 13 categories) — uses your existing key
- CoinMetrics Community on-chain (BTC + ETH + top 20)
- Blockchain.com BTC supplementary
- Mempool.space BTC
- SEC EDGAR filings metadata (S&P 500, no text bodies)
- FINRA short interest (biweekly)
- DeFiLlama TVL
- BLS/BEA/Treasury supplementary
- OECD selected indicators

### Blocked until your manual work complete:
- HistData processing (Task 1.3.E) — needs Task M1 zips
- Etherscan ETH on-chain (Task 1.3.I) — needs Task M3 key

---

## Order of Execution

You can do tasks in any order. Recommended order to minimize agent idle time:

1. **Task M2** (FRED verify) — 1 minute. Reply key status.
2. **Task M3** (Etherscan registration) — 5 minutes. Reply key.
3. **Task M6** (gitignore verify) — 1 minute. Reply confirmed.
4. **Task M7** (machines confirm) — 2 minutes. Reply machines up.
5. **Task M1** (HistData downloads) — 2-3 hours, do in background while M2-M5 happen.
6. **Tasks M4, M5** (optional keys) — skip or do whenever.

---

## When You're Done

Once Tasks M1, M2, M3, M6, M7 complete (M4 and M5 are optional), reply to chat:

```
Stage 1.3 manual tasks complete:
- M1 HistData: <pairs and counts>
- M2 FRED key: <valid status>
- M3 Etherscan key: <key>
- M4 CoinMarketCap: <key or skip>
- M5 Alpha Vantage: <key or skip>
- M6 gitignore: configured
- M7 machines: <which are up>
```

Agent then proceeds with full Stage 1.3 acquisition including:
- HistData FX processing (after M1 complete)
- Etherscan ETH on-chain (after M3 complete)
- All previously-launched tasks completing

After all tasks complete, agent produces `STAGE_1.3_INVENTORY.md` with subscription gap analysis enabling Stage 1.4 decisions.

---

## Common Issues and Solutions

### HistData download stuck or rate-limited

HistData throttles aggressive downloading. Wait 30-60 seconds between zips. Don't use download accelerators (they get banned).

### HistData download requires CAPTCHA

If CAPTCHA appears repeatedly, take a 5-minute break and try again. Use different browser/session if persistent.

### Existing EUR/USD or USD/JPY downloads in different format

If your existing downloads are MT4 format instead of Generic ASCII, agent's HistData processing script can handle both. Just specify which format in your reply.

### Etherscan registration requires phone verification

Some accounts trigger phone verification. If you don't want to provide phone, skip Etherscan registration (Task M3) — agent will skip ETH on-chain task and use Glassnode for ETH metrics later (if subscription approved at Stage 1.4).

### One of the 3 machines unavailable

No problem. Agent redistributes tasks. Worst case all-on-Omega adds maybe 2-3 hours but completes correctly.

---

## Questions or Issues?

Reply to chat with any blockers. Agent will adjust plan accordingly.

---

## Reference

- Stage 1.3 full procedure: `13_STAGE_1.3_FREE_DATA_ACQUISITION.md`
- Project 3 master plan: `00_PROJECT_3_MASTER_PLAN.md`
- Data catalog: `12_STAGE_1.2_DATA_CATALOG.md`
