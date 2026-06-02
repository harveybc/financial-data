# Project 3 Agent Handoff Spec Kit - 2026-05-12

This file exists to prevent vague agent handoffs. Every external agent prompt
below includes the exact repository, working directory, files to read first,
current artifact state, commands to run, forbidden actions, and acceptance
criteria.

Do not send an agent a shortened version unless the user explicitly asks for a
small summary. If an agent cannot access the named repo/path, it must stop and
report that exact blocker instead of guessing.

## Current Ground Truth

Date/time context:
- Current date: 2026-05-12.
- Local timezone in Codex session: America/Bogota.

Repositories:
- `financial-data`: `/home/harveybc/Documents/GitHub/financial-data`
- `agent-multi`: `/home/harveybc/Documents/GitHub/agent-multi`

Python:
- Financial-data command prefix:
  `/home/harveybc/anaconda3/envs/tensorflow/bin/python`
- Agent-multi command prefix:
  `/home/harveybc/anaconda3/envs/tensorflow/bin/python`
- Do not assume `python` is on PATH.

Project constraints:
- Stage C is a strict one-shot heldout firewall using rows at/after
  `2025-01-01`.
- Do not inspect, train on, tune on, or unlock Stage C.
- Do not launch training unless a prompt explicitly says to launch a specific
  Stage B run. The prompts below are implementation/review prompts only.
- Do not change PPO/SAC/DQN algorithms as a way to rescue results.
- Synthetic Phase 4 remains training-only and cannot provide tradability
  evidence.

Latest status from local artifacts:
- Stage B statistical report:
  `financial-data/experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json`
  - `evidence_files`: 50
  - `evidence_pass`: 50
  - `evidence_fail`: 0
  - `candidate_gate_pass`: 0
  - `candidate_gate_fail`: 22
  - `dsr_pass_n_raw`: 0
  - `dsr_fail_n_raw`: 50
  - `stage_c_allowed`: false
  - `stage_c_blocked_reason`:
    `NO_STAGE_B_CANDIDATE_PASSED_ALL_STATISTICAL_GATES`
- Stage B approval packet:
  `financial-data/experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json`
  - `total_candidates`: 4933
  - `n_stage_b_ready`: 0
  - status counts:
    - `KILL_NON_POSITIVE_RETURN`: 2761
    - `KILL_NO_TRADES`: 1154
    - `KILL_NEGATIVE_SHARPE`: 974
    - `BLOCKED_DSR_DEFERRED`: 19
    - `BLOCKED_MISSING_EVIDENCE`: 13
    - `BLOCKED_FAMILY_ABLATION`: 8
    - `BLOCKED_BASELINE_COMPARISON`: 4
- Stage B cluster status:
  `financial-data/experiments/stage_b_validation/run_plan/stage_b_cluster_live_status.json`
  - assigned: 90
  - done: 49
  - failed: 36
  - aborted_no_trade: 5
  - running: 0
  - not_started: 0
  - all machine queries OK: true

Files recently implemented by Codex in `financial-data`:
- `_scripts/workers/stageb_dsr_pbo_evaluator.py`
- `_scripts/workers/stage_b_approval_gate_worker.py`
- `_scripts/workers/stage_b_cluster_live_status_worker.py`
- `_scripts/tests/test_stageb_dsr_pbo_evaluator.py`
- `_scripts/tests/test_stage_b_approval_gate_worker.py`
- `experiments/stage_b_validation/hardening/RETURN_TRACE_CONTRACT.md`
- `experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json`
- `experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md`
- `experiments/stage_a_screening/stage_b_approval/`

Verification already run by Codex:
- In `financial-data`:
  `/home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests -q`
  -> `308 passed, 11 warnings`
- In `agent-multi`:
  `/home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q`
  -> `52 passed`
- In `agent-multi`:
  `/home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stageb_run_plan.py --reference-config examples/config/project3_ethusdt_4h_sac_train_val_test.json --output-dir /tmp/project3_stageb_run_plan_smoke --dry-run-validate-only --allow-missing-data`
  -> `training_launched=false`, `stage_c_access=DENIED`

## Prompt For Claude - Financial-Data Stage B Evaluator Review And Upgrade

Use this exact prompt for Claude inside VS Code with repo access.

