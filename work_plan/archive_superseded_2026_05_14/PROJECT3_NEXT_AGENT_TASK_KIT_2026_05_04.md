# Project 3 Next Agent Task Kit — 2026-05-04

This kit assigns the next useful work while Stage 3.1 continues running. It assumes:

- Claude and Copilot have repo/code access.
- ChatGPT 5.5 Pro is web-only and must receive all context in the prompt or via small attachments.
- No agent may touch Stage C or launch Phase 4 training.
- Current Stage B gate status: 356 Stage A candidates classified; 0 Stage B ready; the only surviving candidate is blocked by `LEDGER_MISSING_ENTRY`, `DSR_APPROXIMATE_INSUFFICIENT`, and `PBO_DEFERRED`.
- Current Phase 4 synthetic protocol status: dry-run arm scaffold exists and is locked; no multi-phase runner exists; no Phase 4 training should launch.

## Current Refresh — 2026-05-10 UTC

This section supersedes the stale 356-candidate snapshot above.

- Stage A index refreshed to **4,933 runs**.
- Supervisor/worker queue check: `overall_ok=true`, no active queue anomalies.
- Current Stage B approval counts:
  - `KILL_NON_POSITIVE_RETURN`: 2,761
  - `KILL_NO_TRADES`: 1,154
  - `KILL_NEGATIVE_SHARPE`: 974
  - `BLOCKED_DSR_DEFERRED`: 32
  - `BLOCKED_FAMILY_ABLATION`: 8
  - `BLOCKED_BASELINE_COMPARISON`: 4
  - `PASS_STAGE_B_READY`: 0
- Ledger mapping is no longer the active blocker for the top candidates; deterministic composite matching is working.
- B1/B10 heldout audit: 3,515 auditable runs pass, 0 leakage failures, 1,418 blocked by missing train inputs.
- B8 simple-baseline evidence refreshed: 3,515 runs with baselines; 72 beat base/pessimistic simple-baseline checks.
- B9 family-ablation evidence refreshed; best ETHUSDT 4h SAC tech_stat passes B9.
- No-trade diagnostic with trace scan:
  - 1,154 no-trade runs
  - 930 traces scanned, 224 trace files missing
  - `policy_deadband_collapse`: 520
  - `policy_hold_collapse`: 410
  - `needs_continuous_action_trace`: 89
  - `needs_discrete_action_trace`: 135
- Best current `BLOCKED_DSR_DEFERRED` candidate by return:
  - `ethusdt_perp_15m_sac_tech_full_direct_atr_sltp_s1_20260503T141731Z_project3_stage31_firstwave`
  - total return `0.529359`, Sharpe `0.069861`, trades `198`
  - blockers: `DSR_APPROXIMATE_INSUFFICIENT`, `PBO_DEFERRED`
- Previous ETHUSDT 4h SAC tech_stat candidate remains viable but is no longer the top return:
  - total return `0.151216`, trades `426`
  - blockers: `DSR_APPROXIMATE_INSUFFICIENT`, `PBO_DEFERRED`
- `stageb_dsr_pbo_evaluator.py` now fails closed when no Stage B runs exist:
  - `stage=stage_b_missing`
  - `stage_b_gate_clearance=BLOCKED_NO_STAGE_B_RUNS`
  - Stage A fallback scanning requires explicit `PROJECT3_STAGEB_DSR_PBO_SCAN_STAGE_A_FALLBACK=1`.

Immediate next engineering work:

1. **DONE:** Generate a locked Stage B run plan for the 32 `BLOCKED_DSR_DEFERRED` candidates and their matched baselines, including return-trace/evidence paths and no Stage C access.
   - Worker: `_scripts/workers/stage_b_locked_run_plan_worker.py`
   - Outputs: `experiments/stage_b_validation/run_plan/stage_b_locked_run_plan.{json,csv,md}`
   - Locked config templates: 90
   - Candidate templates: 64 (32 candidates x base/pessimistic)
   - Matched RL baseline templates: 26
   - Blocked matched baseline templates: 1 (`BLOCKED_INPUT_MISSING`)
   - All generated configs set `_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED=true`, `stage_c_access=DENIED`, `return_trace_dir=...`, and a live progress contract with `trades_total` and `total_return`.
   - Status reader: `_scripts/workers/stage_b_run_plan_status_worker.py`
   - Status outputs: `experiments/stage_b_validation/run_plan/stage_b_run_plan_status.{json,csv,md}`
   - Current status: 90 `NOT_STARTED_LOCKED`, 0 anomalies.
2. Implement or verify the Stage B runner can execute 1M-step validation runs with `return_trace_dir`/`evidence.json` enabled while respecting the Stage B lock.
3. Run no-trade remediation only for diagnostics/parameter repair; do not promote no-trade runs.
4. After Stage B traces exist, run the Stage B DSR/PBO evaluator and then add Reality Check/SPA/paired-seed aggregation.

## Priority Order

1. Claude: clear the `LEDGER_MISSING_ENTRY` blocker by implementing robust ledger/run ID resolution in the Stage B approval gate.
2. Copilot: implement return-trace emission and Stage B statistical-input scaffolding in `agent-multi`, without launching training.
3. ChatGPT 5.5 Pro: research and critique the exact DSR/PBO/Reality Check/SPA implementation choices for RL trading, with thresholds and pseudocode.
4. Codex: verify all outputs, patch integration defects, and keep supervisor/watchdog health checked.

---

## Prompt For Claude — Ledger ID Resolver And Stage B Gate Integration

```text
Act as a senior Python/research-platform engineer working inside the financial-data repo.

Mission:
Fix the Stage B approval gate's `LEDGER_MISSING_ENTRY` blocker without weakening the gate. The current best Stage A survivor is:

ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave

The Stage B approval gate currently reports that this run_slug is not found as a direct `run_id` or `trial_id` in the ledger. The known suspicion is that ledger IDs and run directory slugs use different formats. Implement a robust resolver and tests.

Context:
- Current worker: `_scripts/workers/stage_b_approval_gate_worker.py`
- Current tests: `_scripts/tests/test_stage_b_approval_gate_worker.py`
- Current outputs: `experiments/stage_a_screening/stage_b_approval/`
- Ledger sources may include `artifacts/run_ledger.parquet`, `artifacts/run_ledger.jsonl`, and related summary/index artifacts.
- Existing Stage B gate statuses: 239 `KILL_NON_POSITIVE_RETURN`, 66 `KILL_NEGATIVE_SHARPE`, 50 `KILL_NO_TRADES`, 1 `BLOCKED_DSR_DEFERRED`.
- The target is NOT to mark any candidate Stage B ready. DSR/PBO must remain blocked until rigorous Stage B return traces exist.

Required implementation:
1. Inspect actual ledger columns and rows.
2. Identify how run directory slugs map to ledger entries.
3. Implement `resolve_ledger_membership(run_slug, ledger_entries)` or equivalent.
4. Use conservative matching only:
   - exact match on `run_id`, `trial_id`, `run_slug`, `output_dir`, or basename of run path;
   - deterministic canonicalization is allowed if documented and tested;
   - fuzzy matching is forbidden.
5. Emit evidence fields in the approval CSV/JSON:
   - `ledger_match_status`
   - `ledger_match_field`
   - `ledger_match_value`
   - `ledger_trial_id`
   - `ledger_run_id`
6. If no deterministic match exists, keep `LEDGER_MISSING_ENTRY`.
7. Regenerate the Stage B approval packet.
8. Add/extend unit tests covering:
   - exact `run_id` match;
   - exact `trial_id` match;
   - basename path match;
   - canonicalized slug match, if implemented;
   - no false positive on near/fuzzy match;
   - best-run fixture if feasible.

Safety constraints:
- Do not launch training.
- Do not touch Stage C or any 2025-01-01+ data.
- Do not weaken DSR/PBO blockers.
- Do not mark any candidate `PASS_STAGE_B_READY` unless all gate criteria are truly satisfied.

Commands to run:
- `python -m pytest _scripts/tests/test_stage_b_approval_gate_worker.py -q`
- `python _scripts/workers/stage_b_approval_gate_worker.py`

Final response:
- files changed;
- tests run;
- exact ledger resolution rule implemented;
- whether `LEDGER_MISSING_ENTRY` cleared for the best run;
- final candidate status counts;
- confirmation that DSR/PBO remain blocked and Stage C was not touched.
```

