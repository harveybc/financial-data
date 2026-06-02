# Project 3 Stage 3X Portfolio Environment Agent Specs

Date: 2026-05-19

## Purpose

Add a safe, testable path toward multi-asset portfolio experiments without
blocking the active single-asset micro-NSGA run.

2026-05-22 update: portfolio support is now aligned with the weekly-retrained
production target in
`work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`.

This is not a Stage C task and not a profitability claim. It is infrastructure
for weekly allocation/no-trade supervision above per-asset SAC models, and for
later optimization over target assets, cross-asset inputs, portfolio weights,
preprocessing, and SAC hyperparameters.

Hard rules for all agents:

- Stage C remains locked: no 2025-01-01+ rows.
- Do not launch training unless explicitly asked after config acceptance.
- Do not modify PPO/SAC/DQN algorithm source.
- Do not hide warnings. Emit them as warnings or optimizer penalties.
- Use tiny fixtures and tiny windows first.
- Treat negative one-week returns as optimizer values, not mechanical blockers,
  unless evidence/accounting/broker-safety checks fail.

## Copilot Spec: agent-multi / gym-fx Portfolio Plumbing

Repository:

- `/home/harveybc/Documents/GitHub/agent-multi`
- `/home/harveybc/Documents/GitHub/gym-fx`

Mission:

Implement a config-gated, test-only multi-asset portfolio environment path for
up to 5 assets. The first deliverable is mechanical: observation/action shape,
weekly allocation/no-trade inputs, per-asset accounting, force-close fields,
and evidence fields. Do not train.

Read first:

1. `agent-multi/pipeline_plugins/rl_pipeline_with_validation.py`
2. `agent-multi/pipeline_plugins/_return_trace.py`
3. `agent-multi/tools/project3_stage3x_sac_smoke_plan.py`
4. `gym-fx/app/env.py`
5. Existing return-trace and Stage 3X smoke-plan tests.

Implement:

1. A config-gated portfolio mode, for example:
   - `portfolio_mode: true`
   - `portfolio_assets: [...]`
   - `portfolio_allocation_policy: equal_weight | inverse_vol | trend_inverse_vol | downside_inverse_vol`
   - `portfolio_max_assets: 5`
   - `weekly_portfolio_supervisor: true`
   - `portfolio_no_trade_flags: {...}`
   - `portfolio_target_weights: {...}`
2. Observation fields:
   - per-asset OHLCV/feature tensor or dict fields;
   - per-asset current position/exposure;
   - per-asset bars/hours to force-close;
   - portfolio cash/equity/exposure summary.
   - weekly portfolio supervisor state: target weight, no-trade flag, and risk
     budget per asset.
3. Action semantics:
   - first mechanical version may use deterministic allocation policy outputs;
   - do not require SAC action-space redesign yet if that would be large;
   - document how SAC action support would be added later.
4. Evidence:
   - `portfolio_mode`
   - `portfolio_assets`
   - `portfolio_allocation_policy`
   - per-asset trade counts, exposure, return, cost;
   - portfolio-level trade count, return, drawdown, cost.
5. Tests:
   - one 2-asset fixture;
   - one 5-asset fixture;
   - Stage C denial;
   - force-close fields present;
   - per-asset accounting sums to portfolio accounting within tolerance.

Output:

- changed files;
- tests run;
- exact config snippet;
- explicit confirmation: no training, no Stage C, no PPO/SAC/DQN source edit.

## Claude Spec: financial-data Portfolio Contract and Guard Review

Repository:

- `/home/harveybc/Documents/GitHub/financial-data`

Python:

- `/home/harveybc/anaconda3/envs/tensorflow/bin/python`

Mission:

Prepare financial-data to accept and audit portfolio-mode evidence without
weakening the current single-asset Stage 3X micro-NSGA path.

Read first:

1. `work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
2. `work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
3. `experiments/stage3x_micro_nsga_g15_results/stage3x_sac_smoke_result_synthesis.json`
4. `experiments/stage3x_micro_nsga_plan/stage3x_micro_nsga_plan.json`
5. `experiments/stage3x_sac_smoke_results/stage3x_sac_smoke_result_synthesis.json`
6. `_scripts/workers/stage3x_sac_smoke_result_synthesis_worker.py`
7. `_scripts/workers/stage3x_absurdity_guard_worker.py`

Implement:

1. A portfolio evidence contract draft under
   `experiments/stage3x_portfolio_contract/`.
2. A CPU-only portfolio sanity worker that can read synthetic portfolio
   evidence fixtures and verify:
   - no Stage C rows;
   - per-asset and portfolio trade counts exist;
   - per-asset returns aggregate to portfolio return;
   - force-close exposure is measured per asset;
   - trade-frequency policy is checked per asset and at portfolio level.
3. A weekly walk-forward contract worker that emits production-like anchors:
   - training window;
   - validation week;
   - next-week test window;
   - Stage C denial;
   - target asset and cross-asset input masks.
4. A warning policy:
   - negative returns are optimizer objectives, not mechanical blockers;
   - missing evidence, bad hashes, Stage C rows, impossible accounting, or all
     no-trade remain blockers.
4. Tests using tiny fixtures only.

Output:

- changed files;
- tests run;
- generated portfolio contract summary;
- explicit confirmation: no training, no Stage C.

## ChatGPT 5.5 Pro Web Spec: Portfolio Research Review

Use only if we need external research before implementation. Attach:

- this file;
- `PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`;
- `PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md`;
- latest `stage3x_sac_smoke_result_synthesis.md`.

Task:

Review practical portfolio allocation choices for a small RL trading system
with up to 5 assets:

- equal weight;
- inverse volatility;
- trend-weighted inverse volatility;
- downside-risk / PMPT-style allocation;
- risk-parity variants;
- whether allocation weights should be optimized by NSGA or estimated
  deterministically before RL.

Output:

- Markdown memo with primary or well-cited references;
- implementation recommendation for a first mechanical portfolio smoke;
- what to defer until after single-asset micro-NSGA results.
