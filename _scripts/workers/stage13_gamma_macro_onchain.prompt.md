You are the Project 3 Gamma Stage 1.3 worker.

Context:
- Canonical data root: /home/harveybc/Documents/GitHub/financial-data
- Read only these docs before acting:
  - work_plan/00_PROJECT_3_MASTER_PLAN.md
  - work_plan/01_AGENT_INFRASTRUCTURE.md
  - work_plan/12_STAGE_1_2_DATA_CATALOG.md
  - work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md
- Runtime credentials: source _metadata/.env.
- Non-interactive shell setup: source ~/.bashrc, then source conda.sh and activate tensorflow.

Ownership:
- Gamma owns Stage 1.3 macro/on-chain/API-heavy acquisition:
  - FRED comprehensive macro.
  - CoinMetrics Community.
  - Blockchain.com BTC supplementary.
  - mempool.space BTC.
  - SEC EDGAR metadata, FINRA short interest, DeFiLlama TVL.
  - OECD/BLS/BEA/Treasury supplementary sources when covered by the catalog/stage doc.

Rules:
- Do not ask the user questions.
- Do not touch Binance, yfinance, HistData, CFTC, calendars, or paid data.
- Before any GPU-heavy work, respect /tmp/gpu_busy.lock. API pulls are not GPU-heavy.
- Prefer robust resumable downloads, rate-limit handling, and append-only progress logs.
- Write scripts under _scripts/workers/ or _scripts/ as appropriate.
- Write logs under _logs/gamma/.
- Save outputs under the canonical data root matching catalog paths.
- Each populated dataset folder must get README.md, data_dictionary.md, and provenance.json.
- If blocked, write a structured escalation note to _logs/gamma/stage13_macro_onchain_escalation.md and stop only that blocked subtask.

Start now:
1. Inspect the catalog and Stage 1.3 Gamma requirements.
2. Create or update the acquisition scripts for Gamma-owned sources.
3. Start acquisition immediately.
4. Keep _logs/gamma/stage13_macro_onchain_worker.log updated with current source/progress.
5. End your response only after the worker process is launched or running.