---

## Prompt For Copilot — Return Trace And Stage B Statistical Inputs In Agent-Multi

```text
Act as a senior ML infrastructure engineer working inside the agent-multi repo.

Mission:
Implement the return-trace emission and Stage B statistical-input scaffold required by Project 3, without launching training.

Why:
The financial-data Stage B approval gate blocks the only surviving Stage A candidate on:
- `DSR_APPROXIMATE_INSUFFICIENT`
- `PBO_DEFERRED`

Both require per-step/per-bar return traces and enough metadata for rigorous Stage B statistical evaluation. Stage B training will later run 1M-step PPO/SAC/DQN jobs; today you must only implement the plumbing and tests.

Required behavior:
1. Add config support for `return_trace_file`.
2. During RL evaluation/training, when configured, write a machine-readable trace file containing at minimum:
   - timestamp or step index;
   - asset/timeframe if available;
   - close/price used for reward if available;
   - action;
   - position or exposure;
   - reward;
   - gross_return;
   - net_return if costs are available;
   - equity/account value if available;
   - commission/slippage/cost fields if available;
   - episode/run identifiers;
   - seed;
   - split label (`train`, `validation`, `test`, or explicit evaluation split).
3. Add a compact trace metadata sidecar, preferably JSON:
   - config hash;
   - data file hash;
   - feature list hash if available;
   - seed;
   - split boundaries;
   - heldout boundary `2025-01-01`;
   - whether any trace row is at or after heldout boundary.
4. Fail closed if `return_trace_file` would include Stage C rows unless an explicit final Stage C evaluation mode is active. Do not implement final Stage C mode now.
5. Add tests using a tiny synthetic environment or mocked pipeline:
   - trace file is created when requested;
   - required columns exist;
   - row count is nonzero;
   - deterministic seed metadata exists;
   - heldout rows are rejected;
   - no trace is written when config omits `return_trace_file`;
   - existing configs still run/dry-run without requiring the new field.
6. Do not implement DSR/PBO math here. This repo only emits the raw inputs for financial-data's evaluator.

Important constraints:
- Do not launch Project 3 training.
- Do not unlock Phase 4 synthetic configs.
- Do not run Stage C.
- Do not silently change SAC/PPO/DQN hyperparameters.
- Keep backward compatibility with existing agent-multi configs.

Recommended files to inspect:
- `pipeline_plugins/rl_pipeline.py`
- `pipeline_plugins/rl_pipeline_with_validation.py` if present
- `tools/seed_sweep.py`
- Project 3 example configs under `examples/config/`
- Existing tests under `tests/`

Commands to run:
- targeted unit tests for the changed pipeline/tooling;
- if available, a dry-run or smoke test that does not train for meaningful time.

Final response:
- files changed;
- trace schema;
- tests run;
- example config snippet showing `return_trace_file`;
- confirmation no training launched and Stage C not touched;
- remaining Stage B integration work for financial-data.
```

---

## Prompt For ChatGPT 5.5 Pro — Web-Only Research Review

### Attachment Guidance

If upload limits allow, attach only these two files:

1. `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_MEMO.md`
2. `TASKS.md` from `experiments/stage_a_screening/stage_b_approval/TASKS.md`

If only one file can be attached, attach `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_MEMO.md`. Do not attach large JSON/CSV outputs unless specifically requested.

### Prompt

```text
You are acting as an external senior quantitative-research reviewer. You do not have repository access, so all relevant Project 3 context is included here.

Project 3 context:
- We are evaluating fixed PPO/SAC/DQN reinforcement-learning trading policies.
- The project varies assets, timeframes, feature families, source families, seeds, splits, and cost scenarios.
- Stage 3.1 Stage A screening is/was broad screening, not final evidence.
- Stage B is stricter validation.
- Stage C is a one-shot held-out firewall using data from 2025-01-01 onward. Stage C must not be inspected or used before final locked evaluation.
- Current Stage A hardening classified 356 candidates:
  - 239 KILL_NON_POSITIVE_RETURN
  - 66 KILL_NEGATIVE_SHARPE
  - 50 KILL_NO_TRADES
  - 1 BLOCKED_DSR_DEFERRED
- The only surviving candidate is ETHUSDT 4h SAC tech_stat seed 0, but it is blocked by:
  - LEDGER_MISSING_ENTRY: ledger ID mapping issue, not yet resolved;
  - DSR_APPROXIMATE_INSUFFICIENT: Stage A DSR was only approximate;
  - PBO_DEFERRED: Stage A single split cannot support proper PBO/CSCV.
- Stage B must emit per-step/per-bar return traces before rigorous DSR/PBO/Reality Check/SPA can be computed.
- Synthetic Phase 4 work exists but must remain training-only and cannot provide tradability evidence; synthetic-only metrics are diagnostic.

Your task:
Research and produce an implementation-grade critique and refinement of the Stage B statistical governance plan. Focus on exact choices, not generic praise.

Required sections:
1. Executive recommendation: what must be implemented before Stage B can promote any candidate.
2. Return trace schema: minimum fields required to compute DSR, PBO/CSCV, Reality Check, SPA, paired seed uncertainty, turnover/cost fragility, and performance profiles.
3. Deflated Sharpe Ratio:
   - exact formula and inputs;
   - how to estimate skew/kurtosis;
   - how to choose number of trials `N_raw`;
   - how to estimate effective number of trials `N_eff`;
   - what to do when returns are autocorrelated and non-normal.
4. PBO/CSCV:
   - why random k-fold is forbidden;
   - recommended purged/embargoed split design for 4h and 15m trading returns;
   - how to handle multiple seeds and assets;
   - minimum number of folds/paths if data is limited.
5. White Reality Check and Hansen SPA:
   - exact null;
   - studentized vs unstudentized statistic;
   - stationary/block bootstrap choice;
   - block length selection;
   - family grouping for feature/source families;
   - how to interpret a winner that passes raw metrics but fails family-level test.
6. RL seed uncertainty:
   - minimum paired seeds;
   - median/IQM/trimmed mean recommendations;
   - bootstrap CI design;
   - probability of improvement;
   - performance-profile reporting.
7. Go/no-go thresholds:
   - propose conservative defaults and justify them;
   - distinguish hard gates from warning gates.
8. Failure modes:
   - data snooping;
   - seed cherry-picking;
   - cost fragility;
   - synthetic data misuse;
   - leakage through Stage C or revised/misaligned data.
9. Implementation checklist suitable for a GitHub issue.
10. Primary references with links. Prefer primary papers, official docs, or well-cited technical sources.

Important:
- Do not suggest changing PPO/SAC/DQN algorithms.
- Do not suggest using Stage C for tuning.
- Do not suggest using synthetic validation as tradability evidence.
- Clearly separate what is mathematically required from what is practical engineering policy.
- If a recommendation depends on unavailable information, state the needed artifact precisely.

Output:
Produce a Markdown memo. Be skeptical, concrete, and implementation-oriented.
```

