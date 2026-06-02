# Project 3 Stage 3X Agent Spec Kit

Date: 2026-05-14

Purpose: provide complete, copy-paste-ready specs for Codex, Claude, Copilot,
and ChatGPT 5.5 Pro Web during the SAC-first, data/preprocessing-first Stage 3X
branch.

This file is now the active external-agent handoff kit. Older one-off prompt
files are archived under `work_plan/archive_superseded_2026_05_14/` and
`work_plan/archive_superseded_2026_05_23_weekly_data_first/`.

2026-05-22 update: Stage 3X is now explicitly a weekly-retrained portfolio
branch. Every agent must read
`work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md` before
new Stage 3X work.

## Current Active Operating Files

- Active weekly-retrained portfolio protocol:
  `work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
- Active SAC/NSGA input optimization protocol:
  `work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
- Active market-state representation protocol:
  `work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md`
- Active market-state representation agent specs:
  `work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_AGENT_SPECS_2026_05_23.md`
- Active portfolio environment/evidence spec:
  `work_plan/PROJECT3_STAGE3X_PORTFOLIO_ENV_AGENT_SPECS_2026_05_19.md`

The old Claude/Copilot/ChatGPT prompt files from 2026-05-14 were executed and
archived. For new agent work, create a fresh short prompt from the active
protocols instead of reusing those stale prompts.

## Shared Project State

Project 3 now evaluates a weekly-retrained production loop across data,
feature, asset, seed, weekly anchor, cost, and broker-policy variants. The
current active branch is **SAC-first actor-critic input optimization**:

1. screen data/feature/preprocessing contracts on train/validation only;
2. use tiny smoke windows to prove data reaches the model and evidence is
   valid;
3. use DEAP/NSGA-II for data, preprocessing, SAC hparams, and weekly-anchor
   optimization;
4. keep PPO/DQN as robustness comparators after SAC/data search is auditable;
5. keep Stage C locked until a future promotion packet passes.

Latest known facts to verify, not assume:

- Stage C access is `DENIED`.
- Stage B statistical evaluator has no promotion-ready candidate.
- Current Stage 3X guard says broad GPU launch is blocked by
  `NO_STAGE_B_PROMOTION`.
- Parametric data-space worker discovered `369` train-only input datasets and
  emitted `54` CPU-screening seed genomes.
- Input/preprocessing worker emitted `56` CPU-first diagnostic cells.
- Target-relation screen has now screened `54` genomes, passed `13`, and
  emitted `12` selected feature contracts.
- The guard now allows only a small SAC smoke plan, not a broad GPU launch.

Canonical artifacts:

- `work_plan/00_PROJECT_3_MASTER_PLAN.md`
- `work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
- `work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
- `experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space_summary.md`
- `experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space.schema.json`
- `experiments/stage3x_parametric_data_space/project3_data_preprocessing_seed_population.csv`
- `experiments/stage3x_input_preprocessing_optimization/stage3x_input_preprocessing_optimization_plan.md`
- `experiments/stage3x_input_preprocessing_optimization/stage3x_input_preprocessing_matrix.csv`
- `experiments/stage3x_absurdity_guard/stage3x_absurdity_guard_report.md`
- `experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.md`
- `experiments/stage3x_target_relation_screen/selected_feature_contracts.json`
- `experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json`
- `experiments/stage_b_validation/hardening/stage_b_feature_action_audit.json`
- `experiments/stage_b_validation/hardening/stage_b_decision_readiness.json`

Global hard rules:

- Do not inspect, train, tune, or evaluate Stage C rows
  (`DATE_TIME >= 2025-01-01`) unless a future Stage C authorization exists.
- Do not launch broad GPU work while the absurdity guard blocks it.
- Do not modify PPO/SAC/DQN algorithm implementations.
- Do not weaken Stage B hard gates to manufacture a pass.
- Every future GPU trial must be a counted trial with feature hash,
  observation hash, progress, trades, profit, and Stage C denial evidence.

## 2026-05-22 Weekly Portfolio Supervisor Update

Stage 3X no longer assumes one static model must trade a long OOS period
without retraining. The intended product retrains every weekend and trades the
following week. New work must therefore support:

- rolling weekly train/validation/next-week anchors;
- cross-asset input masks separate from the target trading asset;
- paid/free data source masks with coverage/utility checks;
- a weekly portfolio supervisor that emits weights, no-trade flags, risk
  budgets, and trade-rate budgets;
- portfolio evidence with per-asset and portfolio-level returns, costs,
  drawdown, turnover, and force-close compliance.

Negative one-week smoke returns are optimizer objectives, not blockers, unless
they coincide with mechanical failures such as missing evidence, Stage C rows,
all-no-trade, hard overtrading, broker-policy violations, or impossible
portfolio accounting.

