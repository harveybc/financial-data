# Project 3 SAC-First NSGA Input Optimization Protocol

Date: 2026-05-14

## Decision

The next research branch is **SAC-first actor-critic input optimization**, not
another broad PPO/SAC/DQN grid and not Stage C.

2026-05-22 amendment: this branch is now explicitly a
**weekly-retrained portfolio optimization branch**. The model lifetime being
optimized is the next trading week after a weekend retrain, not a year-long
static deployment. See:

`work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`

2026-05-23 amendment: market-state representation is now a first-class search
object. The optimizer must compare `1h` and `4h` state profiles using
engineered summaries, PCA, autoencoder, TS2Vec/Patch-style embeddings, regime
probabilities, and hybrid profiles, but only after CPU split-safety and
negative-control diagnostics. See:

`work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md`

Rationale:

- SAC is the best fit for the current continuous-action trading interface: it
  is an off-policy actor-critic method with entropy regularization and stronger
  sample-efficiency properties than broad on-policy search.
- PPO remains useful as a later robustness comparator. DQN remains a discrete
  baseline only. Neither should drive the expensive input search right now.
- The binding failure in the latest Stage B artifacts is not "the model needs
  one more rerun"; it is that feature, preprocessing, observation-state, and
  reward/context choices have not been selected by a disciplined protocol.
- Stage C remains locked until a candidate passes Stage B hard gates.

## Literature Anchor

- SAC: Haarnoja et al. 2018, *Soft Actor-Critic*. Off-policy maximum-entropy
  actor-critic for continuous control.
- PPO: Schulman et al. 2017, *Proximal Policy Optimization*. Strong practical
  actor-critic method, but on-policy and less suitable for wide input search.
- NSGA-II: Deb et al. 2002. Standard multi-objective genetic algorithm for
  Pareto search under competing objectives.
- Reliable RL evaluation: Agarwal et al. / `rliable` metrics: IQM, bootstrap
  CIs, probability of improvement, performance profiles.
- Time-series representation learning: TS2Vec/CPC-style contrastive encoders
  are candidates for train-only representation pretraining, not Stage C tuning.

## Search Philosophy

No guessing. The search happens in layers:

1. **CPU filter layer**: remove feature/preprocessing choices that cannot show
   stable train-to-validation relation with future returns or trade context.
2. **Weekly walk-forward layer**: evaluate tiny "train / validate / next-week"
   anchors because the intended production system retrains every weekend.
3. **SAC smoke layer**: tiny counted GPU runs only for CPU-passing candidates.
4. **NSGA-II layer**: multi-objective search over feature subsets,
   preprocessing, asset/timeframe, cross-asset inputs, portfolio/risk controls,
   and SAC hyperparameters.
5. **Stage B validation layer**: full paired-seed, cost-scenario, baseline,
   DSR/PBO/Reality Check/SPA gate.
6. **Stage C**: still one-shot, only after Stage B promotion.

## Genome

Each NSGA individual is a complete, countable experiment specification:

- `target_asset`: the asset being traded.
- `input_asset_mask`: other assets whose prices/returns/volatility/liquidity
  may be used as inputs for the target asset model.
- `input_source_mask`: free/paid data source families included as inputs.
- `asset`: legacy alias for `target_asset` in existing artifacts.
- `asset_selection_policy`: fixed shortlist, liquidity/cost screen,
  diversification screen, or optimizer-selected portfolio subset.
- `timeframe`: start with 4h; add 1h/15m only after cost/trade-rate sanity.
- `feature_family_mask`: technical, statistical, volatility, trend, momentum,
  volume/liquidity, calendar/force-close, regime/OOD, representation embeddings.
- `feature_subset_mask`: sparse binary mask over candidate features after
  redundancy/stability filtering.
- `preprocessing_profile`: scaling mode, scaling window, clip value,
  observation window size, price-window inclusion, agent-state inclusion.
- `seasonal_context`: day-of-week, hour-of-week, bars/hours to Friday close,
  force-close zone, Monday entry window.