---

## Codex Integration Checklist

After Claude/Copilot/ChatGPT return:

- Verify worker status before reading outputs.
- Run tests locally.
- Re-run generated workers/tools.
- Confirm no Stage C access and no unauthorized training.
- Patch only integration defects.
- Update this work plan or the appropriate Stage B/Phase 4 docs if requirements changed.

---

# V2 Handoff Prompts — More Detailed, Current As Of 2026-05-05

These prompts supersede the short prompts above for the next idle-agent round. They are written as paste-ready spec kits. Use them one at a time.

Current operational update:

- Gamma recently failed to launch `usdcad_15m_baseline_12_sac_s0_50000`.
- Root cause: the remote Gamma filesystem was missing:
  - `features/trading_asset_data/usdcad/15m.parquet`
  - `features/trading_asset_features/usdcad/15m/technical.parquet`
  - generated `experiments/stage_a_screening/inputs/usdcad/15m/baseline_12/train.csv`
- Manual sync and remote input preparation fixed Gamma.
- A small watchdog status-display patch was added so active IDs can be shown even when queue sync lags.
- Dragon and Gamma continue Stage 3.1 Stage A screening.
- Stage B remains blocked until rigorous return traces plus DSR/PBO/family tests exist.

## V2 Prompt For Claude — Remote Worker Data Sync Hardening

```text
Act as a principal infrastructure and research-platform engineer working inside the financial-data repo. Your job is to make the Project 3 worker orchestration more reliable without changing experiment science.

Mission:
Prevent Dragon/Gamma launch failures caused by missing remote feature/input files.

Immediate incident context:
- Gamma failed on `usdcad_15m_baseline_12_sac_s0_50000`.
- The failing command was:
  `python _scripts/workers/stage31_prepare_inputs_worker.py --asset usdcad --timeframe 15m --preset baseline_12 --split train`
- The remote Gamma repo lacked:
  - `features/trading_asset_data/usdcad/15m.parquet`
  - `features/trading_asset_features/usdcad/15m/technical.parquet`
  - `experiments/stage_a_screening/inputs/usdcad/15m/baseline_12/train.csv`
- Manual rsync of the missing files fixed the issue and Gamma resumed training.

Project constraints:
- Do not touch Stage C.
- Do not access, inspect, tune on, or generate outputs from data at or after `2025-01-01` except existing approved preheldout pipeline checks.
- Do not launch new training manually except through the existing watchdog/worker mechanism if needed to validate the prelaunch fix.
- Do not change PPO/SAC/DQN algorithms, hyperparameters, feature definitions, or queue semantics.
- Do not weaken any Stage B governance gates.
- Preserve Dragon/Gamma/Omega responsibilities.

Existing relevant files to inspect:
- `_scripts/orchestration/project3_stage31_watchdog.py`
- `_scripts/workers/stage31_agent_multi_run_worker.py`
- `_scripts/workers/stage31_prepare_inputs_worker.py`
- `_scripts/workers/stage31_expand_matrix_queue_worker.py`
- `_scripts/workers/stage31_reconcile_queue_worker.py`
- `experiments/stage_a_screening/queues/dragon.json`
- `experiments/stage_a_screening/queues/gamma.json`

Required design:
Implement a deterministic remote-prelaunch data availability layer. Before launching a remote worker on Dragon/Gamma, the watchdog or a small helper must:

1. Determine the next runnable pending job for the remote machine.
2. Determine the required source files for that job:
   - always require `features/trading_asset_data/<asset>/<timeframe>.parquet`;
   - for `baseline_12`, require `features/trading_asset_features/<asset>/<timeframe>/technical.parquet` if Omega has it, because baseline features are selected from technical features;
   - for non-baseline presets, derive required feature families from the same mapping used by `_scripts/workers/stage31_prepare_inputs_worker.py`;
   - if a feature family is optional in current preparation logic, report it as optional/missing-not-fatal, not fatal;
   - if a required file is absent on Omega too, fail closed with a clear report instead of launching a doomed remote run.
3. Check whether those files exist on the remote host.
4. Sync only missing required files/directories from Omega to the remote host.
5. Optionally sync an already-generated input CSV if present on Omega:
   `experiments/stage_a_screening/inputs/<asset>/<timeframe>/<preset>/train.csv`
   but the remote machine must still be able to regenerate it via `stage31_prepare_inputs_worker.py`.
6. Verify remote readiness after sync.
7. Emit a compact machine-readable and human-readable report.

Required report fields:
- generated_at
- machine
- host
- run_id
- asset
- timeframe
- preset
- split
- required_files
- optional_files
- omega_missing_required_files
- remote_missing_before_sync
- synced_files
- remote_missing_after_sync
- readiness_status: `ready`, `blocked_missing_on_omega`, `sync_failed`, `not_remote`, `no_pending_job`
- commands_or_rsync_operations run

Recommended implementation shape:
- Prefer adding pure helper functions that are easy to unit test:
  - `required_files_for_job(job) -> RequiredFilePlan`
  - `remote_file_exists(machine, relpath) -> bool`
  - `sync_required_files(machine, plan) -> SyncReport`
- Keep SSH/rsync effects isolated from pure planning.
- If modifying `project3_stage31_watchdog.py`, keep the code small and conservative.
- Consider a new helper module or worker if that keeps the watchdog readable, e.g.:
  `_scripts/workers/stage31_remote_data_preflight.py`
  but do not over-engineer a new framework.

Acceptance criteria:
1. For the known incident job `usdcad_15m_baseline_12_sac_s0_50000`, the planner includes:
   - `features/trading_asset_data/usdcad/15m.parquet`
   - `features/trading_asset_features/usdcad/15m/technical.parquet`
2. If the remote is missing these files and Omega has them, the preflight syncs them and reports `ready`.
3. If Omega lacks a required base parquet, the preflight reports blocked and does not launch.
4. Watchdog status remains accurate.
5. The queue is not mutated except by existing worker/reconcile logic.
6. Unit tests cover the planning logic without requiring SSH.
7. `python -m py_compile` passes for changed scripts.

Tests to add or run:
- Unit test required-file planning for:
  - baseline_12 FX job;
  - tech_stat job;
  - tech_stat_decomp job;
  - learned_lstm/learned_cnn job with missing optional artifact behavior documented;
  - crypto_full/fx_full asset-family remapping if applicable.
- Existing Stage 3.1 worker tests if available.
- At minimum:
  `python -m py_compile _scripts/orchestration/project3_stage31_watchdog.py`
  and any new helper/test file.

Operational validation:
- Do not force a new experiment grid.
- If Dragon/Gamma are active, do not interrupt them.
- A dry preflight report is enough. If a remote worker is idle and has pending queue, allow the normal watchdog path to launch after readiness succeeds.

Failure modes to handle explicitly:
- remote SSH unavailable;
- remote parent directory missing;
- rsync failure;
- Omega missing source file;
- queue has no pending job;
- queue job has malformed `asset`, `timeframe`, or `preset`;
- remote queue sync lags behind process status.

Final response format:
1. Summary of the incident class fixed.
2. Files changed.
3. Exact required-file planning rule.
4. Tests run and results.
5. Whether Dragon/Gamma remote launch preflight is now protected.
6. Any remaining risks.
7. Confirmation: no Stage C touched, no algorithm/hyperparameter changes, no unauthorized training launched.
```

