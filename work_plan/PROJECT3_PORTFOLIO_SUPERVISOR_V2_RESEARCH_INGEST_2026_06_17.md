# Project 3 Portfolio Supervisor v2 Research Ingest

Date: 2026-06-17
Status: ACCEPTED INTO ACTIVE PLAN

## Source Package

The 2026-06-17 ChatGPT 5.5 Pro research response arrived as:

```text
PROJECT3_RESEARCH_REVIEW_AUTOCRITIC_ORCHESTRATOR_2026-06-17.md
PROJECT3_ORCHESTRATOR_HANDOFF_2026-06-17.md
PROJECT3_EXPERIMENT_PLAN_2026-06-17.json
PROJECT3_LEAKAGE_ACCEPTANCE_CHECKLIST_2026-06-17.md
PROJECT3_PORTFOLIO_SCHEMA_DELTA_2026-06-17.sql
```

The useful decision is not to jump to a sophisticated learned allocator. The
next business-aligned layer is a deterministic, auditable portfolio supervisor
that allocates across already-trained per-asset streams using only information
known before each weekly rebalance.

## Accepted Immediately

- Keep `selection_score = 0.5 * train_tail_total_return + 0.5 * validation_total_return`.
- Never use same-anchor test return for stream selection, no-trade gates, risk
  estimation, covariance/CVaR, or allocation parameters.
- Add explicit v2 allocation method names for top-K capped baselines.
- Add turnover and rebalance cost accounting.
- Add max stream, max asset, and max cluster exposure caps.
- Add hard no-trade gates before allocation.
- Write a per-rebalance cutoff manifest with:

```text
same_anchor_test_used = false
future_anchor_used = false
stage_c_access = DENIED
```

- Treat equal weight and score weight as mandatory baselines. Optimized
  allocators can easily underperform when weekly stream history is short or
  noisy.

## Already Implemented In Agent-Multi

Implemented in:

```text
agent-multi/tools/project3_portfolio_supervisor.py
```

Current v2 additions:

```text
equal_weight_top_k_capped
score_weight_top_k_capped
score_inverse_vol_top_k_capped
score_inverse_cvar_top_k_capped
score_inverse_vol_turnover_penalty
score_inverse_cvar_turnover_penalty
score_inverse_vol_portfolio_vol_target
portfolio_activations
portfolio_cutoff_manifests
```

The implementation keeps the older method names available for compatibility.

## Accepted But Deferred

These are valid research directions, but should not block the current v2
portfolio layer:

- HRP / shrunk covariance allocation;
- full Markowitz optimization;
- Black-Litterman;
- Kelly sizing;
- learned ML/meta-allocator;
- large transformer/market-language model as the portfolio allocator.

They require more stable multi-asset weekly stream history and stronger
multiple-testing controls before promotion.

## Event Context Policy

Event context should first be used as risk/no-trade/sizing information, not as
guaranteed directional alpha. Any event-derived field used in a trading
observation must satisfy:

```text
first_available_ts <= model_decision_ts
```

Fields without reliable point-in-time availability are audit/reporting-only.

## Oracle Policy

ZigZag oracle and anti-oracle labels are allowed only as train-window behavior
pretraining or auxiliary signals. Validation/test oracle labels are
reporting-only. Promotion depends on trading composite and post-selection
diagnostics, not oracle imitation accuracy.

## Multiple-Testing Note

Search width must be visible. Future dashboards should count:

```text
candidate_count
parameter_config_count
seed_count
anchor_count
selected_by_test
```

Deflated Sharpe / PBO diagnostics are useful reporting additions once enough
candidate history exists, but they are not a reason to stop pragmatic
experimentation now.
