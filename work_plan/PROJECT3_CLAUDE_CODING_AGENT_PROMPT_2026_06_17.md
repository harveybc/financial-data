# Prompt For Claude Coding Agent

You are helping on Project 3, a pragmatic weekly-retrained portfolio trading
system. Do not treat this as an academic benchmark. The business target is a
paid portfolio/trading service where each client account holds multiple active
asset streams, rebalanced weekly. Per-asset SAC agents trade inside each asset;
a higher portfolio layer decides weekly asset activation, no-trade flags, and
order-size/capital weights.

Repository context:

```text
agent-multi repo:
/home/harveybc/Documents/GitHub/agent-multi

financial-data repo:
/home/harveybc/Documents/GitHub/financial-data

active pool DB:
/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite

active work plan:
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md

event transformer spec:
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_EVENT_TOKEN_TRANSFORMER_AGENT_SPEC_2026_06_17.md
```

Current implemented pieces:

```text
agent-multi/tools/project3_weekly_pool.py
agent-multi/tools/project3_weekly_materialize.py
agent-multi/tools/project3_weekly_phase_orchestrator.py
agent-multi/tools/project3_portfolio_supervisor.py
```

Codex already implemented:

- `context_embedding_profile.family = event_token_attention_v1`
  in `project3_weekly_materialize.py`;
- first portfolio supervisor simulator in `project3_portfolio_supervisor.py`;
- tests:
  - `tests/unit/test_project3_weekly_pool.py`
  - `tests/unit/test_project3_portfolio_supervisor.py`.

Your task has two parts.

## Part A: Event Token Transformer Encoder

Implement:

```text
context_embedding_profile.family = event_token_transformer_v1
```

Requirements:

1. Fit only on each subjob train window. Do not fit scalers, weights, targets,
   or model parameters on validation/test rows.
2. Use selected source columns, initially `event_*`, as variable/source-token
   inputs.
3. Produce fixed row embeddings:

```text
ctx_evt_tr_00 ... ctx_evt_tr_{embedding_dim-1}
ctx_evt_tr_attn_mass
ctx_evt_tr_token_count
```

4. Write a manifest:

```json
{
  "schema_version": "project3_context_embedding_manifest_v1",
  "family": "event_token_transformer_v1",
  "fit_scope": "train_only",
  "fit_window_start": "...",
  "fit_window_end": "...",
  "source_columns": [],
  "embedding_columns": [],
  "diagnostic_columns": [],
  "training_summary": {},
  "model_config": {}
}
```

5. Integration point must remain `project3_weekly_materialize.py`, so pool
   workers can materialize a subjob and run SAC without custom manual steps.
6. Start small: 1-2 encoder blocks, small hidden size, CPU-safe for tests.
   GPU use is allowed in production but tests must be lightweight.
7. If PyTorch is used, make the implementation deterministic by seed.
8. If dependencies are unavailable, fail clearly with a useful error.

Add tests proving:

- refuses missing source columns when `required=true`;
- fit metadata is train-only;
- validation/test rows are transformed but not fitted;
- generated columns are added to `feature_list`;
- materialized config points to the derived CSV;
- phase orchestrator can dry-run an `event_token_transformer_v1` phase.

## Part B: Portfolio Supervisor Hardening

Improve `project3_portfolio_supervisor.py` without breaking the current API.

Add:

1. A covariance-aware long-only Markowitz-style allocator if feasible without
   heavy dependencies. If not feasible, implement a robust diagonal fallback
   and document it clearly.
2. A downside-risk allocator using semivariance or CVaR from prior weekly
   returns only.
3. A no-trade/activation rule:
   - inactive if composite signal <= threshold;
   - inactive if prior lookback has too few observations;
   - inactive if recent drawdown exceeds threshold.
4. SQLite output tables remain reproducible and append/replace by `run_id`.
5. Tests for:
   - no use of current test return in allocation;
   - weights sum to 1 for active weeks;
   - max weight cap;
   - no-trade activation;
   - covariance/downside allocator deterministic behavior.

## Business Rules

- Selection metric is:

```text
0.5 * train_tail_total_return + 0.5 * validation_total_return
```

- Test return is never used for selection or allocation.
- Stage C rows remain denied.
- Weekend-flat rule remains.
- Portfolio layer controls order-size/capital weights; per-asset agents still
  choose trading actions inside their assigned budget.

## Commands To Run

From `agent-multi`:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest \
  tests/unit/test_project3_weekly_pool.py \
  tests/unit/test_project3_portfolio_supervisor.py -q

/home/harveybc/anaconda3/envs/tensorflow/bin/python -m py_compile \
  tools/project3_weekly_materialize.py \
  tools/project3_weekly_phase_orchestrator.py \
  tools/project3_portfolio_supervisor.py
```

Do not launch long training jobs. Only code, unit tests, and dry-runs.

Report:

- files changed;
- exact new config/profile names;
- test results;
- any blockers.