- `market_state_profile_id`: engineered, PCA, autoencoder, contrastive/patch,
  regime, or hybrid state profile.
- `market_state_profile_hash`: deterministic hash of state columns, encoder
  config, fit metadata, and output contract.
- `market_state_lookback_weeks`: state lookback length; outcome remains the
  next trading week.
- `market_state_timeframe`: `1h` or `4h`, selected separately from target
  asset and input assets.
- `weekly_anchor_id`: the rolling weekend retrain anchor being simulated.
- `event_calendar_profile`: upcoming-week event risk score and feature policy.
- `portfolio_allocation_policy`: equal weight, inverse volatility,
  trend-weighted inverse volatility, downside-risk/CVaR, HRP/risk parity, or
  later NSGA-parameterized policy.
- `portfolio_no_trade_thresholds`: per-asset no-trade/risk-off thresholds from
  the weekly supervisor.
- `reward_context`: force-close exposure penalty coefficient; churn penalty
  coefficient if introduced later.
- `SAC_hyperparameters`: learning rate, batch size, train frequency, gradient
  steps, buffer size, tau, gamma, ent_coef mode/value, net architecture.
- `cost_scenario`: base, plus_50pct, plus_100pct.

PPO/DQN hyperparameter genes are excluded from the first NSGA branch. They can
be used later as algorithm robustness checks on the best input contract.

## Objectives

Use multi-objective ranking, not a single fragile score:

1. maximize repeated next-week net return after costs;
2. maximize next-week Sharpe / downside-adjusted return;
3. maximize probability of improvement vs matched baseline;
4. minimize turnover and excessive trade-rate violations;
5. minimize Friday-late exposure and always-in-market losing behavior;
6. minimize feature count and redundancy;
7. maximize seed robustness via IQM/median and bootstrap CI;
8. maximize portfolio diversification by strategy-stream correlation;
9. penalize any DSR/PBO/family-test warning when a candidate graduates to
   full Stage B validation.

Hard constraints:

- no Stage C rows;
- no missing `feature_list_hash` / `observation_state_hash`;
- no no-trade collapse;
- no excessive-trade hard flag;
- no always-in-market losing flag;
- every trial counted in the ledger and multiple-testing accounting.

## Immediate Implementation Order

1. Generate the parametric data/preprocessing search surface:
   `_scripts/workers/stage3x_parametric_data_space_worker.py` emits an
   actual DEAP/NSGA-ready schema and CPU-screening seed population under
   `experiments/stage3x_parametric_data_space/`.
2. Generate and run CPU-first matrix:
   `_scripts/workers/stage3x_input_preprocessing_optimization_plan_worker.py`
   already emits 56 planned cells under
   `experiments/stage3x_input_preprocessing_optimization/`.
3. Enforce the absurdity guard:
   `_scripts/workers/stage3x_absurdity_guard_worker.py` blocks broad GPU
   launch when there is no Stage B promotion, missing feature/observation
   hashes, feature-insensitive signatures, active runs, or missing search-space
   artifacts.
4. Implement a train/validation-only target-relation screen:
   - rank IC / Spearman IC by feature and regime;
   - mutual-information proxy;
   - redundancy/stability overlay;
   - simple cost-aware threshold strategy sanity check.
5. Implement an NSGA plan generator, but keep it dry-run until the CPU filter
   has produced a reduced feature universe.
6. Run one SAC smoke matrix, not a full Stage B matrix:
   - diverse 5-contract input/preprocessing shortlist from the research review;
   - 3 seeds;
   - base cost only;
   - Stage C denied;
   - counted in ledger.
7. Promote to full Stage B only if smoke passes behavior sanity and shows
   non-degenerate action sensitivity.

## Current Implementation Status

Updated: 2026-05-15 05:05 UTC

- Parametric data-space worker completed:
  - input datasets discovered: `369`
  - CPU-screening seed genomes: `54`
- Input/preprocessing matrix completed:
  - CPU-first diagnostic cells: `56`
