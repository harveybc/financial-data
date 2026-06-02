# Stage 1.3 — Manual Tasks for User

**Project:** Project 3 — Comprehensive Data Acquisition for RL Trading Research
**Stage:** 1.3 (Free Data Acquisition)
**Date:** 2026-04-28
**Last updated:** 2026-05-01 (M1–M5 complete)
**Owner:** harveybc

---

## Overview

This document contains the manual tasks the user completes for Stage 1.3. The agent automates everything else per `01_AGENT_INFRASTRUCTURE.md` (architecture v2).

**Status: M1–M5 complete as of 2026-05-01.** M6 and M7 are agent-handled per the v2 infrastructure (Tier 2 probes machines and verifies `.gitignore` automatically).

**Credential update:** the existing private companion document is the accepted source of truth for Stage 1.3 free-tier API key values in this private repo. Runtime values are loaded from `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env`, generated from that private companion file.

The actual API key values are NOT stored in this document. They live in:
- `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` (chmod 600, in `.gitignore`) — runtime values
- `STAGE_1_3_API_KEYS_PRIVATE.md` (in `.gitignore`, NOT committed) — personal reference companion to this doc

This document references keys by environment variable name only, so it can be safely committed to the repo.

---

## Task Checklist

| # | Task | Status | Env var name |
|---|------|--------|--------------|
| M1 | Download HistData FX 8 additional pairs | ✅ DONE | n/a (zip files in `~/Downloads/histdata/<pair>/`) |
| M2 | FRED API key (already valid from Project 2) | ✅ DONE | `FRED_API_KEY` |
| M3 | Etherscan free API key | ✅ DONE | `ETHERSCAN_API_KEY` |
| M4 | CoinMarketCap free key (optional) | ✅ DONE | `COINMARKETCAP_API_KEY` |
| M5 | Alpha Vantage free key (optional) | ✅ DONE | `ALPHA_VANTAGE_API_KEY` |
| M6 | `.gitignore` for credentials | 🤖 AGENT-HANDLED (Stage 1.1 bootstrap §8.7) |
| M7 | Confirm Dragon + Gamma machines available | 🤖 AGENT-PROBED (you just power them on) |

**You don't need to reply task-by-task anymore.** With M1–M5 complete, send the single completion message in the "When You're Done" section below and the agent takes over.

---

---

## Task M1: HistData FX Pairs ✅ DONE

**Status:** All 8 G10 pairs downloaded into `~/Downloads/histdata/<pair>/`:
- gbpusd, usdchf, audusd, usdcad, nzdusd, eurgbp, eurjpy, gbpjpy

Plus existing EUR/USD and USD/JPY downloads from Project 2.

**Original procedure (kept for reference, not for execution):**
1. Visit https://www.histdata.com/download-free-forex-data/
2. Click pair name → "1 Minute Bar Quotes" section → "Generic ASCII" format
3. Download yearly zips 2005–2025 per pair (21 zips per pair)
4. Move zips to `~/Downloads/histdata/<pair>/`

The Tier 1 supervisor on Omega will validate file counts, coverage, and integrity automatically when Stage 1.3 acquisition runs. Per `01_AGENT_INFRASTRUCTURE.md` §11, file counts and coverage checks are agent responsibilities.

**Information needed from user in completion message** (the agent cannot infer these):
- Path where existing EUR/USD downloads live (e.g., `~/Downloads/eurusd/` or `~/Downloads/histdata/eurusd/`)
- Path where existing USD/JPY downloads live
- Format of existing data (5m or 1m)
- Approximate end date of existing coverage (best guess; agent verifies exactly)

---

## Task M2: FRED API Key ✅ DONE

**Status:** Existing Project 2 FRED key verified valid.

**Env var:** `FRED_API_KEY`
**Location of value:** `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` and `STAGE_1_3_API_KEYS_PRIVATE.md` (NOT version controlled)

---

## Task M3: Etherscan API Key ✅ DONE

**Status:** Free Etherscan account registered, API key generated (5 calls/sec free tier).

**Env var:** `ETHERSCAN_API_KEY`
**Location of value:** `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` and `STAGE_1_3_API_KEYS_PRIVATE.md` (NOT version controlled)

**Provides:** ETH on-chain metrics (transactions, gas, contracts) for Stage 1.3 task 1.3.I (ETH on-chain via Etherscan supplementary).

---

## Task M4: CoinMarketCap Free Key ✅ DONE

**Status:** Free CoinMarketCap account registered, API key generated (333 calls/day free tier).

