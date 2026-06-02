# Project 3 Weekly-Retrained Portfolio Protocol

Date: 2026-05-22

## Decision

Project 3 is no longer framed as "find one RL model that trades well for a
full year after training." The practical target is:

> Every weekend, retrain/update the system using data available through the
> completed week, then trade only the next week under a weekly portfolio
> supervisor.

The active research object is therefore the complete weekly production loop:

1. choose tradable assets;
2. build per-asset input contracts using all useful own-asset and cross-asset
   data from free and paid sources;
3. optimize feature selection, preprocessing, SAC hyperparameters, and
   portfolio/risk controls;
4. allocate capital weekly across the selected assets/models;
5. trade the following week only;
6. record weekly evidence and feed it into the next weekend retrain.

This protocol supersedes any interpretation of Stage 3X that blocks progress
because an unoptimized short smoke model is not yet a Stage B/Stage C-ready
candidate. Stage C remains locked, but Stage 3X optimization is allowed to
continue while all data-safety and mechanical evidence checks pass.

## Why This Is The Right Target

The user-facing system is not a static academic benchmark. It is intended to be
a live portfolio trading engine. A model that is retrained every weekend should
be judged by its next-week behavior, not by pretending it must remain optimal
for a year without retraining.

The research question changes from:

- "Can this single model survive a long static OOS period?"

to:

- "Can this automated weekend retrain + weekly portfolio allocation process
  produce repeated next-week risk-adjusted edge after costs?"

Long validation still matters, but only as repeated weekly walk-forward
episodes. The correct sample is many historical "train on past / trade next
week" anchors, not one monolithic year-long deployment.

## Rolling Weekly Split Policy

For each historical anchor week `W`, the production-like split is:

- **Training:** approximately 4 years ending before the validation week.
- **Validation:** the week immediately before the simulated trading week, or a
  small rolling bundle of recent weeks when a single week is too noisy.
- **Test / next-week simulation:** exactly the following week.
- **Live deployment analogy:** after the real weekend retrain, the next live
  week is the only intended model lifetime.

Default research policy:

- micro smoke: 14d train / 7d validation / 7d test only to prove mechanics;
- micro-NSGA: many tiny weekly anchors, cheap enough to iterate;
- serious Stage 3X validation: repeated rolling weekly anchors across multiple
  regimes;
- Stage B promotion: still requires cost scenarios, seeds, baselines,
  statistical gates, and no Stage C rows;
- Stage C: still one-shot final heldout.

Do not use a single one-week result as proof of tradability. Use it as one
episode in an optimizer and later aggregate across many weekly anchors.

## Data And Input Policy

For every target trading asset, the input universe may include:

- own-asset OHLCV, returns, volatility, trend, momentum, liquidity, and
  technical/statistical features;
- prices/returns/volatility/liquidity of other tradable assets;
- cross-asset spreads, correlations, beta-like exposures, relative strength,
  lead/lag features, and regime features;
- FX/crypto/macro/event-calendar variables when available;
- paid-source features only when the provider gives enough historical coverage
  to enter train/validation screening;
- free-source equivalents when paid data does not prove unique value.

This is important: asset prices are not only tradable instruments. They are
also valid inputs for models trading other assets. The data-space worker must
therefore treat `input_asset_mask` and `target_asset` as separate genome genes.

Paid data is not used because it was paid for. It is used only when it passes
coverage, leakage, freshness, cost, and train/validation utility checks.

## Asset And Portfolio Selection

Do not hard-code "top 10 assets" as a permanent rule. Start with a safe
operational cap, then let evidence choose the number.

Initial caps:

- single-asset micro-NSGA remains active;
- portfolio mechanical smoke: up to 5 assets;
- later production research: configurable cap, probably 3-10 assets depending
  on liquidity, spread, correlation, and operational risk.

Asset eligibility metrics:

- data coverage and feature availability;
- spread/slippage/cost model quality;
- liquidity and market-hour compatibility;
- next-week walk-forward net return distribution;
- downside risk / CVaR / drawdown;
- correlation to other selected strategy streams;
- marginal contribution to portfolio risk-adjusted return;
- trade frequency inside broker policy bands;
- no persistent no-trade, overtrade, or always-in-market-losing behavior.

The selected portfolio should be the smallest set that improves risk-adjusted
weekly portfolio behavior, not the largest list of assets we can run.

## Weekly Portfolio Supervisor

The portfolio supervisor is above the per-asset SAC agents.

Inputs:

- per-asset model health from the previous week;
- latest feature/regime state;
- expected next-week event-calendar risk score;
- per-asset spread/slippage/cost estimates;
- recent weekly returns of each strategy stream;
- covariance/correlation of strategy streams, not only raw asset prices;
- broker constraints and Friday force-close policy.

Outputs:

- target asset/model weights for the next week;
- no-trade flags per asset/model;
- per-asset risk budgets;
- weekly trade-rate budgets;
- max weekly loss / drawdown guard;
- forced flattening schedule.

