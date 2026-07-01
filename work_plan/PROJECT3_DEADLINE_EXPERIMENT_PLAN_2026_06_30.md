# Project3 Deadline Experiment Plan - 2026-06-30

## Hard Deadline

Today is Tuesday 2026-06-30. The RTX 5090 setup is expected Monday
2026-07-06. On Monday morning the current weekly-pool work plan will be
paused and the project will switch to `doin` decentralized optimization with
the best model/data/configuration available at that time.

This plan is therefore time-boxed. It does not wait for a stable metric,
trigger, or perfect completion of the current queue.

## Objective

By Sunday 2026-07-05 evening, freeze one practical winner candidate and a small
backup shortlist for the Monday `doin` handoff.

The winner must be selected from comparable weekly walk-forward evidence:

- annual return;
- annual RAP;
- mean weekly return;
- mean weekly RAP;
- mean weekly drawdown;
- worst-week RAP;
- week coverage;
- runtime and operational stability.

Full-year results dominate partial results. Partial results are useful only for
promotion decisions and insight generation.

## Current State Snapshot

Snapshot taken from the live pool on 2026-06-30 around 12:20 America/Bogota.

- Dashboard: `http://127.0.0.1:8787`
- SQLite pool:
  `/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite`
- Active machines: omega, dragon, gamma.
- Subjobs: 10129 done, 249 pending, 3 running, 5991 deferred, 2688
  superseded, 4 failed.
- Remaining active backlog:
  - `risk_adjusted_reward_phase7_v3`: ETHUSDT 4h, 112 pending, 1 running.
  - `sltp_risk_geometry_phase8_v3`: ETHUSDT 4h, 137 pending, 2 running.

Best full-year test candidate at snapshot:

- ETHUSDT 4h, `risk_adjusted_reward_phase7_v3`, scratch 4y,
  `rv0p075`, 52 test weeks.
- annual return: +1.4593%.
- annual RAP: -2.2305%.
- mean weekly return: +0.0281%.
- mean weekly RAP: -0.0429%.

Best partial signals at snapshot:

- ETHUSDT 4h, Phase7 `rv0p075`, 20 test weeks:
  annualized return +5.5048%, annualized RAP +3.3171%.
- SOLUSDT 4h `aware_rv0p50_base` remains a high-interest partial from the
  transversal OLAP review and must not be forgotten. It is not a final winner
  until it has comparable coverage.

## Allocation Rule

Remaining time is a portfolio. Do not let one axis consume all compute.

Approximate capacity from the last live run is roughly 15-20 weekly subjobs per
hour across three machines, but planning must assume slower periods and machine
interruptions. Every status check should adjust the remaining allocation.

If a lane overruns its time budget, reduce breadth or probe weeks in the next
lane. If a lane finds no useful signal early, stop expanding it.

## Experiment Lanes

### Lane A - Finish Current ETH Risk Baseline

Time box: Tuesday afternoon through early Wednesday.

Purpose:

- finish enough of the already-running Phase7/Phase8 ETHUSDT 4h backlog to
  know whether the current risk-adjusted reward and SL/TP geometry candidates
  can beat the previous full-year baseline;
- preserve the best full-year candidate for Monday.

Rules:

- do not enqueue additional ETH-only breadth while other lanes are waiting;
- if the remaining Phase7/Phase8 queue stretches past Wednesday morning,
  defer weak or redundant pending subjobs and move to Lane B;
- keep status reports focused on annual return/RAP, mean weekly return/RAP,
  mean weekly drawdown, and coverage.

### Lane B - Asset/Timeframe Diversity

Time box: Wednesday.

Purpose:

- avoid entering Monday with only ETHUSDT 4h evidence;
- test the most promising assets/timeframes in short but comparable windows.

Priority order:

1. SOLUSDT 4h continuation from the `aware_rv0p50_base` partial signal.
2. SOLUSDT 1h only if it can be tested cheaply and does not starve SOL 4h.
3. BTCUSDT 4h and BNB/XRP style broad-market alternatives if already present
   in the data inventory and plan builders.
4. ETHUSDT 1h only as a sanity comparison against ETHUSDT 4h.

Probe design:

- 8-12 evenly-spaced weeks for first pass;
- promote only the top few to near-full-year validation/test coverage;
- do not treat partial annualized numbers as final.

Promotion signal:

- positive or near-frontier mean weekly RAP;
- annualized return materially above the current ETH full-year baseline;
- drawdown not exploding relative to return;
- enough trades to avoid no-trade artifacts.

Concrete SOLUSDT 4h partials to prioritize for promotion:

| Candidate family | Coverage | Annualized return | Annualized RAP | Note |
| --- | ---: | ---: | ---: | --- |
| `adaptive_top_seed_extension_seed6_v1`, `aware_rv0p50_base` | 10 weeks | +64.69% | +44.80% | strongest partial at snapshot |
| `adaptive_top_seed_extension_seed8_v1`, `aware_rv0p50_base` | 10 weeks | +51.53% | +29.27% | strong replication |
| `adaptive_top_seed_extension_seed7_v1`, `aware_rv0p50_base` | 10 weeks | +51.71% | +27.66% | strong replication |
| `sltp_risk_geometry_phase8_v1`, `margin_aware_rv0p50_cap2p5` | 10 weeks | +47.38% | +27.15% | risk-geometry alternative |
| `sltp_risk_geometry_phase8_v1`, `fixed_rv0p50_sl1p25_tp1p25` | 10 weeks | +42.32% | +22.13% | simple high-exposure baseline |

These are promotion candidates, not final winners, because they are still
partial. The next useful work is extending coverage and checking whether the
signal survives outside the initial bloom weeks.

### Lane C - Data And Feature Representation Diversity

Time box: Thursday.

Purpose:

- touch the main data/representation axes before the 5090 switch;
- identify which representation should be part of the Monday `doin` search
  space.

Required representation probes:

- current `kitchen_sink_guarded_exec` baseline;
- `tech_stat_decomp`;
- `sota_low_cost`;
- event-context features;
- event-token attention embedding;
- event-token transformer embedding.

Rules:

- run small probes first, not full-year broad sweeps;
- compare within the same asset/timeframe/risk profile wherever possible;
- promote only representations that improve L1/validation RAP without creating
  obvious test-only artifacts.

### Lane D - Training Policy And Oracle Pretraining

Time box: Friday.

Purpose:

- compare scratch vs fine-tune where it matters;
- test whether oracle behavior pretraining is a useful initialization signal
  without contaminating causality.

Required comparisons:

- scratch 4y vs fine-tune recent window m3/m6/m12 for the strongest
  asset/representation candidates;
- oracle behavior-cloning pretrain on a very small, audit-friendly probe;
- no extra model-family expansion unless it is already implemented and cheap.

Rules:

- oracle labels are allowed only when generated from the training window;
- test remains report-only;
- if oracle pretraining is unstable or expensive, record the failure and stop.

### Lane E - Finalist Full-Year Promotion

Time box: Saturday.

Purpose:

- convert the best partials into comparable full-year evidence.

Promote:

- best ETHUSDT 4h Phase7/8 full-year candidate;
- best SOLUSDT candidate if partial signal remains strong;
- best representation-diversity candidate;
- best scratch/fine-tune/oracle candidate if it is distinct from the above.

Each promoted finalist should target at least 48 weekly test windows when
possible. Anything below that is a backup, not the primary Monday winner.

### Lane F - Freeze And Handoff

Time box: Sunday.

Purpose:

- freeze winner and backup shortlist;
- document exact data file, preprocessing, feature set, model config,
  hyperparameters, risk geometry, and evaluation metrics;
- leave Monday clean for `doin`.

Sunday rules:

- no new large sweeps after Sunday noon;
- run only sanity checks, missing-week completion, and report generation;
- any `doin` implementation/config work is deferred until the user explicitly
  asks component-by-component during the weekend.

## Status-Time Control Rules

Every status check should include:

- active machines and heartbeat freshness;
- big alert if any machine is stale, down, or has no progress;
- active subjob per machine;
- pending/running/done counts;
- current ETA;
- best full-year annual return and annual RAP;
- best partial candidate clearly marked as partial;
- whether the current lane is on schedule.

Early stale detection:

- heartbeat older than 10 minutes: warning;
- heartbeat older than 20 minutes: alert and inspect/restart;
- GPU utilization near zero plus no progress for more than 15 minutes:
  investigate immediately;
- remote API heartbeat without progress still counts as suspicious if the
  progress file is static.

Backlog control:

- if pending queue is below 30 and before Sunday noon, enqueue the next planned
  lane;
- if pending queue is above 250 and it is all one axis, do not enqueue more of
  that axis;
- if a lane exceeds its time budget, reduce probe weeks or promote fewer
  candidates in the next lane.

## Monday Switch Rule

On Monday 2026-07-06 morning:

1. stop or pause Project3 weekly-pool services/jobs unless a tiny sanity job is
   explicitly approved;
2. freeze the best available Project3 candidate;
3. start `doin` integration/optimization preparation with that candidate;
4. do not wait for remaining Project3 sweeps to finish.
