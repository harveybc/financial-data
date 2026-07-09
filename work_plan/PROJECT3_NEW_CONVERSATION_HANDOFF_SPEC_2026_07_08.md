# Project3 New Conversation Handoff Spec - 2026-07-08

This document is the handoff prompt/context for replacing the current Codex
conversation with a fresh one. The next agent must continue Project3 as a
senior machine learning scientist, senior software engineer, trading systems
engineer, data scientist, and production/SRE operator. It must be practical,
evidence-driven, leakage-aware, and careful with GPU/RAM orchestration.

## Immediate Incident State

Date/time of handoff: 2026-07-08, America/Bogota.

Omega had a confirmed memory exhaustion incident. Kernel logs show repeated
global OOM kills between 14:50 and 16:03 COT. The killed processes were Python
processes inside Project3 user units, especially:

- `project3-weekly-worker.service`
- `project3-weekly-pool-api.service`

Typical killed process size:

- total virtual memory: 24-43 GB;
- anonymous RSS: 21-30 GB;
- swap was full or almost full.

Hermes disabled Project3 cron/startup entries. This was correct. Do not blindly
restart all Project3 services.

Current safe-mode correction applied:

- omega Project3 systemd user services are disabled;
- dragon `project3-weekly-api-worker.service` is stopped/disabled;
- gamma `project3-weekly-api-worker.service` is stopped/disabled;
- Project3 training processes were stopped on omega, dragon, and gamma;
- stale `running` subjobs were requeued to `pending`;
- `machine_heartbeats` rows for omega/dragon/gamma were set to `disabled`.

As of the correction:

```text
weekly pool status:
  done:       15758
  failed:     21
  pending:    246
  deferred:   8327
  superseded: 2624
  running:    0

market_token_transformer_probe_v1_20260708:
  done:    65
  failed:  1
  pending: 246
  running: 0
```

The system is intentionally paused. Resume only after a resource-safe plan is
chosen.

## Mandatory Status Behavior

When the user asks `status`, do not quote stale DB rows as truth. Always do live
checks:

1. Query the pool DB.
2. SSH to dragon and gamma.
3. Check actual `project3` / `app.main` processes.
4. Check GPU utilization and memory.
5. Check stale `running` subjobs.
6. Include ETA when jobs are running.
7. If any machine is down, stale, disabled, or has no real worker/process,
   print a large visible alert.

Never say a machine is running only because `machine_heartbeats` says so.

Useful commands:

```bash
DB=/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite

sqlite3 -header -column "$DB" "
SELECT machine_id,status,current_subjob_id,
       ROUND((julianday('now')-julianday(heartbeat_at))*86400,1) AS hb_s,
       gpu_summary,message
FROM machine_heartbeats
ORDER BY machine_id;
SELECT status, COUNT(*) n FROM subjobs GROUP BY status ORDER BY status;
SELECT s.status, COUNT(*) AS n
FROM subjobs s JOIN jobs j ON j.id=s.job_id
WHERE j.config_json LIKE '%market_token_transformer_probe_v1_20260708%'
GROUP BY s.status ORDER BY s.status;
SELECT external_id, claimed_by,
       ROUND((julianday('now')-julianday(heartbeat_at))*86400,1) AS hb_s
FROM subjobs
WHERE status='running'
ORDER BY claimed_by, heartbeat_at;
"

pgrep -af '[p]roject3|[w]eekly_walkforward|python -m app[.]main' || true
nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits
nvidia-smi pmon -c 1

ssh dragon "hostname; uptime; free -h; swapon --show; nvidia-smi; pgrep -af '[p]roject3|[w]eekly_walkforward|python -m app[.]main' || true"
ssh -p 22022 192.0.2.16 "hostname; uptime; free -h; swapon --show; nvidia-smi; pgrep -af '[p]roject3|[w]eekly_walkforward|python -m app[.]main' || true"
```

## Repositories And Key Paths

Primary repos:

```text
/home/harveybc/Documents/GitHub/predictor
/home/harveybc/Documents/GitHub/agent-multi
/home/harveybc/Documents/GitHub/financial-data
```

Main SQLite OLAP/pool DB:

```text
/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

Main work plan:

```text
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md
```

Most important support documents:

```text
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/project3_orchestrator_event_context_representation_addendum_2026_06_09.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_RESEARCH_AGENT_PRAGMATIC_CONTEXT_2026_06_09.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_EVENT_TOKEN_TRANSFORMER_AGENT_SPEC_2026_06_17.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_PORTFOLIO_SUPERVISOR_V2_RESEARCH_INGEST_2026_06_17.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_OLAP_TRANSVERSAL_ANALYSIS_PLAN_2026_06_29.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_OLAP_TRANSVERSAL_ANALYSIS_REPORT_2026_06_29.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_DEADLINE_EXPERIMENT_PLAN_2026_06_30.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_DOIN_HANDOFF_CANDIDATE_PACK_2026_07_05.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_CHATGPT55_PORTFOLIO_RESEARCH_PROMPT_2026_06_17.md
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_CLAUDE_CODING_AGENT_PROMPT_2026_06_17.md
```

Code touched immediately before handoff:

```text
/home/harveybc/Documents/GitHub/agent-multi/tools/project3_weekly_pool.py
/home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md
```

`project3_weekly_pool.py` was changed so `weekly_result_olap` exposes:

- `job_config_json`
- `subjob_result_json`

The view was recreated successfully with:

```bash
python - <<'PY'
import sys
sys.path.insert(0, '/home/harveybc/Documents/GitHub/agent-multi/tools')
from project3_weekly_pool import connect, init_db
path = '/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite'
conn = connect(path)
init_db(conn)
conn.commit()
conn.close()
PY
```

## Configuration Contract

All future experiments must be JSON-first:

- `jobs.config_json` is the canonical job-level config.
- `subjobs.config_path` is the materialized weekly concrete config.
- `weekly_result_olap.job_config_json` must be used to export/recreate a run.
- `weekly_result_olap.subjob_result_json` exposes the raw result payload.
- Every data, model, optimizer, training, reward, risk, SL/TP, feature,
  embedding, and orchestration parameter should be present in JSON.
- Code defaults are fallback compatibility only, not the source of truth for new
  runs.

This is required so Metabase, DOIN, LTS, and ad-hoc scripts can extract a row
from OLAP, write a JSON file, and run with `--config` or `--load_config` without
reverse-engineering code.

## Current Scientific Plan

Project3 uses weekly retrained walk-forward evaluation:

- train on historical data before each week;
- validate on the configured validation window/year when applicable;
- test on the following weekly test window;
- aggregate weekly test results over a full test year;
- business-facing annual metrics must use near-full-year coverage, normally 48+
  weeks.

Never report a single week or partial average as an annual result unless clearly
labelled partial.

Key metrics to include in status and reports:

- mean weekly return;
- annual return;
- mean weekly drawdown;
- mean weekly RAP;
- annual RAP;
- unique test weeks / full-year coverage;
- mean weekly trades;
- worst/best weekly RAP when relevant.

## Current Best Annual Diversity Evidence

The annual diversity survey completed:

```text
phase: annual_diversity_survey_fast40k_v2
matrix: 20 assets x 3 timeframes x 52 weeks = 3120 subjobs
status: complete
```

Best decision-grade full-year row:

```text
SOLUSDT 4h
unique weeks: 52
mean weekly return: +0.1559%
annual return: +8.1072%
mean weekly RAP: +0.0629%
annual RAP: +3.2723%
mean weekly drawdown: 0.1860%
```

Other positive/near-flat full-year rows:

```text
EURUSD 4h: annual return +0.0058%, annual RAP +0.0051%
DOGEUSDT 4h: annual return +0.0039%, annual RAP +0.0028%
```

Important interpretation:

- the survey is not expected to be fully optimized;
- negative RAP rows are still useful for selecting assets/timeframes for DOIN or
  later optimization;
- portfolio construction should not rely only on SOL/crypto 4h;
- target portfolio should include at least 3 short-horizon and 3 long-horizon
  candidate streams when evidence exists.

Canonical annual selection query:

```sql
SELECT
  asset,timeframe,candidate_id,unique_weeks,coverage_ratio_52w,
  mean_weekly_return,annual_return,mean_weekly_drawdown,
  mean_weekly_rap,annual_rap,worst_weekly_rap,best_weekly_rap,
  mean_weekly_trades,last_completed_at
FROM weekly_result_full_year_protocol_olap
WHERE metric_block='test_year'
  AND candidate_id LIKE '%annual_diversity_survey_fast40k_v2%'
  AND has_near_full_year_coverage=1