- Target-relation screen completed:
  - genomes screened: `54`
  - CPU-screen pass: `13`
  - selected feature contracts: `12`
- Absurdity guard status:
  - broad GPU launch allowed: `false`
  - small SAC smoke allowed: `true`
  - reason broad launch remains blocked: `NO_STAGE_B_PROMOTION`
- SAC smoke request/acceptance bridge completed:
  - request packet:
    `experiments/stage3x_sac_smoke_request/stage3x_sac_smoke_request.json`
  - smoke shortlist:
    `experiments/stage3x_sac_smoke_request/selected_feature_contracts_smoke_shortlist.json`
  - accepted agent-multi manifest:
    `/home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_sac_smoke_plan/stage3x_sac_smoke_plan_manifest.json`
  - configs accepted: `15` (`5` contracts x `3` seeds x base cost)
  - acceptance status: `ACCEPTED_LOCKED_SMOKE_PLAN`
  - Stage C access: `DENIED`
  - training launched by the bridge: `false`
  - accepted contracts:
    - `btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00__selected`
    - `btcusdt__1h__learned_cnn__rank_ic_topk__p00__selected`
    - `btcusdt__4h__learned_cnn__rank_ic_topk__p00__selected`
    - `btcusdt__1h__learned_lstm__regime_conditioned_topk__p00__selected`
    - `audusd__4h__fx_full__corr_stability_topk__p00__selected`

Current selected contracts are written to:

`experiments/stage3x_target_relation_screen/selected_feature_contracts.json`

The strongest current screen survivors are BTCUSDT/BTCUSDT-perp learned and
crypto contracts. This is not a Stage B promotion and not a tradability claim.
It is only permission to run a small counted SAC smoke plan whose locked config
manifest has now passed financial-data acceptance.

## 2026-05-19 Micro-NSGA Unblock Amendment

The project will not wait for full validation-scale runs before starting the
optimizer. The correct next step is a **small-window mechanical and optimizer
smoke**, not another manual trial and not Stage C.

Current micro-NSGA rule:

- use the same readiness nomenclature as the work plan:
  `eligible_for_stage3x_micro_nsga` and
  `prepare_stage3x_micro_nsga_plan`;
- keep every warning visible in JSON/Markdown;
- treat economic warnings as optimizer penalties/objectives during micro-NSGA,
  not as blockers to starting the optimizer;
- keep true data-safety and mechanical failures as blockers.

Mechanical blockers that still stop micro-NSGA:

- Stage C access not equal to `DENIED`;
- any 2025-01-01+ row in a training/validation/test artifact;
- missing or bad evidence;
- missing feature list, feature hash, observation fields, or observation hash;
- broker/venue profile missing for a contract that requires a broker-specific
  policy;
- all completed seeds show no trades;
- excessive-trade hard max exceeded;
- always-in-market losing behavior;
- OANDA FX Friday-force-flat or daily-break violation;
- locked config cannot preserve split, feature, preprocessing, or SAC
  hyperparameter fields.

Warnings that remain visible but do not block the micro optimizer:

- negative validation/test return;
- cost fragility;
- failed or aborted sibling seeds when at least one seed provides usable
  evidence;
- low Sharpe or weak proxy score;
- trade rate inside the hard max but outside the preferred band.

The reason is practical: without simultaneous feature, preprocessing, asset,
and SAC hyperparameter optimization, a weak early return is not evidence that
the model family is useless. It is only an objective value for the optimizer.

The active micro-NSGA experiment is intentionally tiny:

- training window: `14` days;
- validation window: `7` days;
- test window: `7` days;
- minimum split rows: `30`;
- SAC timesteps per cell: `5000`;
- seeds: `0, 1, 2`;
- cost scenario: `base`;
- Stage C: `DENIED`;
- broad GPU launch: still denied.

Artifacts:

- financial-data micro plan:
  `experiments/stage3x_micro_nsga_plan/stage3x_micro_nsga_plan.json`