```text
You are Claude acting as a senior quantitative engineering reviewer inside the
financial-data repo. You have repository access. Do not guess paths.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- Use /home/harveybc/anaconda3/envs/tensorflow/bin/python
- Do not assume "python" is on PATH.

Project rules:
- Stage C is locked. Do not inspect, train, tune, or evaluate any 2025-01-01+
  heldout data.
- Do not launch training.
- Do not modify PPO/SAC/DQN algorithms.
- Do not weaken fail-closed gates just to produce a PASS.

Read these files first, in this order:
1. work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md
2. work_plan/32_STAGE_3_2_RESULTS_SYNTHESIS.md
3. work_plan/PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md
4. experiments/stage_b_validation/hardening/RETURN_TRACE_CONTRACT.md
5. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md
6. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json
7. experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.md
8. experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json
9. _scripts/workers/stageb_dsr_pbo_evaluator.py
10. _scripts/workers/stage_b_approval_gate_worker.py
11. _scripts/tests/test_stageb_dsr_pbo_evaluator.py
12. _scripts/tests/test_stage_b_approval_gate_worker.py

Current state to verify, not assume:
- Stage B evidence files: 50
- Evidence pass/fail: 50/0
- Candidate statistical gates pass/fail: 0/22
- Stage B ready candidates: 0
- Stage C allowed: false
- Main current blockers include DSR_RIGOROUS_FAIL, PBO_DEFERRED_OR_FAIL,
  FAMILY_REALITY_CHECK_FAIL, SEED_UNCERTAINTY_BLOCKED,
  FINAL_ALWAYS_IN_MARKET_LOSING, FINAL_EXCESSIVE_TRADES_HARD, and
  MISSING_COST_SCENARIO.

Mission:
Review and harden the financial-data Stage B evidence/evaluator/approval path.
Your goal is not to make candidates pass. Your goal is to make the gate
correct, auditable, and hard to misuse.

Tasks:
1. Verify stageb_dsr_pbo_evaluator.py actually validates:
   - evidence schema project3_return_trace_evidence_v1;
   - trace schema stage_b_return_trace_v1;
   - heldout boundary equals 2025-01-01;
   - no unauthorized Stage C rows;
   - trace_file_sha256 matches trace bytes;
   - duplicate split labels rejected;
   - missing trace or metadata rejected.
2. Review the DSR implementation:
   - formula;
   - use of per-bar net returns;
   - skew/kurtosis handling;
   - N_raw from ledger/trial count;
   - N_eff logic;
   - behavior on insufficient/constant returns.
3. Review PBO/CSCV implementation:
   - current code says PBO-lite over contiguous folds;
   - identify precisely what remains missing for full purged/embargoed CSCV;
   - implement small improvements only if safe and testable without training.
4. Review White Reality Check / SPA-lite:
   - verify matched baseline mapping by asset/timeframe/algo/cost scenario;
   - verify bootstrap is deterministic and bounded;
   - do not make it computationally explosive.
5. Review seed uncertainty:
   - current fail-closed minimum seed policy;
   - make sure unpaired or underpowered seed groups cannot pass.
6. Review trade behavior gates:
   - no trades;
   - excessive trades hard limit;
   - always-in-market losing.
7. Review stage_b_approval_gate_worker.py integration:
   - when statistical report exists, it must consume it;
   - missing candidate gate must block;
   - DSR/PBO/family/seed/cost/trade blockers must appear in JSON/CSV/MD;
   - no candidate may become PASS_STAGE_B_READY unless every hard gate clears.
8. Add or improve tests only where coverage is missing.
9. Re-run evaluator and approval gate.

Allowed edits:
- _scripts/workers/stageb_dsr_pbo_evaluator.py
- _scripts/workers/stage_b_approval_gate_worker.py
- _scripts/tests/test_stageb_dsr_pbo_evaluator.py
- _scripts/tests/test_stage_b_approval_gate_worker.py
- generated Stage B evaluator/approval artifacts
- a short work_plan addendum only if needed

Do not edit:
- Stage C data/configs/results.
- Agent-multi repo.
- Existing raw data.
- PPO/SAC/DQN implementations.

Commands to run:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stageb_dsr_pbo_evaluator.py _scripts/tests/test_stage_b_approval_gate_worker.py -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests -q
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stageb_dsr_pbo_evaluator.py
4. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_approval_gate_worker.py

Acceptance criteria:
- Tests pass.
- Evaluator emits stage_c_allowed=false unless at least one candidate passes all hard gates.
- Approval packet reports PASS_STAGE_B_READY only if evaluator promotion_allowed=true and all non-stat gates pass.
- Missing/bad evidence remains promotion_allowed=false.
- Final response includes:
  - files changed;
  - commands run;
  - Stage B evaluator summary;
  - Stage B approval status counts;
  - exact remaining blockers;
  - explicit confirmation that no training launched and Stage C was not touched.
```