ORDER BY annual_rap DESC, annual_return DESC;
```

## Current Paused Probe

The active-but-paused embedding/context probe is:

```text
phase id: market_token_transformer_probe_v1_20260708
assets: SOLUSDT, ETHUSDT, BTCUSDT_PERP
timeframes: 4h, 1h
input preset: kitchen_sink_guarded
policy: scratch_n_years
train_years: 1
test block: 2023 test_year
matrix: 6 streams x 52 weekly windows = 312 subjobs
budget: 40000 timesteps, max_epochs=20, l1_patience=4
```

Status after OOM incident cleanup:

```text
done:    65
failed:  1
pending: 246
running: 0
```

Do not resume this blindly. The OOM happened while Project3 services and
training were active. The probe may be too RAM-heavy on omega with the current
market-token feature set. If resumed, do it with a resource-safe plan:

- no automatic startup;
- one controlled worker at a time until memory is measured;
- consider not using omega as a training worker;
- consider reducing feature/token families, timesteps, or artifact transfer;
- monitor RSS/swap every 10-30 seconds at first;
- stop immediately if swap starts growing aggressively.

## LLM-Like / Market-Token Integration

The current LLM-like idea is not a natural-language LLM and is not yet a
standalone trading agent. It is a variable-token market-context encoder feeding
the SAC actor-critic.

Current implementation path:

```text
/home/harveybc/Documents/GitHub/agent-multi/tools/project3_event_token_transformer.py
/home/harveybc/Documents/GitHub/agent-multi/tools/project3_weekly_materialize.py
```

Current encoder:

- family: `event_token_transformer_v1`;
- for the market-token probe, output prefix: `ctx_mkt_tr`;
- fits normalization/encoder state on train rows only;
- inference on validation/test uses frozen train-fitted state;
- each selected feature column is treated as a token;
- token has identity/type embedding plus train-normalized numeric value;
- transformer/self-attention + attention pooling emits fixed embedding columns;
- appended columns: `ctx_mkt_tr_00..ctx_mkt_tr_15`,
  `ctx_mkt_tr_attn_mass`, `ctx_mkt_tr_token_count`;
- SAC actor-critic sees these as ordinary numeric input features in the
  environment observation.

It is currently a leakage-safe frozen random-projection transformer with a
ridge auxiliary readout, not a fully backprop-trained deep transformer.

Likely next scientific step if evidence justifies it:

- trainable encoder;
- Set Transformer / Perceiver / TFT-style market-state encoder;
- portfolio-level context model that predicts opportunity/bloom probability
  and allocates between asset/timeframe specialists.

## Portfolio Direction

The business target is a portfolio of specialist agents, not one asset:

- asset-specific trading agents;
- multiple timeframes;
- at least a short-horizon sleeve and long-horizon sleeve;
- higher-level allocator decides weekly distribution and asset selection;
- allocator should exploit rush/bloom weeks when detectable;
- portfolio/user execution layers are out of scope for now.

Rush/bloom research should use OLAP:

- find weeks/assets/configs with unusually high return and RAP;
- compare pre-week market state/context;
- look for repeatable predictors of opportunity;
- do not use future leakage in live allocation.

## DOIN Context

User owns a decentralized optimization platform called `doin` on GitHub. It is
plugin-based and uses DEAP-style decentralized optimization with blockchain
history/OLAP. The RTX 5090/eGPU work will likely switch focus to DOIN.

Do not start implementing DOIN unless the user explicitly asks. The previous
instruction before the OOM was to focus on experiments and handoff context, not
DOIN implementation.

When DOIN implementation resumes, the goal is a plugin/config bridge that can
evaluate Project3 weekly-retrained trading/portfolio candidates from JSON.

## Safe Resume Procedure

Before resuming any Project3 job:

1. Confirm system memory/swap on omega, dragon, gamma.
2. Confirm Project3 services are disabled or intentionally controlled.
3. Confirm no `running` stale subjobs.
4. Decide whether omega should be API-only, dashboard-only, or no Project3 at
   all.
5. Start pool API manually only if needed.
6. Start one remote worker manually and monitor memory/GPU.
7. Only after 15-30 minutes stable, consider a second worker.
8. Avoid running omega training worker until OOM root cause is mitigated.

Useful requeue command for stale running rows:

```bash
python - <<'PY'
import json, sqlite3
from datetime import datetime, timezone
path = '/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite'
conn = sqlite3.connect(path)
conn.row_factory = sqlite3.Row
now = datetime.now(timezone.utc).isoformat(timespec='seconds')
rows = conn.execute("SELECT external_id, claimed_by, heartbeat_at FROM subjobs WHERE status='running'").fetchall()
with conn:
    for r in rows:
        conn.execute("""
        UPDATE subjobs
        SET status='pending', claimed_by=NULL, claimed_at=NULL, heartbeat_at=NULL,
            config_path=NULL, run_dir=NULL, result_json=NULL, error=NULL, updated_at=?
        WHERE external_id=? AND status='running'
        """, (now, r['external_id']))
        conn.execute(
            "INSERT INTO pool_events(event_type, subject_id, payload_json, created_at) VALUES (?, ?, ?, ?)",
            ("manual_requeue_stale", r["external_id"], json.dumps(dict(r), sort_keys=True), now),
        )
print(f"requeued={len(rows)}")
PY
```

## User Interaction Requirements

The user is direct and will be upset by vague orchestration. The next agent must:

- be explicit;
- avoid excuses;
- verify before claiming;
- include ETA in status;
- clearly label partial versus full-year results;
- never let stale DB rows masquerade as live workers;
- keep repos clean before pushing;
- protect user worktree changes;
- use `rg` first for search;
- use `apply_patch` for manual file edits;
- avoid destructive commands unless explicitly requested.

If a machine is disabled or down, status must include a large warning.
