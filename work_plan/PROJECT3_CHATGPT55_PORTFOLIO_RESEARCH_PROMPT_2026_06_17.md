# Prompt For ChatGPT 5.5 Pro Research Agent

You are the research agent for Project 3. Your task is to give a practical,
evidence-backed research review that Codex can translate into code and
experiments. This is not an academic publication project. The only useful
outcome is better repeated next-week portfolio profit/risk after realistic
costs, under the exact weekly retraining business mechanic described below.

## Attach These Documents

Attach these 5 files to your research session and use them as the source of
truth for the project context:

1. `PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
2. `PROJECT3_EVENT_TOKEN_TRANSFORMER_AGENT_SPEC_2026_06_17.md`
3. `project3_orchestrator_event_context_representation_addendum_2026_06_09.md`
4. `PROJECT3_RESEARCH_AGENT_PRAGMATIC_CONTEXT_2026_06_09.md`
5. `PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md`

If you need more information, ask for it explicitly. Do not assume an older
Project 3 stage plan is still valid unless it is repeated in those documents.

## Business Mechanic You Must Respect

Project 3 is a weekly-retrained multi-asset portfolio trading system.

- The product is a portfolio service, not a single-asset toy backtest.
- Each tradable asset can have one or more specialist trading agents.
- The specialist agent trades only its target asset, but it may consume context
  from other assets, economic events, market-state embeddings, technical
  indicators, fundamental features, and seasonal features.
- A higher weekly portfolio supervisor decides:
  - which asset/model streams are active next week;
  - which streams receive a no-trade flag;
  - normalized capital/order-size weights for active streams;
  - max weight, max active assets, and correlation/exposure caps.
- The final user-account/execution layer is out of scope for now. We are not
  designing deposits, PAMM/social-trading plumbing, broker routing, or
  user-specific order conversion. Our current output is research-grade control
  signals and normalized portfolio weights.
- Every trainable layer must be evaluated by weekly walk-forward simulation.

## Mandatory Evaluation Rule

For every weekly anchor:

```text
fit/update only with information available before the rebalance cutoff;
train window: N years before validation, often 1-4 years depending experiment;
train-tail metric window: last configurable weeks of the train window;
validation window: next configurable week(s);
test window: following configurable week(s), recorded only after selection;
selection metric: train-tail + validation composite, not test;
repeat across all weekly anchors in the evaluation year;
compare methods by the average weekly metrics across anchors.
```

The test period must never be used to select models, weights, features,
hyperparameters, no-trade flags, or portfolio allocation parameters.

## Current Implemented System

We currently have:

- SQLite weekly job/subjob pool for multi-machine walk-forward experiments.
- Per-asset SAC jobs with scratch training, warm-start chain training, and
  recent-window fine tuning.
- Early stopping based on train-tail + validation composite.
- Event-engineered features.
- A first train-only event-token embedding bridge, not yet a full transformer.
- Zig-zag oracle and anti-oracle baselines for reference and possible future
  behavior-cloning pretraining.
- A first portfolio supervisor simulator with:
  - equal weight;
  - score weight;
  - score inverse volatility;
  - score inverse CVaR.

## Research Questions

### A. Weekly Portfolio Allocation

Find the most practical next portfolio allocation methods for weekly-retrained
strategy streams when expected returns, covariance, and downside risk must be
estimated only from past data and current pre-week context.

Compare at least:

1. Equal weight and score-weight baselines.
2. Markowitz / mean-variance portfolio optimization.
3. Downside-risk / semivariance / CVaR / post-modern portfolio theory.
4. Black-Litterman, Bayesian shrinkage, and expected-return shrinkage.
5. Hierarchical Risk Parity and other covariance-robust allocation methods.
6. Risk parity / volatility targeting / fractional Kelly.
7. Online portfolio selection / rolling allocation methods.
8. ML or meta-allocator methods using market-state/context embeddings.

For each method, answer:

- What variables are required?
- Which variables can be estimated from our weekly pool without leakage?
- What minimum history is realistic for weekly strategy streams?
- What fails when expected-return estimates are noisy?
- How should no-trade flags enter the optimizer?
- How should max active assets and max weight per asset be handled?
- How should transaction costs, spread, and weekend-flat policy be included?
- What should be the first implementable baseline?
- What should wait until simpler baselines show evidence?

### B. Trading-Language / Market-Context Transformer

Assess whether a variable-length context model is useful for:

- per-asset specialist agents;
- portfolio allocation;
- no-trade prediction;
- regime/context-conditioned model selection.

The "language" is not natural language. It is a market/event token language:
economic-calendar events, event surprise values, time-to-future-events,
historical event outcomes, cross-asset price/return tokens, technical/fundamental
tokens, seasonal tokens, and unsupervised market-state tokens.

Research:

- practical architectures for variable-length numeric/event-token sequences;
- whether a small transformer, Set Transformer, TabTransformer/FT-Transformer,
  Temporal Fusion Transformer, Perceiver-style encoder, or simple attention
  pooling is the best first implementation;
- how to avoid leakage when events have actual/expected/revised values;
- how to pretrain with self-supervised objectives without contaminating test;
- how to connect embeddings to SAC agents and to the portfolio supervisor;
- what to do first if compute is limited.

### C. Oracle Behavior Pretraining

We have an ideal zig-zag oracle and anti-oracle baseline. Research how to use
that safely:

- behavior cloning from oracle action labels;
- auxiliary loss for policy pretraining;
- contrastive positive/negative examples using oracle vs anti-oracle actions;
- whether this risks teaching impossible future-aware behavior;
- how to restrict the use to train-only labels so validation/test remain honest;
- how to evaluate whether oracle pretraining improves next-week performance.

## Required Output Format

Give a concise but complete research report with:

1. Executive recommendation.
2. Ranked immediate experiments for the next 1-2 weeks of coding.
3. Portfolio allocation method comparison table.
4. Market-context transformer architecture recommendation.
5. Oracle pretraining recommendation and leakage controls.
6. Exact variables/features needed for each recommended experiment.
7. Data leakage traps and how to prevent them.
8. Metrics to record in the weekly pool and dashboard.
9. Concrete code tasks for Codex/Claude.
10. Real citations with links. Cite primary sources or strong library docs
    where possible; do not invent references.

Be blunt. Reject any idea that sounds impressive but is not testable in our
weekly walk-forward pool.