## Prompt For Copilot - Agent-Multi Stage B Evidence Contract And Run-Plan Readiness

Use this exact prompt for Copilot inside VS Code with repo access.

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi repo. You have repository access. Do not guess paths.

Repository:
- cd /home/harveybc/Documents/GitHub/agent-multi

Python:
- Use /home/harveybc/anaconda3/envs/tensorflow/bin/python
- Do not assume "python" is on PATH.

Related financial-data repo, read-only reference:
- /home/harveybc/Documents/GitHub/financial-data

Project rules:
- Stage C is locked. Do not inspect, train, tune, or evaluate any 2025-01-01+
  heldout data.
- Do not launch training.
- Do not unlock Phase 4 synthetic configs.
- Do not modify PPO/SAC/DQN algorithms.

Read these agent-multi files first:
1. pipeline_plugins/_return_trace.py
2. pipeline_plugins/rl_pipeline.py
3. pipeline_plugins/rl_pipeline_with_validation.py
4. tools/project3_stageb_run_plan.py
5. tools/project3_phase4_protocol_dry_run.py
6. tests/unit/test_return_trace.py
7. tests/unit/test_project3_stageb_run_plan.py, if present
8. examples/config/project3_ethusdt_4h_sac_train_val_test.json

Read these financial-data reference files, but do not edit them:
1. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/RETURN_TRACE_CONTRACT.md
2. /home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md
3. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md

Current contract that agent-multi must satisfy:
- evidence schema: project3_return_trace_evidence_v1
- trace schema: stage_b_return_trace_v1
- heldout boundary: 2025-01-01
- each Stage B run must emit traces/evidence.json
- evidence.json traces[] entries must include split, trace_file,
  trace_file_sha256, metadata_file, row_count, first_timestamp,
  last_timestamp, contains_heldout_rows, stage_c_authorized, episode_id.
- financial-data rejects unauthorized heldout rows, bad trace hashes, duplicate
  splits, missing trace files, missing metadata, unsupported schema versions.

Mission:
Make agent-multi's Stage B trace/evidence infrastructure explicit, validated,
and ready for future reruns without launching training.

Tasks:
1. Verify _return_trace.py writes:
   - fixed stage_b_return_trace_v1 column order;
   - .meta.json sidecars;
   - run-level evidence.json;
   - correct sha256 over trace bytes;
   - heldout boundary fields;
   - stage_c_authorized only when both final_stage_c_evaluation and
     stage_c_acknowledged are explicitly true.
2. Verify rl_pipeline.py and rl_pipeline_with_validation.py:
   - no behavior changes when return_trace_file/return_trace_dir is absent;
   - traces/evidence are written when configured;
   - train/validation/test split traces are discoverable.
3. Verify tools/project3_stageb_run_plan.py:
   - emits locked configs only;
   - stage_c_access DENIED;
   - _NOT_TO_RUN_UNTIL_STAGE_B_APPROVED true;
   - cost scenarios base and pessimistic;
   - seeds default to at least 5 unless smoke override is explicit;
   - return_trace_dir and expected_evidence_file are set.
4. Improve tests if any of the above is not covered.
5. Add a concise docs section or example if the evidence path contract is not
   obvious to financial-data.