- agent-multi locked config manifest:
  `/home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_micro_nsga_plan/stage3x_sac_smoke_plan_manifest.json`
- dispatch state:
  `/home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_micro_nsga_plan/stage3x_sac_smoke_dispatch_state.json`
- dispatch status:
  `/home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_micro_nsga_plan/stage3x_sac_smoke_dispatch_status.md`

The immediate goal is not profit proof. The goal is to prove that the complete
optimization loop can generate data, preserve features/preprocessing, train
briefly, emit evidence, measure trades per week, and feed results back into the
next generation without hiding any warning.

## Portfolio Workstream

Portfolio support is now part of the main Stage 3X direction, but it must not
stop the active single-asset micro-NSGA run. The weekly portfolio supervisor is
the production layer above per-asset SAC models.

Initial scope:

- up to `5` assets in one environment;
- target first implementation as a mechanical smoke, not a profitability
  claim;
- start with deterministic allocation policies inspired by MPT/PMPT:
  equal weight, inverse volatility, trend-weighted inverse volatility,
  downside-risk-weighted allocation;
- later expose allocation weights or allocation-policy parameters to NSGA;
- record per-asset position, exposure, return, turnover, and cost;
- enforce the same Friday force-close and broker trade-frequency policy per
  asset;
- emit weekly allocation decisions, no-trade flags, and risk budgets;
- compare portfolio weights using weekly strategy-stream returns, not only raw
  asset price returns;
- keep Stage C denied.

Portfolio work must not modify PPO/SAC/DQN algorithms directly. It should be
implemented as environment/action-space support and config-gated plugins, with
small synthetic fixtures and tiny real-data windows before any GPU launch.

## Auto-Critique

1. **The first version of the CPU screen almost repeated the same mistake.**
   It ranked high rank-IC contracts even when the cheap cost-aware proxy return
   was negative. That would have wasted GPU. The screen now blocks those with
   `NEGATIVE_COST_AWARE_PROXY_RETURN`.
2. **High feature relation is not enough.** A feature contract must show at
   least weak forward-return relation, nonzero threshold trades, and positive
   cost-aware proxy return before it can enter a SAC smoke plan.
3. **The proxy is not a trading strategy.** It is only an absurdity filter. SAC
   still needs smoke validation, then full Stage B validation.
4. **The selected contracts may still fail RL.** The next smoke run must be
   small, counted, and evidence-rich, not a broad matrix.
5. **The agent-multi SAC smoke-plan blocker is cleared at the dry-run/config
   level.** The remaining risk is execution evidence: the first smoke run must
   prove the selected features reach the observation state, the policy does not
   collapse to no-trade or churn, and no Stage C row appears in any trace.

## Agent Orchestration

Use `work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md` as the active
external-agent handoff kit.

- Codex owns integration, guardrails, work-plan updates, and final acceptance.
- Claude owns financial-data CPU/statistical screening workers.
- Copilot owns agent-multi/gym-fx locked SAC smoke-run infrastructure.
- ChatGPT 5.5 Pro Web owns external research review and safe search-range
  critique, with explicit attachment lists.

No agent should receive a vague prompt that references "the plan" without
repo path, files to read, allowed edits, commands, outputs, and hard rules.

## Explicit Non-Actions

- Do not unlock Stage C.
- Do not pay for CryptoQuant without pre-payment proof of unique historical
  coverage and a concrete feature that passes train/validation screening.
- Do not run a full 900+ config Stage B rerun from intuition.
- Do not tune SAC hyperparameters on Stage C.
- Do not change PPO/SAC/DQN algorithm implementations.

## Acceptance Criteria For This Branch

- A reduced, auditable input universe exists before GPU search.
- The chosen preprocessing profiles are justified by train/validation evidence.
- Force-close/seasonal context is visible in observation evidence and changes
  behavior in the intended direction.
- NSGA search emits reproducible genomes and trial IDs.
- Every GPU trial has progress, trades, profit, feature hash, observation hash,
  and Stage C denial recorded.