## V2 Prompt For Copilot — Agent-Multi Return Trace Evidence Index

```text
Act as a principal ML platform engineer working inside the agent-multi repo. Your task is to make Stage B statistical evidence discoverable and auditable, without changing model behavior.

Mission:
Add a first-class evidence index for Project 3 return traces emitted by agent-multi.

Background:
- agent-multi now emits Stage B return traces via:
  - `pipeline_plugins/_return_trace.py`
  - `pipeline_plugins/rl_pipeline.py`
  - `pipeline_plugins/rl_pipeline_with_validation.py`
- Trace schema version is `stage_b_return_trace_v1`.
- Each trace gets a `.meta.json` sidecar.
- Current gap: financial-data needs to discover all trace and metadata paths for a run without scraping logs or guessing split-specific paths.

Project constraints:
- Do not launch training.
- Do not access Stage C.
- Do not unlock Phase 4 synthetic configs.
- Do not change SAC/PPO/DQN algorithms or hyperparameters.
- Preserve backward compatibility for configs without return tracing.
- Keep `stage_b_return_trace_v1` stable unless a breaking change is truly necessary. If breaking, justify and update tests.

Existing files to inspect:
- `pipeline_plugins/_return_trace.py`
- `pipeline_plugins/rl_pipeline.py`
- `pipeline_plugins/rl_pipeline_with_validation.py`
- `tools/seed_sweep.py`
- `tests/unit/test_return_trace.py`
- `tests/unit/test_project3_phase4_protocol_dry_run.py`
- Project 3 configs under `examples/config/`

Required feature:
When return tracing is enabled, produce a run-level evidence index that financial-data can ingest.

Acceptable implementation options:
- Option A: Add a top-level `return_trace_evidence` object to the pipeline summary/results JSON.
- Option B: Write an `evidence.json` file next to the trace(s), and include its path in the summary.
- Best result: do both if simple:
  - summary contains enough direct pointers;
  - `evidence.json` is a durable artifact.

Evidence index schema:
At minimum:

```json
{
  "schema_version": "project3_return_trace_evidence_v1",
  "generated_at": "...",
  "run_id": "...",
  "pipeline_plugin": "rl_pipeline or rl_pipeline_with_validation",
  "trace_schema_version": "stage_b_return_trace_v1",
  "asset": "...",
  "timeframe": "...",
  "seed": 0,
  "config_hash": "...",
  "data_file": "...",
  "data_file_hash": "...",
  "feature_list_hash": "...",
  "heldout_boundary": "2025-01-01",
  "contains_heldout_rows": false,
  "stage_c_authorized": false,
  "traces": [
    {
      "split": "train|validation|test|evaluation",
      "trace_file": "...",
      "trace_file_sha256": "...",
      "metadata_file": "...",
      "row_count": 123,
      "first_timestamp": "...",
      "last_timestamp": "...",
      "contains_heldout_rows": false,
      "stage_c_authorized": false
    }
  ]
}
```

Hard validation:
- If any trace metadata says `contains_heldout_rows: true` and `stage_c_authorized: false`, evidence generation must fail.
- If a trace file path is missing or metadata file is missing, evidence generation must fail.
- If split labels are duplicated unexpectedly, evidence generation must fail.
- If no traces are produced because tracing is disabled, do not produce evidence and do not error.

Desired helper shape:
- Add helper functions to `_return_trace.py` or a small sibling module:
  - `build_return_trace_evidence(metadata_items, config, output_path=None)`
  - `write_return_trace_evidence(...)`
- Avoid duplicating sidecar parsing logic in multiple pipelines.
- Keep field names explicit and stable.

Tests required:
1. Legacy config without `return_trace_file` or `return_trace_dir` still passes and produces no evidence.
2. Single-split `rl_pipeline` emits:
   - trace CSV;
   - trace `.meta.json`;
   - evidence JSON or summary `return_trace_evidence`.
3. Multi-split `rl_pipeline_with_validation` emits evidence with all split traces.
4. Evidence contains `trace_schema_version`, `heldout_boundary`, `contains_heldout_rows`, and `stage_c_authorized`.
5. Evidence generation fails closed if metadata indicates unauthorized heldout rows.
6. Evidence generation fails closed if trace metadata file is missing.
7. Existing Phase 4 dry-run tests remain green.

Commands to run:
- `python -m pytest tests/unit/test_return_trace.py -q`
- `python -m pytest tests/ -q`
- Optional import smoke:
  `python - <<'PY'\nfrom pipeline_plugins import _return_trace\nprint(_return_trace.SCHEMA_VERSION)\nPY`

Do not run:
- Project 3 training jobs.
- Stage C evaluation.
- Any command that unlocks Phase 4 synthetic training.

Final response format:
1. Files changed.
2. Evidence schema implemented.
3. Example evidence JSON snippet.
4. Tests run and results.
5. Confirmation that legacy configs still work.
6. Confirmation that no training launched and Stage C was not touched.
7. Remaining financial-data integration work.
```

## V2 Prompt For ChatGPT 5.5 Pro — N_eff And Family Testing Research Memo

Use this for the web-only ChatGPT 5.5 Pro. It has no repo access, so include all context below. Attachments are optional.

Attachment guidance:
- Best single attachment: `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md`
- If a second attachment is allowed: `experiments/stage_a_screening/stage_b_approval/TASKS.md`
- Do not attach large CSV/JSON files unless asked.

