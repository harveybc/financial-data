# Project 3 Research Agent Pragmatic Context Brief

Date: 2026-06-09
Audience: external research / web / literature agent
Status: ACTIVE CONTEXT PACKET

## Purpose

This document tells a research agent how Project 3 currently works and how to
give useful recommendations. The research agent may not know the current
business mechanics, so it must not assume this is a static academic benchmark.

Project 3 is a weekly retrained portfolio trading system. Research should help
us improve profit/risk under that business loop.

## The Current Business Loop

The production-shaped loop is:

```text
1. use only data known before a weekend decision cutoff;
2. train or update the model;
3. trade the following week;
4. retrain/update again the next weekend;
5. allocate portfolio capital and no-trade flags weekly;
6. eventually provide this as a paid trading/portfolio service.
```

The research simulation mirrors this:

```text
weekly anchor:
  train       = N years before the validation week
  train_tail  = final slice of train, used only for early-stop/ranking metric
  validation  = next week or configurable next period
  test        = period after validation, inspected only after selection
```

The serious evidence unit is not one run. It is a collection of weekly
subjobs across many historical anchors.

## Selection Criterion

The primary score is:

```text
score = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

The test result is reported for the model selected by this score. The test
result is not used to select the model.

This is intentional. Ranking by validation alone can overfit to validation.
Ranking by test is leakage. Ranking by train-tail + validation is a pragmatic
compromise that rewards recent train behavior and validation behavior without
using the test week.

## What Not To Recommend

Do not recommend:

- a static one-year holdout benchmark as the main criterion;
- using test results to pick candidates;
- launching broad GPU searches before a matched weekly-pool comparison exists;
- direct LLM trading agents;
- Stage C access or heldout rows before the final locked evaluation;
- more elaborate gates that block practical experimentation;
- single-week promotion;
- "causal proof of alpha" language;
- academic pass/fail stages that do not map to profit/risk.

## What To Recommend Instead

Useful recommendations should be framed as:

- candidate input families;
- candidate preprocessing profiles;
- candidate model or hyperparameter families;
- candidate portfolio/risk overlays;
- exact matched baseline comparison;
- expected effect on weekly train-tail + validation;
- risk of leakage;
- minimum data coverage needed;
- how to test cheaply before GPU scaling.

Every recommendation should answer:

```text
What existing baseline should this be compared against?
Which asset/timeframe should test it first?
Which weekly anchors should be reused?
Which fields must be point-in-time?
What would count as a practical improvement?
What failure mode would make this idea not worth pursuing?
```

## Current System State

The weekly SQLite job pool exists and runs continuously.

Current default DB:

```text
financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

Dashboard:

```text
http://127.0.0.1:8787
```

The pool supports:

- weekly subjobs;
- `scratch_n_years`;
- warm-start chains;
- train/validation/test splits;
- train-tail + validation composite scoring;
- persistent run artifacts;
- machine heartbeat;
- dashboard monitoring.

Current active modeling family is SAC on 4h crypto inputs, especially
`sota_low_cost`.

Recent evidence:

- BTC-perp 4h with current SAC/input setup produced no positive composite
  score in the earlier sweep.
- A multi-asset sweep found preliminary positive composite signals in
  `ethusdt` 4h.
- This makes `ethusdt` 4h a better immediate target for input/context
  improvements than repeating more BTC-perp-only runs.

## Event Context Idea

We are considering adding event/calendar/news context, inspired by the fact that
LLM-like systems handle variable-length context well. But the implementation
must be pragmatic.

The first form should not be a full transformer or direct LLM agent. It should
be engineered point-in-time features:

- upcoming high-impact event count;
- time to next high-impact event;
- event importance weighted by asset/currency relevance;
- CPI/FOMC/NFP/central-bank week flags;
- recent surprise values only after availability;
- event-window no-trade and sizing risk;
- spread/slippage stress around events.

Only after this engineered baseline has value should we test learned event-token
encoders.

## Point-In-Time Rule

For event/calendar data, the most important practical issue is timestamp
quality.

Required concept:

```text
first_available_ts <= model_decision_ts
```

If actual/forecast/revision/surprise values lack reliable availability
timestamps, they must not enter trading observations. They may be used only for
source coverage reports.

Scheduled future events are different. Their existence, release time, event
family, country/currency, and provider importance may be known before the
weekend cutoff and can be used if the source proves they were available then.

## Preferred Research Output Format

Use this structure:

```text
Recommendation:
  ADD / TEST LATER / DO NOT ADD

Business fit:
  How it helps weekly retrained trading.

Data requirements:
  Exact fields, coverage, timestamps, availability rules.

First practical experiment:
  asset:
  timeframe:
  baseline:
  candidate:
  anchors:
  score:
  expected runtime:

Leakage risks:
  What can go wrong and how to mask/reject.

Failure criteria:
  What result means we stop pursuing it.

Next action:
  A concrete worker/spec/query, not a broad research wish.
```

## Acceptable Literature Use

Literature is useful to justify testing a feature family, not to declare that it
will be profitable.

Good literature use:

- "macro surprises affect FX price discovery, therefore event surprise is worth
  testing on EURUSD/AUDUSD";
- "attention pooling handles variable-size sets, therefore it is a candidate
  encoder after engineered event features pass";
- "geopolitical risk affects downside risk, therefore it is first a risk/OOD
  feature, not a directional alpha signal."

Bad literature use:

- "paper says it works, therefore launch broad GPU search";
- "LLMs are powerful, therefore use an LLM to trade";
- "causal inference suggests relation, therefore unlock Stage C";
- "one positive week proves alpha."

## Current Research Priorities

Priority 1:

```text
Find data/input combinations that improve weekly train-tail + validation.
```

Priority 2:

```text
Expand promising assets, especially ethusdt 4h and later FX pairs.
```

Priority 3:

```text
Add event context as engineered point-in-time features and compare against
matched baselines in the weekly pool.
```

Priority 4:

```text
Only after engineered event context has value, test event-token embeddings.
```

Priority 5:

```text
Use portfolio supervisor and no-trade/sizing overlays once strategy streams
have enough evidence.
```

## Final Instruction To Research Agents

Be critical, pragmatic, and business-oriented. Do not optimize for sounding
academic. Optimize for helping us find a repeatable asset/data/model/risk setup
that can make money after costs under weekly retraining.

If a recommendation does not map to a concrete weekly-pool experiment, rewrite
it until it does.