## Codex Role

Codex is the integration owner.

Own:

- active work-plan consistency;
- guardrail logic;
- financial-data integration and tests;
- final acceptance review after Claude/Copilot results;
- updating this spec kit when the implementation advances.

Codex should directly implement small cross-cutting workers and tests when that
unblocks the external agents.

## Claude Spec A: Financial-Data Target-Relation Screen

Status: implemented by Codex on 2026-05-14. Use this spec for review or
hardening, not duplicate implementation, unless defects are found.

```text
You are Claude acting as a senior quantitative engineer inside the
financial-data repo. You have repository access. Do not guess paths.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- Use /home/harveybc/anaconda3/envs/tensorflow/bin/python
- Do not assume "python" is on PATH.

Read these files first, in this order:
1. work_plan/00_PROJECT_3_MASTER_PLAN.md
2. work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md
3. work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md
4. experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space.schema.json
5. experiments/stage3x_parametric_data_space/project3_data_preprocessing_seed_population.csv
6. experiments/stage3x_input_preprocessing_optimization/stage3x_input_preprocessing_matrix.csv
7. experiments/stage3x_absurdity_guard/stage3x_absurdity_guard_report.json
8. _scripts/workers/stage3x_parametric_data_space_worker.py
9. _scripts/workers/stage3x_input_preprocessing_optimization_plan_worker.py
10. _scripts/workers/stage3x_absurdity_guard_worker.py
11. _scripts/workers/stage3x_feature_redundancy_stability_worker.py

Mission:
Implement the train/validation-only target-relation screening layer for the
Stage 3X data/preprocessing branch. This is CPU-first and must not launch RL
training.

Implement:
1. New worker:
   _scripts/workers/stage3x_target_relation_screen_worker.py
2. Inputs:
   - project3_data_preprocessing_seed_population.csv
   - actual train.csv files referenced by the seed population
   - existing redundancy/stability artifacts when available
3. For each seed genome, compute train/validation-safe diagnostics:
   - timestamp and Stage C firewall checks;
   - feature missingness / constant / near-constant counts;
   - redundancy summary;
   - Spearman rank IC to next-bar and multi-bar forward returns;
   - mutual-information proxy or safe fallback when sklearn is unavailable;
   - regime-conditioned IC by volatility/trend/calendar bins when columns exist;
   - simple cost-aware threshold sanity check, with no RL training;
   - recommended feature subset for each selection method.
4. Outputs:
   - experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.json
   - experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.csv
   - experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.md
   - experiments/stage3x_target_relation_screen/selected_feature_contracts.json
5. Add tests with small synthetic CSV fixtures:
   - Stage C rows are rejected;
   - constant features are rejected or penalized;
   - a feature with known forward-return relation ranks above noise;
   - output never sets stage_c_access other than DENIED;
   - no training is launched.

Hard rules:
- Do not use rows at/after 2025-01-01.
- Do not launch training.
- Do not edit agent-multi or gym-fx.
- Do not weaken Stage B gates.

Commands:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stage3x_target_relation_screen_worker.py -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_target_relation_screen_worker.py
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_absurdity_guard_worker.py

Final report:
- files changed;
- tests run;
- number of genomes screened;
- top surviving data/feature/preprocessing contracts;
- explicit blockers;
- confirmation no training launched and Stage C not touched.
```

## Copilot Spec B: Agent-Multi Parametric SAC Infrastructure

Status: ready to dispatch. The required
`experiments/stage3x_target_relation_screen/selected_feature_contracts.json`
artifact now exists.

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi and gym-fx repos. You have repository access. Do not guess paths.

Repositories:
- cd /home/harveybc/Documents/GitHub/agent-multi
- cd /home/harveybc/Documents/GitHub/gym-fx
- Read-only context from /home/harveybc/Documents/GitHub/financial-data

Python:
- Prefer /home/harveybc/anaconda3/envs/tensorflow/bin/python when available.

Read these files first:
1. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md
2. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md
3. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space.schema.json
4. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_input_preprocessing_optimization/stage3x_input_preprocessing_matrix.csv
5. agent-multi/docs/STAGE_B_EVIDENCE_CONTRACT.md
6. agent-multi/pipeline_plugins/_return_trace.py
7. agent-multi/tools/project3_stageb_run_plan.py
8. gym-fx/app/env.py

Mission:
Prepare agent-multi/gym-fx to consume selected Stage 3X data contracts and
emit locked SAC smoke-run configs after financial-data CPU screening approves
them. Do not launch training.

Implement or verify:
1. A dry-run tool, if missing:
   tools/project3_stage3x_sac_smoke_plan.py