Allowed edits:
- pipeline_plugins/_return_trace.py
- pipeline_plugins/rl_pipeline.py
- pipeline_plugins/rl_pipeline_with_validation.py
- tools/project3_stageb_run_plan.py
- tests/unit/*
- examples/config/* only for locked templates or docs examples
- README/docs only if needed

Forbidden:
- Do not launch training.
- Do not run seed_sweep except a dry-run/help/blocked-lock smoke.
- Do not alter model algorithms or reward logic.
- Do not touch Stage C.

Commands to run:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stageb_run_plan.py --reference-config examples/config/project3_ethusdt_4h_sac_train_val_test.json --output-dir /tmp/project3_stageb_run_plan_smoke --dry-run-validate-only --allow-missing-data
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_phase4_protocol_dry_run.py --help

Acceptance criteria:
- tests pass;
- dry-run confirms training_launched=false and stage_c_access=DENIED;
- evidence path contract is clear enough for financial-data to ingest;
- no training launched;
- no Stage C access.

Final response must include:
- files changed;
- tests/commands run;
- exact evidence schema/trace schema confirmation;
- sample evidence path contract;
- exact remaining gaps for full Stage B reruns.
```

## Prompt For ChatGPT 5.5 Pro Web - Research Memo Only

Use this for the web-only ChatGPT 5.5 Pro. It has no repo access, so include
the context below and attach only small docs.

Attachment guidance:
- Attach if possible:
  1. `financial-data/work_plan/PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md`
  2. `financial-data/work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md`
  3. `financial-data/experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md`
- If upload limits allow only one file, attach:
  `PROJECT3_STAGE_B_STATISTICAL_GOVERNANCE_REVIEW_REFINED.md`
- Do not attach huge JSON/CSV outputs.

```text
You are an external senior quant/RL research reviewer. You do not have repo
access. Treat this as a research memo, not code mutation.

Project 3 context:
- We evaluate fixed PPO/SAC/DQN reinforcement-learning trading policies.
- We vary assets, timeframes, feature families, source families, seeds, splits,
  and cost scenarios.
- Stage A was broad screening, not final evidence.
- Stage B is stricter validation using per-bar/per-step return traces.
- Stage C is a one-shot heldout firewall using rows at/after 2025-01-01.
  Stage C must not be used for tuning or repeated evaluation.
- Synthetic Phase 4 work is training-only; synthetic-only metrics are
  diagnostic and cannot prove tradability.
- Latest Stage B implementation state:
  - 50 evidence files validated;
  - 0 evidence failures;
  - 0/22 candidate statistical gates pass;
  - DSR pass/fail using N_raw: 0/50;
  - Stage C allowed: false;
  - current blockers include DSR_RIGOROUS_FAIL, PBO_DEFERRED_OR_FAIL,
    FAMILY_REALITY_CHECK_FAIL, SEED_UNCERTAINTY_BLOCKED,
    FINAL_ALWAYS_IN_MARKET_LOSING, FINAL_EXCESSIVE_TRADES_HARD,
    and MISSING_COST_SCENARIO.

Research task:
Produce an implementation-grade memo for the next Project 3 decisions. Be
skeptical and concrete.

Required sections:
1. Stage B statistical evaluator critique:
   - DSR/PSR formulas and edge cases;
   - N_raw vs N_eff policy;
   - autocorrelation/non-normality handling;
   - PBO/CSCV requirements for RL trading;
   - White Reality Check / Hansen SPA family tests;
   - seed uncertainty and paired bootstrap reporting;
   - trade behavior gates: no-trade, excessive-trade, always-in-market losing.
2. Feature/source research gap map:
   - crypto spot, crypto perps, FX, macro/on-chain/order-flow sources;
   - technical/statistical/decomposition/learned representation families;
   - PCA, autoencoder, VAE, contrastive encoders, CNN/LSTM/Transformer
     embeddings;
   - feature selection methods: redundancy, stability, MI, permutation/SHAP,
     regime-conditioned value.
3. Synthetic data research:
   - stationary/bootstrap methods;
   - regime residual bootstrap;
   - TimeGAN/COT-GAN;
   - TimeVAE/CVAE;
   - diffusion/score models;
   - how to keep synthetic data training-only and count every trial.
4. Concrete recommended next tasks:
   - what to implement now;
   - what to defer;
   - what would violate Stage C and must not be done.

Important:
- Prefer primary papers, official docs, or well-cited technical sources.
- Do not suggest changing PPO/SAC/DQN.
- Do not suggest Stage C tuning.
- Clearly separate mathematically required gates from engineering policy.
- If a recommendation depends on unavailable artifacts, state the exact
  artifact required.

Output:
- Markdown memo with links.
- Include a final checklist suitable for converting into GitHub issues.
```

## Codex Integration Checklist After External Agents Return

When Claude/Copilot/ChatGPT return, Codex must do the following locally:

1. Verify worker/machine status:
   ```bash
   cd /home/harveybc/Documents/GitHub/financial-data
   /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_cluster_live_status_worker.py
   ```
2. Review exact diffs. Do not trust summaries.
3. Re-run financial-data tests:
   ```bash
   /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests -q
   /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stageb_dsr_pbo_evaluator.py
   /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage_b_approval_gate_worker.py
   ```
4. Re-run agent-multi tests if Copilot changed that repo:
   ```bash
   cd /home/harveybc/Documents/GitHub/agent-multi
   /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q
   /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stageb_run_plan.py --reference-config examples/config/project3_ethusdt_4h_sac_train_val_test.json --output-dir /tmp/project3_stageb_run_plan_smoke --dry-run-validate-only --allow-missing-data
   ```
5. Confirm:
   - no training launched unless explicitly requested;
   - no Stage C access;
   - no candidate is PASS_STAGE_B_READY unless every hard gate cleared;
   - status output includes current task/progress/trades/return/anomaly deltas
     and exact next poll time.