First allocation policies to compare:

- equal weight;
- inverse volatility;
- trend-weighted inverse volatility;
- downside-risk / CVaR-weighted allocation;
- HRP/risk-parity style allocation;
- later: NSGA-optimized weight-policy parameters.

Riskfolio-Lib and PyPortfolioOpt are useful reference engines for CPU research,
but the project should own its evidence contract and weekly simulator. External
libraries may help compute weights; they should not become opaque truth.

## Event Calendar Risk Overlay

The first event-calendar implementation is a risk overlay, not a magical alpha
source.

Minimum fields:

- events in the upcoming trading week;
- currency/asset relevance;
- importance score;
- time-to-event;
- expected volatility impact;
- optional actual-vs-forecast field later.

Initial behavior:

- high-risk event week can reduce size or enable no-trade for affected assets;
- during-week actual-vs-expected reactions are deferred until the weekly system
  works;
- event features must be lagged/known at decision time; no leaked outcome data.

## Market-State Causal Contract

The causal layer is framed around the weekly business mechanic, not around a
generic static prediction task.

Role mapping:

- **Patient:** one tradable target asset at one weekly anchor.
- **Patient state:** the market state observed before the weekly decision
  cutoff.
- **Medicine:** the input families, portfolio no-trade flags, exposure buckets,
  and supervisor settings available before the cutoff.
- **Outcome:** the next-week market-status vector for that asset/model stream.

Default timing:

- the decision cutoff is at least 12 hours before the new trading week starts;
- a 6-hour cutoff is the minimum allowed for future experiments;
- the default market-state lookback is 168 hours ending at the cutoff;
- snapshot encoding is allowed only as a cheaper ablation against the window
  summary;
- all weekend-border data must be strictly known before the cutoff.

The first implemented artifact is:

```text
experiments/stage3x_market_state_causal_contract/
```

It emits 12 weekly causal units from the current tiny weekly fixture, keeps
`stage_c_access=DENIED`, launches no training, and records zero temporal
issues. The contract supports later EconML / DML / causal-forest style audits,
but it explicitly forbids treating causal scores as proof of alpha or as an
automatic feature-deletion rule.

The active representation-search plan is:

```text
work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md
```

That plan defines the efficient test ladder for `1h` vs `4h`, engineered
summaries, PCA, autoencoders, TS2Vec/Patch-style embeddings, regime
probabilities, and hybrid profiles. The rule is CPU-first, GPU-second: learned
state encoders must beat engineered/PCA baselines in split-safe diagnostics
before they consume SAC smoke GPU time.

## Optimization Genome Additions

The Stage 3X genome now includes:

- `target_asset`;
- `input_asset_mask`;
- `input_source_mask`;
- `paid_source_mask`;
- `feature_family_mask`;
- `feature_subset_mask`;
- `preprocessing_profile`;
- `window_size`;
- `weekly_anchor_id`;
- `validation_week_policy`;
- `event_calendar_profile`;
- `portfolio_allocation_policy`;
- `portfolio_max_assets`;
- `portfolio_no_trade_thresholds`;
- `risk_budget_profile`;
- `market_state_causal_profile`;
- `pretrade_gap_hours`;
- `market_state_lookback_hours`;
- `market_state_encoding_mode`;
- `SAC_hyperparameters`;
- `cost_scenario`;
- `broker_profile`.

Optimization objectives:

- maximize repeated next-week net return after costs;
- maximize next-week IQM/median return across anchors/seeds;
- maximize probability of improvement vs matched baselines;
- minimize weekly drawdown/CVaR;
- minimize cost-to-gross-edge ratio;
- keep trades/week inside broker policy bands;
- minimize Friday-late exposure;
- minimize feature count/redundancy when performance is similar;
- maximize portfolio diversification by strategy-stream correlation.

## Mechanical Blockers Vs Optimizer Objectives

Mechanical blockers still stop a run:

- Stage C access not `DENIED`;
- 2025-01-01+ rows in any non-Stage-C artifact;
- missing/bad evidence;
- missing feature list/hash or observation fields/hash;
- impossible portfolio accounting;
- missing broker profile for broker-specific policy;
- all completed seeds show no trades;
- trade-frequency hard max exceeded;
- OANDA FX Friday-force-flat or daily-break violation;
- locked config cannot preserve split, feature, preprocessing, SAC, broker, or
  portfolio fields.

Optimizer objectives/warnings do not stop Stage 3X micro-optimization:

- negative one-week return;
- low Sharpe;
- cost fragility below hard limit;
- weak single-anchor result;
- sibling seed disagreement;
- trade rate outside preferred band but below hard max.

Reason: without simultaneous optimization of features, preprocessing, assets,
portfolio policy, and SAC hyperparameters, early weak returns are objective
values, not a reason to stop the search.

## Immediate Implementation Order