```text
You are acting as an external senior quantitative-research reviewer specializing in financial backtest overfitting, multiple testing, and empirical RL evaluation. You do not have repository access, so all relevant Project 3 context is included in this prompt.

Project 3 context:
- We are evaluating fixed PPO/SAC/DQN reinforcement-learning trading policies.
- The project varies assets, timeframes, feature families, source families, seeds, splits, and cost scenarios.
- Stage 3.1 Stage A screening is broad screening, not final evidence.
- Stage B is stricter validation.
- Stage C is a one-shot held-out firewall using data from `2025-01-01` onward.
- Stage C must not be inspected, summarized, tuned on, calibrated on, or used before final locked evaluation.
- Current Stage A hardening classified 356 candidates:
  - 239 `KILL_NON_POSITIVE_RETURN`
  - 66 `KILL_NEGATIVE_SHARPE`
  - 50 `KILL_NO_TRADES`
  - 1 `BLOCKED_DSR_DEFERRED`
- The only surviving candidate is `ETHUSDT 4h SAC tech_stat seed 0`.
- Its ledger mapping is now resolved, but it remains blocked by:
  - `DSR_APPROXIMATE_INSUFFICIENT`
  - `PBO_DEFERRED`
- Stage B must emit per-bar return traces before rigorous Deflated Sharpe Ratio, PBO/CSCV, White Reality Check, Hansen SPA, and paired seed uncertainty can be computed.
- Synthetic Phase 4 work exists but must remain training-only. Synthetic-only metrics are diagnostic and cannot provide tradability evidence.

Research task:
Produce an implementation-grade memo specifically about estimating:

1. the raw number of trials `N_raw`;
2. the effective number of trials `N_eff`;
3. the correct family groupings for Deflated Sharpe Ratio, White Reality Check, and Hansen SPA in Project 3.

This must be concrete enough for an engineer to implement. Avoid generic praise or vague warnings.

Required sections:

## 1. Executive Recommendation
- Give the conservative default policy for Project 3.
- State when to use `N_raw`, when to use `N_eff`, and when to report both.
- State whether a candidate can promote if `N_eff` is uncertain.

## 2. Define `N_raw`
Address whether each of the following counts as a distinct trial:
- algorithm: PPO/SAC/DQN;
- asset;
- timeframe;
- feature preset;
- feature family;
- source family;
- synthetic protocol;
- reward config;
- action-space config;
- cost scenario;
- split version;
- seed;
- failed run;
- killed run;
- manually discarded run;
- rerun after code/config fix.

For each, say:
- count as distinct trial;
- repeated measurement;
- diagnostic-only;
- or separate family but not same-family trial.

## 3. Estimate `N_eff`
Give practical estimators for effective number of trials when candidate returns are correlated.
Include at least:
- correlation-matrix eigenvalue / participation-ratio approach;
- clustering of strategy return streams;
- Li/Ji or related effective-number approximations if appropriate;
- conservative cap/floor rules;
- what to do when only summary metrics are available;
- what to do when per-bar return traces are available.

Make the policy fail-closed:
- if traces are missing, what conservative value should be used?
- if correlation matrix is singular or unstable, what fallback?
- if there are fewer than a minimum number of return observations, what fallback?

## 4. DSR Trial Count Policy
Explain how `N_raw` and `N_eff` enter DSR.
Provide formulas or pseudocode.
State how to report:
- `DSR_N_raw`
- `DSR_N_eff`
- `DSR_selected_gate_value`
and which one should control promotion.

## 5. White Reality Check / Hansen SPA Family Grouping
Define Project 3 comparison families:
- feature family tests;
- source family tests;
- asset/timeframe tests;
- algorithm-specific tests;
- synthetic protocol tests;
- cost-scenario tests;
- paid-data overlay tests.

For each family, specify:
- benchmark/null model;
- alternatives included;
- whether killed/failed variants are included;
- whether seeds are averaged first or treated as variants;
- whether cost scenarios are separate tests or stress dimensions.

## 6. Seeds: Trials Or Repeated Measurements?
Give a strong recommendation for RL seeds.
Discuss:
- matched seed design;
- whether seed 0,1,2 are separate strategies or repeated measurements;
- minimum paired seeds;
- how seeds interact with DSR trial count;
- how seeds interact with Reality Check/SPA.

## 7. Killed, Failed, And Missing Runs
Define exact accounting rules for:
- no-trade runs;
- non-positive-return kills;
- negative-Sharpe kills;
- OOM/NaN/interrupted runs;
- missing trace files;
- reruns after infrastructure failure.

Do not allow silent deletion.

## 8. Practical Defaults For Project 3
Propose default values/policies:
- minimum return-trace length;
- minimum candidates per family;
- minimum seeds;
- bootstrap repetitions;
- block-length selection for 4h and 15m returns;
- family-test p-value thresholds;
- DSR threshold;
- PBO warning/gate thresholds;
- when to downgrade a hard gate to a warning because data are insufficient.

## 9. Implementation Pseudocode
Provide pseudocode for:
- building the trial ledger;
- computing `N_raw`;
- computing `N_eff` from return traces;
- choosing DSR gate value;
- grouping candidates for Reality Check/SPA;
- producing a fail-closed promotion decision.

## 10. Failure Modes And Guardrails
Include:
- data snooping;
- seed cherry-picking;
- correlated trials;
- family leakage;
- synthetic data misuse;
- Stage C leakage;
- revised/misaligned data;
- cost fragility;
- accidental undercounting of trials.

## 11. Primary References
Use primary papers, official docs, or well-cited technical sources.
At minimum discuss:
- Deflated Sharpe Ratio;
- Probability of Backtest Overfitting / CSCV;
- White Reality Check;
- Hansen SPA;
- stationary/bootstrap methods for dependent time series;
- empirical RL uncertainty / performance profiles.

Important constraints:
- Do not suggest changing PPO/SAC/DQN algorithms.
- Do not suggest using Stage C for tuning, calibration, or threshold selection.
- Do not suggest using synthetic validation as tradability evidence.
- Separate mathematical requirements from engineering policy.
- If a recommendation depends on unavailable artifacts, name the exact artifact needed.

Output:
Produce a Markdown memo with equations, tables, implementation defaults, and a GitHub-issue-style checklist.
```

## V2 Prompt For Codex Integration Owner

```text
Act as Codex, the Project 3 integration owner. Review the outputs from Claude, Copilot, and ChatGPT 5.5 Pro. Do not assume they are correct.

Required sequence:
1. Check Dragon/Gamma/Omega status before editing.
2. Inspect the external-agent file changes.
3. Run relevant tests locally.
4. Re-run generated workers/tools if safe.
5. Confirm no Stage C access and no unauthorized training.
6. Patch only integration defects.
7. Summarize accepted outputs, rejected outputs, files changed, tests run, and remaining blockers.

Current high-priority blockers:
- Stage B DSR/PBO still need return-trace ingestion and evaluator implementation.
- Remote worker launch preflight must prevent missing-data failures.
- agent-multi trace evidence should be discoverable without log scraping.

Final response:
- worker status;
- agent-output verification;
- patches made by Codex;
- tests run;
- whether Stage C stayed untouched;
- next recommended task.
```

---

# V3 Production Handoff Spec Kits — Current As Of 2026-05-05

These V3 prompts are more prescriptive than V2. They are intended for the next idle-agent round and should be pasted exactly, with only small path adjustments if the local workspace differs.

Current verified state to include in every handoff:

- Project 3 evaluates fixed PPO/SAC/DQN RL trading policies.
- Stage A screened 356 candidates.
- The only surviving candidate is `ETHUSDT 4h SAC tech_stat seed 0`.
- The ledger issue is resolved for that candidate by deterministic composite key:
  - `ledger_match_field = composite_asset_timeframe_algo_preset_seed`
  - `ledger_run_id = ethusdt_4h_tech_stat_sac_s0_50000`
  - `ledger_trial_id = c76965f79c5dad1ca8bee650`
- Remaining promotion blockers:
  - `DSR_APPROXIMATE_INSUFFICIENT`
  - `PBO_DEFERRED`
- agent-multi now emits Stage B return traces and run-level evidence indexes:
  - trace schema: `stage_b_return_trace_v1`
  - evidence schema: `project3_return_trace_evidence_v1`
- financial-data still needs to ingest and validate those evidence indexes before a DSR/PBO evaluator can trust them.
- Stage C begins at `2025-01-01` and must not be touched.
- Phase 4 synthetic work remains training-only and cannot provide tradability evidence.

## V3 Prompt For Claude — Financial-Data Stage B Trace Evidence Ingestion

Use this for Claude because it has repo access and is strong at careful implementation plus tests.

