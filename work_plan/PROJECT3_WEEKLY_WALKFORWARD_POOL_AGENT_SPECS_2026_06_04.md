# Project 3 Weekly Walk-Forward Pool Agent Specs

Date: 2026-06-04
Status: ACTIVE COPY-READY AGENT HANDOFF

## Shared Context For All Agents

Project 3 is a weekly-retrained portfolio/RL system. The previous
the previous short-window line is obsolete and deleted. Do not recreate
it. Do not use `train_days=28`, `val_days=14`, `test_days=14` as optimization
evidence.

Correct business unit:

```text
for each weekly anchor:
  train      = N years before validation week
  validation = 7 days
  test       = next 7 days
aggregate results across weekly anchors
```

Initial sweep:

```text
train_years = 1..10
early_stop_train_tail_days = 7 initially, then compare 14 and 28
validation_days = 7 initially, then compare 14 and 28
test_days = 7 initially, then compare 14 and 28
training_policy = scratch_n_years first
Stage C = DENIED
heldout boundary = 2025-01-01
```

Use the existing repos:

```text
financial-data = /home/harveybc/Documents/GitHub/financial-data
agent-multi   = /home/harveybc/Documents/GitHub/agent-multi
gym-fx        = /home/harveybc/Documents/GitHub/gym-fx
```

Do not mutate PPO/SAC/DQN algorithm internals unless explicitly assigned.
Do not launch broad training. Mechanical tests must be tiny.

## Spec A: Queue And SQLite Pool

Recommended agent: Copilot coding agent.

Ownership:

```text
agent-multi/tools/project3_weekly_pool.py
agent-multi/tests/unit/test_project3_weekly_pool.py
```

Task:

Implement a SQLite-backed weekly walk-forward job pool.

Required CLI:

```text
python tools/project3_weekly_pool.py init --db <path>
python tools/project3_weekly_pool.py enqueue --db <path> --plan <json>
python tools/project3_weekly_pool.py claim --db <path> --machine <name>
python tools/project3_weekly_pool.py heartbeat --db <path> --machine <name> ...
python tools/project3_weekly_pool.py complete --db <path> --subjob-id <id> --result <json>
python tools/project3_weekly_pool.py fail --db <path> --subjob-id <id> --reason <text>
python tools/project3_weekly_pool.py status --db <path> --json
```

Required tables:

- `jobs`
- `subjobs`
- `results`
- `machine_heartbeats`
- `artifacts`

Required behavior:

- atomic claim with SQLite transaction;
- no two machines can claim the same subjob;
- Stage C fields must be present and equal to `DENIED`;
- enqueue rejects any subjob whose train/validation/test interval touches
  `2025-01-01` or later;
- enqueue rejects optimization jobs using `train_days=28`, `val_days=14`,
  `test_days=14`;
- status reports pending/running/done/failed counts and best aggregate summary.

Tests:

- schema creation;
- enqueue creates expected jobs/subjobs;
- duplicate claim race cannot return same subjob;
- heldout rows rejected;
- obsolete short-window optimization rejected;
- completion stores reproducibility fields and metrics, including
  `early_stop_train_tail_days`, `validation_days`, and `test_days`;
- status returns exact counts.

No training launched.

## Spec B: Weekly Split And Config Materialization

Recommended agent: Claude coding agent.

Ownership:

```text
agent-multi/tools/project3_weekly_materialize.py
agent-multi/tests/unit/test_project3_weekly_materialize.py
```

Task:

Create locked `agent-multi` configs from pool subjobs.

Inputs:

- SQLite pool DB;
- selected feature/input contract;
- target asset;
- timeframe;
- weekly anchor;
- train_years;
- early_stop_train_tail_days;
- validation_days;
- test_days;
- SAC hyperparameters;
- preprocessing profile.

Required behavior:

- compute exact train/validation/test timestamps;
- count rows in each split;
- write config JSON with `split_anchor`/explicit date boundaries;
- preserve selected features, data hash, preprocessing params, market-state
  profile id/hash, broker profile, cost scenario;
- write config path back to SQLite;
- reject missing rows or too-small splits before training;
- never use Stage C rows.

Required output fields per subjob:

```text
train_start, train_end, train_rows
validation_start, validation_end, validation_rows
test_start, test_end, test_rows
config_file
run_dir
```

Tests:

- 1-year and 4-year windows produce correct row counts;
- validation/test are exactly 7 days each;
- train_end <= validation_start < validation_end <= test_start < test_end;
- 2025 rows fail closed;
- generated config has no obsolete `train_days=28/val_days=14/test_days=14`.