**Env var:** `COINMARKETCAP_API_KEY`
**Location of value:** `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` and `STAGE_1_3_API_KEYS_PRIVATE.md` (NOT version controlled)

**Provides:** Backup verification of top 50 crypto list (CoinGecko free is primary; CMC is secondary cross-check).

---

## Task M5: Alpha Vantage Free Key ✅ DONE

**Status:** Alpha Vantage free key generated (5 calls/min free tier — very limited, backup only).

**Env var:** `ALPHA_VANTAGE_API_KEY`
**Location of value:** `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` and `STAGE_1_3_API_KEYS_PRIVATE.md` (NOT version controlled)

**Provides:** Backup commodities + FX daily data if yfinance fails. Stage 1.3 prefers yfinance; Alpha Vantage is fallback only.

---

## Tasks M6 + M7: Agent-Handled

**M6 (.gitignore):** handled automatically by Stage 1.1 bootstrap (`11_STAGE_1_1_STORAGE_ARCHITECTURE.md` §8.7). Tier 2 re-verifies on every cron tick. No user action required.

**M7 (machine availability):** Tier 2 orchestrator probes Dragon and Gamma via SSH and reports availability. User actions are limited to: (a) ensure Dragon and Gamma are powered on, (b) keep `~/.ssh/config` current with their IPs (per `01_AGENT_INFRASTRUCTURE.md` §3).
### Reply

In your "Stage 1.3 manual tasks complete" message, just include one of:

- `Machines: all 3 powered on, IPs unchanged`
- `Machines: all 3 powered on, IPs changed — updated ~/.ssh/config`
- `Machines: only Omega available right now`
- `Machines: not sure — agent please probe`

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

**M1–M5 are complete.** The remaining setup is:

1. Populate `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` with the 4 key values from `STAGE_1_3_API_KEYS_PRIVATE.md` (the private companion doc generated alongside this one). Make sure the file is `chmod 600` and listed in `.gitignore`.
2. Confirm Dragon and Gamma are powered on (and SSH-reachable from Omega). If their IPs have changed, update `~/.ssh/config` per `01_AGENT_INFRASTRUCTURE.md` §3.
3. Send the "Stage 1.3 manual work complete" message below.

---

## When You're Done

Once `_metadata/.env` is populated and Dragon + Gamma are reachable, send this single confirmation message to start the agent run:

```
Stage 1.3 manual work complete (architecture v2):
- HistData: 8 new pairs in ~/Downloads/histdata/, plus existing EUR/USD and USD/JPY
  - Existing EUR/USD path: <fill in>
  - Existing USD/JPY path: <fill in>
  - Existing format: <5m or 1m>
  - Existing coverage end (best guess): <YYYY-MM>
- API keys: FRED, Etherscan, CoinMarketCap, Alpha Vantage all populated in _metadata/.env
- Machines: <"all 3 powered on, IPs unchanged" / "all 3 powered on, IPs changed — updated ~/.ssh/config" / "only Omega" / "not sure — agent please probe">
```

The user does NOT include actual key values in this message. The keys live only in `_metadata/.env` (chmod 600, gitignored) and in `STAGE_1_3_API_KEYS_PRIVATE.md` (also gitignored).

Per `01_AGENT_INFRASTRUCTURE.md` §9 (auto-validation: full auto), once you send this message:

- Tier 2 (OpenCode Go on Omega) dispatches the validation and acquisition tasks.
- Tier 1 supervisors on Dragon and Gamma watch the validation logs.
- File counts, coverage checks, schema validation, and integrity tests run automatically.
- Findings land in `STAGE_1.3_DELIVERABLE.md` and `STAGE_1.3_INVENTORY.md`.
- Only blockers ping you. Advisory issues are documented and the pipeline continues.

Agent then proceeds with full Stage 1.3 acquisition including:
- HistData FX processing (using zips already in `~/Downloads/histdata/`)
- Etherscan ETH on-chain pull (using `ETHERSCAN_API_KEY` from `.env`)
- FRED comprehensive macro pull (using `FRED_API_KEY`)
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

- Agent infrastructure (read this first): `01_AGENT_INFRASTRUCTURE.md`
- Stage 1.3 full procedure: `13_STAGE_1_3_FREE_DATA_ACQUISITION.md`
- Project 3 master plan: `00_PROJECT_3_MASTER_PLAN.md`
- Data catalog: `12_STAGE_1_2_DATA_CATALOG.md`