```text
Act as a senior research-platform engineer and skeptical ML governance implementer inside the `financial-data` repo. Your work must make Project 3 Stage B return-trace evidence ingestible, auditable, and fail-closed.

Mission:
Implement the financial-data side of the agent-multi return-trace evidence handoff.

Why this matters:
Claude already fixed Stage B ledger resolution. Copilot already added return trace emission and `evidence.json` indexes in agent-multi. financial-data now needs a loader/validator that can consume those artifacts and connect them to the Stage B approval gate and future DSR/PBO evaluator.

Do not implement DSR/PBO yet unless there is already an obvious stub to wire. This task is about artifact ingestion, schema validation, hashing, ledger consistency, Stage C guarding, and reportability.

Hard constraints:
- Do not touch Stage C data or outputs.
- Do not launch training.
- Do not change PPO/SAC/DQN algorithms or configs.
- Do not weaken existing Stage B approval blockers.
- Do not silently ignore missing or malformed evidence.
- Do not use fuzzy ledger matching. Only use the deterministic matching rules already implemented.
- Preserve existing generated Stage A and Stage B reports unless a rerun is necessary and safe.

Known agent-multi evidence schema:

Top-level `evidence.json` fields:
- `schema_version`: must equal `project3_return_trace_evidence_v1`
- `generated_at`
- `run_id`
- `pipeline_plugin`
- `trace_schema_version`: must equal `stage_b_return_trace_v1`
- `asset`
- `timeframe`
- `seed`
- `config_hash`
- `data_file`
- `data_file_hash`
- `feature_list_hash`
- `heldout_boundary`: must equal `2025-01-01`
- `contains_heldout_rows`
- `stage_c_authorized`
- `traces[]`

Each `traces[]` entry:
- `split`
- `trace_file`
- `trace_file_sha256`
- `metadata_file`
- `row_count`
- `first_timestamp`
- `last_timestamp`
- `contains_heldout_rows`
- `stage_c_authorized`
- `episode_id` may be present

Known return trace CSV fixed column order:

```text
step,timestamp,asset,timeframe,split,episode_id,run_id,seed,bar_index,price,action_raw,position,reward,gross_return,net_return,equity,pnl,commission_paid,slippage_paid,trade_cost,trades
```

Required implementation:

1. Add a reusable loader module, preferably:
   `_scripts/lib/stageb_trace_evidence.py`

   It should expose pure-ish functions:
   - `load_evidence(path) -> dict`
   - `validate_evidence_schema(evidence) -> list[str] or raises`
   - `validate_trace_files(evidence, root=None) -> TraceEvidenceValidation`
   - `load_trace_header(trace_file) -> list[str]`
   - `validate_trace_csv(trace_file, expected_sha256, expected_schema) -> TraceFileValidation`
   - `summarize_evidence(evidence) -> compact dict`

2. Validation must fail closed on:
   - missing evidence file;
   - invalid JSON;
   - wrong `schema_version`;
   - wrong `trace_schema_version`;
   - missing top-level fields;
   - missing trace entries;
   - duplicate split labels;
   - missing trace file;
   - missing metadata file;
   - trace SHA mismatch;
   - metadata JSON invalid;
   - metadata `trace_file_sha256` mismatch with evidence;
   - timestamp parse failure;
   - non-monotonic trace timestamps within a trace;
   - `heldout_boundary != "2025-01-01"`;
   - any `contains_heldout_rows = true` while `stage_c_authorized = false`;
   - any trace row timestamp at or after `2025-01-01` while not Stage C authorized.

3. Build a small CLI worker:
   `_scripts/workers/stageb_trace_evidence_ingest_worker.py`

   Required CLI behavior:
   - `--evidence-file PATH` validates one evidence file.
   - `--evidence-glob GLOB` validates many evidence files.
   - `--output-dir experiments/stage_b/evidence_ingest` default.
   - writes:
     - `trace_evidence_ingest_report.json`
     - `trace_evidence_ingest_report.md`
     - `trace_evidence_ingest.csv`
   - exits nonzero if any evidence file has a hard validation error, unless `--report-only` is explicitly passed.

4. Add Stage B approval integration without pretending DSR/PBO is solved.

   If appropriate, update `_scripts/workers/stage_b_approval_gate_worker.py` so it can optionally read a trace evidence ingest report or evidence index path and add fields:
   - `trace_evidence_status`
   - `trace_evidence_file`
   - `trace_schema_version`
   - `trace_splits`
   - `trace_row_count_total`
   - `trace_contains_heldout_rows`
   - `trace_stage_c_authorized`
   - `trace_blockers`

   Important:
   - If Stage B trace evidence is absent, the candidate remains blocked by DSR/PBO. Do not mark it ready.
   - If trace evidence exists and passes, only clear a future `TRACE_EVIDENCE_MISSING`/`TRACE_EVIDENCE_INVALID` style blocker. Do not clear `DSR_APPROXIMATE_INSUFFICIENT` or `PBO_DEFERRED`.

5. Tests:

   Add tests under `_scripts/tests/`, preferably:
   `_scripts/tests/test_stageb_trace_evidence.py`

   Required test cases:
   - valid single-split evidence passes;
   - valid multi-split evidence passes;
   - missing evidence file fails;
   - wrong schema fails;
   - missing top-level field fails;
   - duplicate split labels fail;
   - missing trace file fails;
   - trace SHA mismatch fails;
   - unauthorized heldout in top-level evidence fails;
   - unauthorized heldout in trace entry fails;
   - timestamp at or after `2025-01-01` fails when unauthorized;
   - unparseable timestamp fails;
   - non-monotonic timestamps fail;
   - metadata/evidence mismatch fails;
   - CSV header missing required trace fields fails;
   - CLI writes JSON/MD/CSV reports on valid fixture.

6. Fixtures:
   Use temporary files generated inside tests. Do not depend on live agent-multi outputs.

7. Commands to run:
   - `python -m pytest _scripts/tests/test_stageb_trace_evidence.py -q`
   - `python -m pytest _scripts/tests/test_stage_b_approval_gate_worker.py -q`
   - `python _scripts/workers/stageb_trace_evidence_ingest_worker.py --help`
   - `python -m py_compile _scripts/lib/stageb_trace_evidence.py _scripts/workers/stageb_trace_evidence_ingest_worker.py`

8. Acceptance criteria:
   - The loader can validate `project3_return_trace_evidence_v1`.
   - All unauthorized heldout cases fail closed.
   - Hash mismatches fail closed.
   - Trace CSV schema mismatches fail closed.
   - Existing Stage B approval tests remain green.
   - No candidate is promoted merely because trace evidence exists.
   - No training launched.
   - Stage C not touched.

Final response format:
- Files changed.
- Schema accepted.
- Validation rules implemented.
- Tests run and exact results.
- Whether the ETHUSDT 4h SAC tech_stat candidate is still blocked.
- Remaining blockers after this task.
- Confirmation: no Stage C touched, no training launched, no algorithm/hyperparameter changes.
```

## V3 Prompt For Copilot — Agent-Multi Stage B Locked Run-Plan Expander

Use this for Copilot/Opus because it has repo access and is strong at code generation and test scaffolding.