No training launched.

## Spec C: Worker Loop And Remote Machine Runner

Recommended agent: Codex primary or Copilot if available.

Ownership:

```text
agent-multi/tools/project3_weekly_worker.py
agent-multi/tools/project3_weekly_remote_launcher.py
agent-multi/tests/unit/test_project3_weekly_worker.py
```

Task:

Implement worker loops for local, `dragon`, and `gamma`.

Required CLI:

```text
python tools/project3_weekly_worker.py --db <path> --machine <name> --once
python tools/project3_weekly_worker.py --db <path> --machine <name> --loop --poll-seconds 30
python tools/project3_weekly_remote_launcher.py --db <path> --machines dragon,gamma --start
```

Required behavior:

- heartbeat before and during jobs;
- claim next subjob;
- materialize config if missing;
- run `python -m app.main --load_config <config> --quiet_mode`;
- record stdout/stderr paths;
- parse result/evidence JSON into `results`;
- mark done or failed;
- request next subjob without user intervention.

Required safety:

- worker exits or idles when queue empty;
- failed subjob records exact failure reason;
- process interruption leaves subjob recoverable;
- no broad Stage C unlock.

Tests:

- `--once` claims one mocked subjob and completes;
- failure path records reason;
- stale running subjob can be reclaimed after timeout;
- heartbeat table updates.

Training in tests must be mocked, not real.

## Spec D: AdminLTE Dashboard

Recommended agent: Claude or Copilot frontend-capable coding agent.

Ownership:

```text
agent-multi/tools/project3_weekly_dashboard.py
agent-multi/tests/unit/test_project3_weekly_dashboard.py
```

Task:

Implement a local monitoring dashboard using AdminLTE.

Default command:

```text
python tools/project3_weekly_dashboard.py --db <path> --host 127.0.0.1 --port 8787
```

Default URL:

```text
http://127.0.0.1:8787
```

Use Python standard library `http.server` plus SQLite unless a dependency is
explicitly justified. AdminLTE may load by CDN; provide readable fallback if
offline.

Required pages:

- `/` global dashboard;
- `/api/status` JSON;
- `/api/jobs` JSON;
- `/api/subjobs` JSON;
- `/api/machines` JSON;
- `/api/best` JSON.

Dashboard must show:

- queue totals;
- machine cards with GPU, active subjob, heartbeat age, ETA;
- active subjobs with job id, asset, timeframe, training policy, train_years,
  anchor, train/validation/test dates and row counts;
- best aggregate so far by return, Sharpe, drawdown, CVaR, cost ratio;
- training-window sweep chart/table for `train_years=1..10`;
- failure table;
- reproducibility details: features, preprocessing, hyperparameters, data hash,
  config path, run path.

Tests:

- server renders HTML;
- API status returns expected JSON from fixture DB;
- dashboard handles empty DB gracefully.

No training launched.

## Spec E: Financial-Data Plan/Contract Worker

Recommended agent: Codex or Claude.

Ownership:

```text
financial-data/_scripts/workers/project3_weekly_pool_plan_worker.py
financial-data/_scripts/tests/test_project3_weekly_pool_plan_worker.py
```

Task:

Generate the first clean pool plan JSON from existing validated data inventory.

Initial plan:

```text
target_asset = btcusdt_perp
timeframe = 4h
training_policy = scratch_n_years
train_years = 1..10
early_stop_train_tail_days = 7 initially, then 14/28 comparison
validation_days = 7 initially, then 14/28 comparison
test_days = 7 initially, then 14/28 comparison
anchors = representative pre-2025 weekly anchors
seeds = 0,1,2
model_family = SAC actor-critic
```

Required output:

```text
financial-data/experiments/weekly_walkforward_pool/weekly_pool_seed_plan.json
financial-data/experiments/weekly_walkforward_pool/weekly_pool_seed_plan.md
```

Required checks:

- no Stage C rows;
- selected data file exists;
- enough rows for every split;
- exact row counts per anchor;
- feature list and preprocessing recorded;
- plan includes enough metadata to reproduce each subjob.

No training launched.

## Completion Definition

The system is ready to run when:

1. SQLite pool initializes.
2. Seed plan enqueues.
3. Dashboard opens on `http://127.0.0.1:8787`.
4. One local mocked worker test passes.
5. No obsolete short-window artifacts are required by active code.
6. All active docs point to this weekly walk-forward pool, not to the deleted
   short-window smoke chain.