2. Inputs:
   - selected_feature_contracts.json from financial-data target-relation screen
   - parametric search-space schema
3. The tool should emit locked SAC configs only:
   - top N selected data contracts;
   - 3 seeds by default;
   - base cost only for smoke;
   - Stage C access DENIED;
   - return_trace/evidence enabled;
   - feature_list_hash and observation_state_hash required;
   - progress file, trades, profit, and no-trade anomaly fields available.
4. Ensure config parameters can express:
   - feature_columns / feature_list;
   - scaling_mode;
   - feature_scaling_window;
   - feature_clip;
   - window_size;
   - stage_b_force_close_obs;
   - force-close reward penalty fields if selected.
5. Ensure no PPO/SAC/DQN algorithm implementation is modified.
6. Add tests:
   - generated config denies Stage C;
   - missing feature list fails closed;
   - selected preprocessing fields are preserved;
   - smoke plan does not launch training;
   - evidence path contract is present.

Hard rules:
- Do not launch training.
- Do not touch Stage C.
- Do not change PPO/SAC/DQN algorithm source.
- Do not weaken evidence guards.

Commands:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stage3x_sac_smoke_plan.py --help
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stage3x_sac_smoke_plan.py --dry-run --validate-only

Final report:
- files changed;
- tests run;
- example locked config;
- exact financial-data input contract expected;
- confirmation no training launched and Stage C not touched.
```

## ChatGPT 5.5 Pro Web Spec C: Research Review

Attach these files, in priority order. If attachment limits are tight, attach
only the first five:

1. `PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
2. `PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md`
3. `project3_data_preprocessing_search_space_summary.md`
4. `project3_data_preprocessing_search_space.schema.json`
5. `stage3x_absurdity_guard_report.md`
6. `stage3x_input_preprocessing_optimization_plan.md`
7. `stage_b_feature_action_audit.md`
8. `stageb_dsr_pbo_report.md`
9. `PROJECT3_CRYPTOQUANT_SUBSCRIPTION_DECISION_2026_05_13.md`

```text
You are an external senior quant/RL research reviewer. You do not have repo
access beyond the attached files.

Project 3 evaluates fixed PPO/SAC/DQN trading policies across assets,
timeframes, source families, feature families, seeds, costs, and splits. Stage C
is a one-shot heldout firewall using rows at/after 2025-01-01 and cannot be
used for tuning.

Current decision:
- No Stage B candidate is promotion-ready.
- Broad GPU work is blocked until train/validation-only data/preprocessing
  screens justify it.
- The active branch is SAC-first actor-critic input optimization.
- DEAP/NSGA-II should optimize SAC only after feature/data/preprocessing
  contracts survive CPU screening.
- CryptoQuant is cancelled unless a pre-payment proof shows unique, useful
  historical coverage.

Research task:
Produce an implementation-grade memo for the next Project 3 decisions:
1. Best-practice feature/source families for RL trading:
   technical, statistical, decomposition, calendar/session, on-chain/free
   crypto, perp/funding, FX/macro where available.
2. Feature selection methods:
   redundancy/stability, rank IC, mutual information, permutation/SHAP,
   regime-conditioned value, cost-aware threshold sanity checks.
3. Preprocessing search:
   rolling vs expanding normalization, clipping, observation windows,
   leakage-safe fitting, train/validation split policy.
4. SAC-first hyperparameter optimization:
   which SAC hyperparameters should be searched after CPU screening, and safe
   ranges for DEAP/NSGA-II.
5. Multi-objective objective design:
   return, Sharpe/downside, trade-rate sanity, Friday exposure, turnover,
   seed robustness, feature simplicity, DSR/PBO penalties.
6. What should be killed/deferred to avoid wasting GPU or paid data money.

Rules:
- Do not suggest unlocking Stage C.
- Do not suggest changing PPO/SAC/DQN algorithm implementations.
- Do not suggest broad GPU reruns before CPU feature/preprocessing screening.
- Clearly separate proven recommendations from speculative research.
- Prefer primary papers, official docs, or well-cited technical sources.

Output:
- Markdown memo;
- concrete checklist suitable for GitHub issues;
- links to references.
```

## Stage 3X Implementation Sequence

1. Codex keeps this spec kit and guardrails current.
2. Claude implements `stage3x_target_relation_screen_worker.py`.
3. Copilot implements/validates `project3_stage3x_sac_smoke_plan.py` in
   agent-multi after Claude produces selected contracts.
4. ChatGPT 5.5 Pro Web reviews the research assumptions and safe NSGA ranges.
5. Codex integrates outputs and updates the absurdity guard.
6. Only if the guard clears, run a small SAC smoke matrix.
7. Only if smoke passes behavior/evidence checks, generate a counted Stage B
   validation plan.