```text
Act as a senior ML systems engineer inside the `agent-multi` repo. Your job is to create a locked Stage B run-plan expander for Project 3. This is a dry-run/config-generation task only; do not launch training.

Mission:
Generate auditable Stage B run-plan manifests and locked configs for the current surviving Project 3 candidate:
`ETHUSDT 4h SAC tech_stat`.

Why this matters:
financial-data needs Stage B return traces for rigorous DSR/PBO/Reality Check/SPA. agent-multi can now emit return traces and `evidence.json`, but we still need a deterministic run-plan scaffold that expands the candidate into seeds, cost scenarios, baselines, and trace-output paths without allowing accidental Stage C use or unauthorized training.

Hard constraints:
- Do not launch training.
- Do not touch Stage C.
- Do not unlock Phase 4 synthetic configs.
- Do not change SAC/PPO/DQN algorithm code or hyperparameters.
- Do not mutate existing Project 3 reference configs except by reading them.
- Do not write configs that can run unless they contain an explicit Stage B lock.
- Do not use data at or after `2025-01-01`.

Reference context:
- Return trace schema is `stage_b_return_trace_v1`.
- Evidence index schema is `project3_return_trace_evidence_v1`.
- Existing Project 3 Phase 4 dry-run tool:
  `tools/project3_phase4_protocol_dry_run.py`
- Existing trace module:
  `pipeline_plugins/_return_trace.py`
- Existing trace tests:
  `tests/unit/test_return_trace.py`
- Existing Phase 4 dry-run tests:
  `tests/unit/test_project3_phase4_protocol_dry_run.py`

Required feature:
Create a Stage B locked run-plan expander, preferably:
`tools/project3_stageb_run_plan.py`

The tool should accept:
- `--reference-config PATH`
- `--candidate-id ethusdt_4h_sac_tech_stat`
- `--output-dir PATH`
- `--seeds 0,1,2,3,4` default minimum 5
- `--cost-scenarios base,pessimistic` default
- `--baselines no_trade,buy_and_hold,random,momentum,reversal` default
- `--heldout-start 2025-01-01` default
- `--dry-run-validate-only`

Generated outputs:
1. `stageb_run_plan_manifest.json`
2. `stageb_run_plan_manifest.md`
3. locked candidate configs, one per:
   - seed;
   - cost scenario;
   - model variant: candidate plus matched baselines where supported by existing infrastructure.
4. Each generated config must include:
   - `_project3_stage_b_lock`
   - `_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED: true`
   - `heldout_start: "2025-01-01"`
   - `stage_c_access: "DENIED"`
   - `return_trace_dir` or `return_trace_file`
   - deterministic output paths for trace CSV, metadata sidecars, and evidence JSON
   - copied algorithm/hyperparameter settings from the reference config without changes
   - seed explicitly set
   - cost scenario explicitly set
   - candidate metadata: asset, timeframe, algorithm, feature preset, source family if available

Manifest required fields:
```json
{
  "schema_version": "project3_stageb_run_plan_v1",
  "generated_at": "...",
  "reference_config": "...",
  "reference_config_sha256": "...",
  "candidate_id": "ethusdt_4h_sac_tech_stat",
  "algorithm": "sac",
  "asset": "ETHUSDT",
  "timeframe": "4h",
  "feature_preset": "tech_stat",
  "heldout_start": "2025-01-01",
  "stage_c_access": "DENIED",
  "training_launched": false,
  "seeds": [0, 1, 2, 3, 4],
  "cost_scenarios": ["base", "pessimistic"],
  "baselines": [...],
  "configs": [
    {
      "role": "candidate|baseline",
      "baseline_name": null,
      "seed": 0,
      "cost_scenario": "base",
      "config_file": "...",
      "return_trace_dir": "...",
      "expected_evidence_file": "..."
    }
  ],
  "promotion_rules": {
    "minimum_paired_seeds": 5,
    "candidate_must_beat_matched_baseline_under_base_cost": true,
    "pessimistic_cost_must_not_be_catastrophic": true,
    "stage_c_forbidden": true
  }
}
```

Validation rules:
- Refuse to generate if reference config points to data with max timestamp at or after `2025-01-01` unless the config is explicitly marked final Stage C. Since this is not Stage C, that should fail.
- Refuse if reference config lacks asset/timeframe/agent/pipeline fields needed for trace emission.
- Refuse if output config omits return trace configuration.
- Refuse if generated config lacks `_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED: true`.
- Refuse if seed list has fewer than 5 seeds unless `--allow-too-few-seeds-for-smoke-test` is passed. The manifest must label that as non-promotable.
- Refuse if cost scenarios do not include both `base` and `pessimistic` unless explicitly overridden for smoke testing.
- Never invoke training commands.

Baseline handling:
- If agent-multi already has baseline strategy plugins, wire them as config variants.
- If not, generate baseline configs as `TEMPLATE_ONLY_BASELINE_NOT_IMPLEMENTED` entries in the manifest and clearly mark them `promotion_eligible: false` until implemented.
- Do not fake baseline performance.

Tests required:
Create:
`tests/unit/test_project3_stageb_run_plan.py`

Required test cases:
1. Valid reference config produces manifest and locked configs.
2. All generated configs include `_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED: true`.
3. No generated config contains `stage_c_access` other than `DENIED`.
4. Seeds default to at least five.
5. Cost scenarios include `base` and `pessimistic`.
6. Output paths for trace/evidence are deterministic.
7. Reference config SHA changes when config changes.
8. Heldout-violating reference config is rejected.
9. Too-few-seeds fails unless smoke override is passed.
10. Existing Phase 4 dry-run tests remain green.

Commands to run:
- `python tools/project3_stageb_run_plan.py --help`
- `python -m pytest tests/unit/test_project3_stageb_run_plan.py -q`
- `python -m pytest tests/ -q`

Do not run:
- `seed_sweep.py` in a way that trains.
- Any Stage C script.
- Any command that flips Phase 4 locks.

Final response format:
- Files changed.
- Manifest schema implemented.
- Generated config directory.
- Tests run and exact results.
- Explicit confirmation that no training launched.
- Explicit confirmation that Stage C stayed denied.
- Remaining gaps, especially any baseline configs marked template-only.
```

## V3 Prompt For ChatGPT 5.5 Pro — Exact Stage B Evaluator Algorithms

Use this for web ChatGPT 5.5 Pro. It has no repo access. Attach at most the refined governance memo if useful.

Recommended attachment:
- `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md`

Optional second attachment if available:
- `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_MEMO _last`

Do not attach large JSON/CSV files.