1. Finish and synthesize the current micro-NSGA generation.
2. Continue micro-NSGA while mechanical blockers are clear.
3. Add a weekly walk-forward contract worker in financial-data:
   - emits historical weekly anchors;
   - records train/validation/next-week windows;
   - prevents Stage C rows;
   - supports tiny smoke anchors and larger validation anchors.
4. Extend the parametric data-space worker:
   - separate `target_asset` from `input_asset_mask`;
   - include cross-asset features;
   - include paid/free source flags and coverage quality.
5. Add a CPU weekly portfolio supervisor worker:
   - consumes per-asset weekly return streams or synthetic fixtures first;
   - compares equal weight, inverse vol, downside-risk, trend-inverse-vol, and
     HRP/risk-parity style policies;
   - emits target weights, no-trade flags, and risk budgets.
6. Add a market-state causal contract worker:
   - maps patient/state/medicine/outcome at weekly anchors;
   - enforces 6h minimum / 12h default pretrade gap;
   - blocks any row at or after the Stage C boundary;
   - emits diagnostic-only causal estimator policy.
7. Add portfolio evidence contract:
   - per-asset returns/trades/cost/exposure;
   - portfolio return/drawdown/CVaR/cost;
   - weekly allocation decisions;
   - broker and Friday force-close compliance.
8. Only after the CPU supervisor contract passes, add agent-multi/gym-fx
   config-gated portfolio-mode mechanical support.
9. Then expose portfolio and market-state causal genes to DEAP/NSGA.

## Current Status

Updated: 2026-05-23 local / 2026-05-24 UTC.

- G15 dispatch completed: `36/36`.
- G15 evidence validated: `36`.
- G15 Stage C access: `DENIED`.
- G18 dispatch is active: `8 done`, `4 running`, `24 pending`, `0 failed` at
  the last status check.
- G18 Stage C access: `DENIED`.
- The positive median one-week test return is promising only as optimizer
  feedback, not a tradability proof.
- Weekly walk-forward, portfolio sanity, and market-state causal contracts now
  exist as CPU-first financial-data workers with passing tests.
- Market-state profile generation and CPU screening now exist:
  - total profiles: `144`;
  - implemented CPU profiles: `72`;
  - learned-encoder stubs: `72`;
  - selected nonredundant profiles: `12`;
  - selected packet:
    `experiments/stage3x_market_state_profile/selected_market_state_profiles.json`.
- The next protocol shift is to expose cross-asset inputs, market-state causal
  context, and weekly portfolio allocation into the optimizer instead of
  freezing on one single asset/model stream.

## Agent Work Packages

For market-state representation work, use the dedicated active handoff:

```text
work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_AGENT_SPECS_2026_05_23.md
```

### Claude / financial-data

Mission: implement/review CPU-only weekly walk-forward and portfolio-supervisor
contracts.

Read first:

1. `work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
2. `work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
3. `experiments/stage3x_micro_nsga_g15_results/stage3x_sac_smoke_result_synthesis.json`
4. `_scripts/workers/stage3x_micro_nsga_nextgen_worker.py`
5. `_scripts/workers/stage3x_sac_smoke_result_synthesis_worker.py`

Deliverables:

- weekly walk-forward contract worker;
- portfolio-supervisor CPU worker with tiny fixtures;
- tests for Stage C denial, no leakage, weekly split correctness, and
  portfolio accounting.

No training. No Stage C. No PPO/SAC/DQN edits.

### Copilot / agent-multi + gym-fx

Mission: prepare config-gated portfolio-mode plumbing only after the
financial-data CPU contract is defined.

Read first:

1. this protocol;
2. `work_plan/PROJECT3_STAGE3X_PORTFOLIO_ENV_AGENT_SPECS_2026_05_19.md`;
3. `agent-multi/pipeline_plugins/_return_trace.py`;
4. `agent-multi/tools/project3_stage3x_sac_smoke_plan.py`;
5. `gym-fx/app/env.py`.

Deliverables:

- config schema for portfolio mode;
- no-training mechanical tests with 2-asset and 5-asset fixtures;
- evidence fields for per-asset and portfolio accounting.

No broad GPU launch. No Stage C. No PPO/SAC/DQN source edits.

### ChatGPT 5.5 Pro Web

Use only for research review if needed. Best prompt:

> Review this weekly-retrained portfolio protocol for an RL trading system.
> Focus on practical profit/risk, weekly walk-forward validation, PMPT/MPT/HRP
> allocation, event-calendar risk overlays, and how to avoid leakage. Do not
> suggest Stage C tuning or broad academic gates. Output concrete engineering
> recommendations and failure modes.

Attach this protocol, the FINRA/OANDA memo, and the latest G15 synthesis.

## Explicit Non-Actions

- Do not unlock Stage C.
- Do not treat one positive micro week as tradability proof.
- Do not stop Stage 3X optimization because early unoptimized returns are weak.
- Do not pay for expensive data unless historical coverage and train/validation
  utility are proven.
- Do not merge portfolio support into SAC algorithm code; keep it config-gated
  in environment/evidence/supervisor layers.