```text
You are acting as an external senior quantitative research reviewer and statistical-methods architect. You do not have repository access. All Project 3 context needed for this task is included below.

Project 3 context:
- We evaluate fixed PPO/SAC/DQN reinforcement-learning trading policies.
- We vary assets, timeframes, feature families, source families, seeds, splits, and cost scenarios.
- Stage A was broad screening and produced one surviving candidate:
  `ETHUSDT 4h SAC tech_stat seed 0`.
- The ledger mapping for that candidate is now resolved, but it remains blocked by:
  - `DSR_APPROXIMATE_INSUFFICIENT`
  - `PBO_DEFERRED`
- Stage B must compute rigorous statistical evidence from per-bar return traces.
- Stage C is a one-shot held-out firewall starting `2025-01-01`. It must not be inspected or used for tuning, thresholds, reports, or calibration before final locked evaluation.
- Synthetic Phase 4 may support training/pretraining experiments, but synthetic-only metrics are diagnostic and cannot provide tradability evidence.
- Do not propose changing PPO/SAC/DQN algorithms.

Known return trace schema from agent-multi:

```text
step,timestamp,asset,timeframe,split,episode_id,run_id,seed,bar_index,price,action_raw,position,reward,gross_return,net_return,equity,pnl,commission_paid,slippage_paid,trade_cost,trades
```

Known evidence index schema:
- `schema_version = project3_return_trace_evidence_v1`
- `trace_schema_version = stage_b_return_trace_v1`
- top-level: run_id, asset, timeframe, seed, config_hash, data_file_hash, feature_list_hash, heldout_boundary, contains_heldout_rows, stage_c_authorized, traces[]
- each trace entry has split, trace_file, trace_file_sha256, metadata_file, row_count, first_timestamp, last_timestamp, contains_heldout_rows, stage_c_authorized.

Your task:
Design the exact algorithms for `stageb_dsr_pbo_evaluator.py`.

Do not write generic advice. Produce implementation-grade math, pseudocode, thresholds, data requirements, and fail-closed rules.

Required output sections:

## 1. Evaluator Scope And Non-Scope
- Define what the evaluator computes.
- Define what it must refuse to compute.
- State that Stage C and synthetic-only validation are excluded.

## 2. Input Contract
Specify required input files:
- trace evidence index;
- return trace CSVs;
- run ledger;
- family manifest;
- matched baseline manifest;
- cost scenario manifest;
- split manifest.

For each, list minimum fields and hard validation rules.

## 3. Deflated Sharpe Ratio Algorithm
Provide:
- formula for Sharpe using per-bar `net_return`;
- annualization policy for 4h and 15m;
- skewness/kurtosis estimation;
- finite-sample DSR formula;
- expected max Sharpe calculation;
- how to handle non-normal returns;
- how to handle autocorrelation;
- `N_raw` policy;
- `N_eff` policy;
- fail-closed fallback when traces are unavailable or too short.

Include pseudocode that an engineer can translate directly.

## 4. PBO/CSCV Algorithm
Provide:
- exact split design for 4h and 15m returns;
- purge and embargo rules;
- how to construct combinations;
- in-sample vs out-of-sample ranking;
- logit rank statistic;
- PBO probability calculation;
- PBO-lite option when full retraining is not yet possible;
- minimum folds/paths and what to do if insufficient data.

## 5. White Reality Check Algorithm
Provide:
- null hypothesis;
- loss/performance differential definition versus baseline;
- stationary/block bootstrap method;
- studentized vs unstudentized recommendation;
- bootstrap repetitions;
- block length selection;
- p-value calculation;
- family grouping.

## 6. Hansen SPA Algorithm
Provide:
- null hypothesis;
- centered/truncated differential handling;
- studentization;
- stationary bootstrap;
- p-value calculation;
- when SPA should override raw winner claims.

## 7. RL Seed Uncertainty Algorithm
Provide:
- paired seed design;
- minimum seeds;
- IQM/median/trimmed mean;
- stratified bootstrap over seeds and folds;
- probability of improvement over matched baseline;
- performance profile data output.

## 8. Cost Fragility Algorithm
Provide:
- base vs pessimistic cost comparison;
- what to compute from commission/slippage/trade_cost columns;
- turnover stress;
- hard gates vs warning gates.

## 9. Family And Trial Accounting
Give exact accounting rules for:
- killed runs;
- failed runs;
- no-trade runs;
- reruns;
- seeds;
- algorithms;
- assets/timeframes;
- feature/source families;
- synthetic protocols;
- cost scenarios.

## 10. Output Schema
Design JSON/CSV/Markdown outputs for:
- per-run metrics;
- per-family tests;
- seed uncertainty;
- DSR/PBO results;
- promotion decision.

Include an example compact JSON.

## 11. Hard Gates And Warning Gates
Propose conservative defaults:
- DSR threshold;
- PBO threshold;
- Reality Check/SPA p-value threshold;
- minimum seeds;
- minimum trace length;
- base and pessimistic cost requirements;
- no Stage C contamination.

Clearly separate mathematical necessity from Project 3 engineering policy.

## 12. Pseudocode For Full Promotion Decision
Provide fail-closed pseudocode:
`load -> validate -> compute -> aggregate -> decide`.

## 13. Primary References
Use primary papers and stable technical sources:
- Deflated Sharpe Ratio;
- Probability of Backtest Overfitting / CSCV;
- White Reality Check;
- Hansen SPA;
- stationary bootstrap;
- empirical RL seed uncertainty/performance profiles.

Important:
- Do not suggest changing PPO/SAC/DQN.
- Do not suggest using Stage C for tuning or threshold choice.
- Do not suggest synthetic validation as tradability evidence.
- If a recommendation depends on unavailable artifacts, name the exact artifact.

Output:
Produce a Markdown memo with equations, tables, implementation defaults, and GitHub-issue checklist bullets.
```

## V3 Prompt For Codex — Integration Owner Verification After V3 Tasks

Use this for Codex after Claude/Copilot/5.5 Pro return.

```text
Act as Codex, the Project 3 integration owner. Verify the V3 outputs from Claude, Copilot, and ChatGPT 5.5 Pro. Do not assume any external-agent claim is correct.

Required sequence:
1. Check Dragon/Gamma/Omega worker status first.
2. Inspect git status in all touched repos:
   - financial-data
   - agent-multi
   - synthetic-datagen if mentioned
3. Review Claude's financial-data trace evidence ingestion:
   - inspect new loader/worker/tests;
   - run tests;
   - run CLI on generated test fixture or safe sample;
   - confirm fail-closed behavior for unauthorized heldout rows;
   - confirm existing Stage B approval remains blocked by DSR/PBO.
4. Review Copilot's agent-multi Stage B run-plan expander:
   - inspect generated configs and manifest;
   - run tests;
   - confirm every config remains locked;
   - confirm no training launched;
   - confirm Stage C access is denied.
5. Review ChatGPT 5.5 Pro evaluator algorithm memo:
   - extract implementable requirements;
   - reject overclaims;
   - update work-plan docs only if useful;
   - create the next implementation prompt for `stageb_dsr_pbo_evaluator.py`.
6. Patch only integration defects.
7. Do not launch Phase 4 training.
8. Do not touch Stage C.

Final response format:
- Worker status.
- Accepted outputs.
- Corrected or rejected outputs.
- Files changed by Codex.
- Tests run and exact results.
- Stage C/no-training confirmation.
- Remaining blockers.
- Next best task for each idle agent.
```

---

## Codex Integration Update — 2026-05-10 Stage B Execution Wiring

Status:
- Stage 3.1 Dragon/Gamma/Omega queues are drained: `project3_stage31_status_compare.py` reports `overall_ok: true` and `anomalies: []`.
- Stage B locked run plan exists with `90` configs, all currently `NOT_STARTED_LOCKED`.
- Stage C access remains `DENIED`; no Stage B or Phase 4 training was launched by Codex during this integration pass.

Defects corrected:
- Stage B locked configs now overwrite stale Stage A `training_progress_file` / `progress_file` paths.
- Every generated Stage B config now sets both top-level `progress_file` and `training_progress_file` to the manifest-owned Stage B path.
- Stage B status reader now accepts both `progress_pct` and agent-multi's `progress_percent` telemetry.
- agent-multi progress callback now emits `progress_pct`, `current_step`, `elapsed_seconds`, `equity`, and `no_trade_anomaly` in addition to existing trade/profit fields.

New execution infrastructure:
- `_scripts/workers/stage_b_locked_run_executor.py`
  - dry-run by default;
  - validates locked config contracts;
  - executes `agent-multi --load_config <locked_config>` directly when explicitly approved;
  - refuses Stage C flags;
  - monitors the Stage B progress file;
  - aborts if progress reaches `20%` with `trades_total <= 0`;
  - writes `stage_b_executor_state.json` / `.md`.

Validation results:
- `python -m pytest _scripts/tests/test_stage_b_locked_run_plan_worker.py -q` → `9 passed`
- `python -m pytest _scripts/tests/test_stage_b_locked_run_executor.py -q` → `7 passed`
- `python -m pytest _scripts/tests/test_stage_b_approval_gate_worker.py _scripts/tests/test_stage_b_locked_run_plan_worker.py -q` → `72 passed`
- `python -m pytest tests/unit/test_training_progress_callback.py -q` in `agent-multi` → `3 passed`
- `python -m pytest tests/unit/test_return_trace.py -q` in `agent-multi` → `22 passed`
- `python _scripts/workers/stage_b_locked_run_executor.py --limit 90` → dry-run `90 ready`, `0 blocked`, `training_launched: false`

Next executable step:
- Deliberate Stage B validation launch can now use:
  `python _scripts/workers/stage_b_locked_run_executor.py --execute --approval-token RUN_STAGE_B_VALIDATION --variant-id <variant_id>`
- For broad launch, distribute by `machine_hint` and keep the executor/status worker loop active so every job reports percent, trades, return, and no-trade anomaly state.
