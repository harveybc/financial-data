# Project 3 Idle-Agent Prompt Kit - 2026-05-04

This file contains paste-ready prompts for the currently idle external agents:

- Claude: careful code, governance, tests, fail-closed validators.
- Copilot: fast implementation inside `agent-multi`, config scaffolding, dry-run tools.
- ChatGPT 5.5 Pro: deep research, statistical design, citations, implementation guidance.

The prompts are intentionally separated by repository ownership so agents do not duplicate work or overwrite each other.

---

## Common Operating Rules For All Agents

Use these rules in every prompt unless the task says otherwise.

```text
You are working on Harvey's Project 3 RL trading research stack.

Critical project constraints:

1. Do not launch any new training unless the prompt explicitly asks for a training run.
2. Do not access, inspect, tune on, or use Stage C / 2025-01-01+ held-out data for training, fitting, generator selection, feature selection, or validation.
3. Treat synthetic data as training/pretraining infrastructure only. Synthetic-only performance is diagnostic, not evidence of tradability.
4. Keep PPO/SAC/DQN algorithms fixed unless explicitly asked otherwise.
5. Preserve Stage A/B/C governance: immutable ledger, leakage audit, simple baselines, family ablation, cost gates, DSR/PBO/multiple-testing accounting, and Stage C firewall.
6. Make validators fail closed: missing evidence means BLOCKED, not PASS.
7. Do not silently relax thresholds.
8. Do not hide failed, blocked, killed, or diagnostic runs.
9. Add tests for every new gate, parser, lock, or protocol check.
10. Do not commit or push unless Harvey explicitly requests it in that agent session. If you do commit, make one focused commit and report the exact commit SHA.

Output requirements:

- List files changed.
- List commands run and exact pass/fail results.
- State whether any training was launched. The expected answer is normally "No training launched."
- State any remaining blockers.
- If blocked, give the exact missing file, schema field, command, or decision needed.
```

---

# Prompt 1 - Claude

## Task: Stage B Approval Gate Validator In `financial-data`

Paste this to Claude.

```text
Act as a senior software engineer, ML experiment-governance specialist, and skeptical quant-research auditor. You are excellent at precise Python, fail-closed validators, test scaffolds, and careful evidence accounting.

Repository:

  /home/harveybc/Documents/GitHub/financial-data

Objective:

Implement a Stage B approval-gate validator for Project 3. This validator must read the existing Stage A governance artifacts and emit a machine-readable and human-readable Stage B approval packet. It must not launch training. It must not inspect or use Stage C / 2025-01-01+ data except to verify the held-out firewall.

Current Project 3 context:

- Stage A screening is in progress across Dragon/Gamma/Omega.
- Fixed RL algorithms are PPO, SAC, and DQN.
- Current best candidate has been ETHUSDT 4h SAC tech_stat, but this task must be generic over all candidates.
- Stage A hardening artifacts already exist under:
  - experiments/stage_a_screening/hardening/promotion_candidates.csv
  - experiments/stage_a_screening/hardening/promotion_hardening_report.json
  - experiments/stage_a_screening/hardening/leakage_heldout_audit_report.json
  - experiments/stage_a_screening/hardening/simple_baseline_report.json
  - experiments/stage_a_screening/hardening/family_ablation_report.json
  - artifacts/run_ledger.jsonl
  - artifacts/run_ledger.parquet if available
  - artifacts/run_ledger_summary.json if available
- The design gate lives at:
  - experiments/design/stage_b_promotion_gate.yaml

Deliverable:

Create a self-contained worker:

  _scripts/workers/stage_b_approval_gate_worker.py

It must generate:

  experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json
  experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.md
  experiments/stage_a_screening/stage_b_approval/stage_b_approval_candidates.csv
  experiments/stage_a_screening/stage_b_approval/TASKS.md

Required gate statuses:

Each candidate must be classified as exactly one of:

- PASS_STAGE_B_READY
- FAIL_ECONOMIC_OR_STATISTICAL
- BLOCKED_MISSING_EVIDENCE
- BLOCKED_LEDGER_ABSENT
- BLOCKED_LEAKAGE_AUDIT
- BLOCKED_HELDOUT_FIREWALL
- BLOCKED_BASELINE_COMPARISON
- BLOCKED_FAMILY_ABLATION
- BLOCKED_DSR_DEFERRED
- BLOCKED_PBO_DEFERRED
- KILL_NO_TRADES
- KILL_NEGATIVE_SHARPE
- KILL_NON_POSITIVE_RETURN

Do not invent evidence. If a required artifact is absent, malformed, missing a candidate row, or lacks required fields, classify the candidate as BLOCKED_MISSING_EVIDENCE with exact details.

Required checks:

1. Ledger membership
   - Candidate run id or run slug must map to the immutable ledger.
   - Failed/killed/blocked candidates must remain visible.
   - If ledger cannot be loaded, do not pass anything.

2. Hardening status
   - Respect kill checks from promotion_hardening_report and promotion_candidates.
   - Do not override hardening kills.

3. Leakage and held-out firewall
   - Use leakage_heldout_audit_report.json when present.
   - PASS is allowed only if the candidate has explicit heldout/firewall evidence or an auditable "not applicable" path.
   - Missing input CSV must remain BLOCKED unless source-level evidence exists.
   - Any evidence of DATE_TIME >= 2025-01-01 in train/fitted inputs is fatal.

4. Simple baselines
   - Use simple_baseline_report.json.
   - Candidate must beat the strongest simple baseline under base cost and pessimistic cost if those fields exist.
   - Missing baseline evidence is BLOCKED_BASELINE_COMPARISON.

5. Family ablation
   - Use family_ablation_report.json.
   - Candidate must have source/feature-family marginal evidence or an explicit "not enough matched variants yet" block.
   - Missing ablation evidence is BLOCKED_FAMILY_ABLATION.

6. Stage B deferred statistical checks
   - Rigorous DSR and PBO may still be deferred if Stage A lacks per-bar returns or split structure.
   - The packet must state clearly whether DSR/PBO are "Stage A approximate", "Stage B required", or "missing".
   - Do not mark a candidate fully PASS_STAGE_B_READY if the gate policy requires rigorous DSR/PBO before Stage B. Instead use a blocked status with exact next action.

7. Economic checks
   - Require positive net result under base cost.
   - Require pessimistic-cost result not catastrophic.
   - Require trade count > 0.
   - Require seed dispersion to be reported when seeds exist.

8. Explainability of blockers
   - Every blocked candidate must include:
     - blocker_code
     - blocker_message
     - evidence_file
     - candidate_id
     - next_required_artifact_or_action

Implementation requirements:

- Use Python stdlib plus pandas if already used by existing workers.
- Prefer reading JSON/CSV robustly and failing closed on parse errors.
- Do not require network.
- Do not mutate existing hardening artifacts.
- Do not launch agent-multi.
- Do not run any GPU job.
- Add deterministic output ordering.
- Include generated_at timestamp.
- Include schema_version.
- Include project3_heldout_start = "2025-01-01".

Testing requirements:

Add tests under one of the existing test locations, choosing the local pattern after inspection. Suggested file:

  _scripts/tests/test_stage_b_approval_gate_worker.py

Tests must cover:

1. Missing ledger blocks all candidates.
2. Missing simple baseline blocks a candidate.
3. Missing family ablation blocks a candidate.
4. Held-out leakage is fatal.
5. KILL_NO_TRADES remains killed.
6. Positive candidate with all mocked evidence can pass or reaches the expected DSR/PBO deferred block depending on the gate policy.
7. Output JSON has stable schema keys.
8. Markdown report includes top candidates and blocker summary.

Suggested command sequence:

  cd /home/harveybc/Documents/GitHub/financial-data
  python _scripts/workers/stage_b_approval_gate_worker.py
  python -m pytest _scripts/tests/test_stage_b_approval_gate_worker.py -q

Final response format:

1. Files changed.
2. Commands run and results.
3. Candidate counts by final status.
4. Whether any candidate is actually Stage B ready.
5. Remaining blockers and exact next action.
6. Confirm: "No training launched. Stage C not touched."
```

---

# Prompt 2 - Copilot

## Task: Agent-Multi Phase 4 Dry-Run Comparator Scaffold

Paste this to Copilot.

```text
Act as a senior Python engineer and ML platform engineer working inside an existing plugin-oriented trading simulation repo. You are fast, practical, and careful about preserving existing behavior. Your job is to implement a dry-run comparator scaffold for Project 3 Phase 4 synthetic pretraining. This is configuration and validation infrastructure only. Do not launch training.

Repository:

  /home/harveybc/Documents/GitHub/agent-multi

Related repos and artifacts to inspect, read-only:

  /home/harveybc/Documents/GitHub/financial-data/work_plan/PHASE4_SYNTHETIC_PRETRAINING_PROTOCOL_ORCHESTRATOR.md
  /home/harveybc/Documents/GitHub/synthetic-datagen/experiments/synthetic_data/project3_eth_4h/regime_residual_bootstrap/regime_residual_bootstrap_v1_anti_mem_protocol.json
  /home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/runs/dragon/ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave/config.json

Current known issue to preserve:

There is already a Phase 4 synthetic config template:

  examples/config/project3_ethusdt_4h_sac_synth_anti_mem_v1.json

It must remain locked by default. Do not remove the protocol lock. Do not run it.

Objective:

Build a dry-run comparator scaffold that creates and validates the four mandatory Project 3 Phase 4 arms without launching agent-multi training:

Arm A:
  real_only_standard

Arm B:
  real_only_compute_matched

Arm C:
  synthetic_only_diagnostic

Arm D:
  synthetic_pretrain_then_real_finetune

Primary comparison:

  Arm D vs Arm B

The scaffold must prove that Arms A/B/C/D share identical candidate identity, asset, timeframe, feature preset, SAC model family, reward mechanics, action space, split boundaries, costs, seeds, and Stage C firewall, except for the explicitly declared training protocol differences.

Strict constraints:

1. Do not launch training.
2. Do not remove or weaken the existing Stage B protocol lock.
3. Do not inspect or use Stage C rows except to validate boundary metadata.
4. Do not change SAC hyperparameters unless the arm definition explicitly requires compute matching through training budget only.
5. Do not introduce a new actor-critic plugin for this comparison. Use the same SAC agent family as the Stage A reference.
6. Synthetic-only Arm C is diagnostic only and must be labeled non-promotion-eligible.
7. Any mismatch between locked packet, config arms, and Stage A reference must fail closed.

Recommended implementation:

Create a CLI tool, adapting to existing repo style after inspection:

  tools/project3_phase4_protocol_dry_run.py

Supported command:

  python tools/project3_phase4_protocol_dry_run.py \
    --reference-config /home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/runs/dragon/ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_20260502T051413Z_project3_stage31_firstwave/config.json \
    --protocol-packet /home/harveybc/Documents/GitHub/synthetic-datagen/experiments/synthetic_data/project3_eth_4h/regime_residual_bootstrap/regime_residual_bootstrap_v1_anti_mem_protocol.json \
    --out-dir examples/config/project3_phase4_ethusdt_4h_sac_arms \
    --seeds 0,1,2 \
    --dry-run-validate-protocol

Expected outputs:

  examples/config/project3_phase4_ethusdt_4h_sac_arms/arm_a_real_only_standard.json
  examples/config/project3_phase4_ethusdt_4h_sac_arms/arm_b_real_only_compute_matched.json
  examples/config/project3_phase4_ethusdt_4h_sac_arms/arm_c_synthetic_only_diagnostic.json
  examples/config/project3_phase4_ethusdt_4h_sac_arms/arm_d_synthetic_pretrain_then_real_finetune.json
  examples/config/project3_phase4_ethusdt_4h_sac_arms/phase4_compare_manifest.json
  examples/config/project3_phase4_ethusdt_4h_sac_arms/phase4_compare_manifest.md

Required manifest fields:

- schema_version
- generated_at
- stage_b_status_required
- project3_heldout_start
- stage_c_access
- reference_config_path
- protocol_packet_path
- protocol_packet_hash
- reference_config_hash
- arms
- primary_comparison
- promotion_eligible_arms
- non_promotion_eligible_arms
- required_equal_fields
- allowed_different_fields
- seeds
- cost_scenarios
- dry_run_only
- training_launched = false

Validation requirements:

The dry-run validator must fail if:

1. Protocol packet project3_valid_for_training is not true.
2. Protocol packet stage_b_status is not PENDING_APPROVAL or APPROVED. PENDING_APPROVAL must keep all configs locked.
3. Any generated config lacks `_protocol_lock`.
4. Any generated config is runnable by seed_sweep without explicit override before Stage B approval.
5. Arm A/B/C/D model/plugin/reward/action/cost/split fields differ outside allowed fields.
6. Arm D changes SAC hyperparameters relative to the reference.
7. Arm C is marked promotion eligible.
8. Any config references a synthetic dataset for validation or test.
9. Any config or manifest references Stage C / 2025-01-01+ as train, pretrain, finetune, validation, or generator-fit input.

Config design:

- Arm A: same as reference standard real-only.
- Arm B: same as reference but with compute-matched total training budget to Arm D. Declare the compute-match logic in metadata.
- Arm C: synthetic-only diagnostic. It must be locked, non-promotion-eligible, and not runnable by default.
- Arm D: synthetic pretraining followed by real-data finetuning. It must be locked until Stage B approval.

Important:

If the repo cannot actually execute multi-phase pretrain/finetune yet, do not fake it as runnable. Emit locked templates plus a clear TODO field:

  "execution_status": "TEMPLATE_ONLY_MULTI_PHASE_RUNNER_NOT_IMPLEMENTED"

Tests:

Add unit tests, selecting existing style after inspection. Suggested:

  tests/unit/test_project3_phase4_protocol_dry_run.py

Tests must cover:

1. Generates all four arm configs and manifest.
2. Dry-run validation passes on a minimal fixture.
3. Dry-run validation fails if protocol packet has project3_valid_for_training=false.
4. Dry-run validation fails if Arm D changes SAC hyperparameters.
5. Dry-run validation fails if Arm C is promotion eligible.
6. Dry-run validation fails if validation/test paths contain synthetic data.
7. Generated configs remain blocked by the seed_sweep protocol lock.

Run:

  cd /home/harveybc/Documents/GitHub/agent-multi
  python tools/project3_phase4_protocol_dry_run.py --help
  python tools/project3_phase4_protocol_dry_run.py ... --dry-run-validate-protocol
  python -m pytest tests/unit/test_project3_phase4_protocol_dry_run.py -q

Final response format:

1. Files changed.
2. Commands run and results.
3. Exact generated arm config paths.
4. Manifest summary.
5. Confirm: "No training launched. Configs remain locked."
6. Remaining implementation gaps, especially if multi-phase execution is template-only.
```

---

# Prompt 3 - ChatGPT 5.5 Pro

## Task: Research Memo For Rigorous DSR/PBO/SPA In RL Trading Evaluation

Paste this to ChatGPT 5.5 Pro.

```text
Act as a senior quantitative finance researcher, empirical deep-RL evaluation expert, and statistical backtesting-governance auditor. Use current research and primary sources where possible. Be skeptical, concrete, and implementation-oriented.

I am working on Project 3, an RL trading research pipeline with fixed PPO/SAC/DQN algorithms. The project evaluates whether data and feature families improve performance. Stage A is broad screening. Stage B is stricter validation. Stage C is a strict one-shot real held-out period starting at 2025-01-01. Stage C must not be touched during research, tuning, feature selection, synthetic generation, or validation.

Current Project 3 context:

- Fixed algorithms: PPO, SAC, DQN.
- Assets include crypto and FX.
- Timeframes include 15m, 1h, 4h.
- Current promising candidate: ETHUSDT 4h SAC tech_stat.
- Stage A hardening already includes:
  - immutable ledger
  - simple baselines
  - leakage/heldout audit
  - family ablation
  - promotion hardening
  - cost proxies
- Remaining statistical governance needs:
  - rigorous Deflated Sharpe Ratio from per-bar/per-step returns
  - PBO/CSCV design for time-series RL
  - White Reality Check or Hansen SPA-style family tests
  - paired seed-level and asset/timeframe-level uncertainty
  - multiple-testing accounting across assets, timeframes, seeds, algorithms, feature families, source families, synthetic generator variants, and training protocol variants

Important constraints:

1. Do not propose changing PPO/SAC/DQN.
2. Do not propose using Stage C before final locked evaluation.
3. Do not treat synthetic data as evaluation evidence.
4. Do not rely on one lucky seed.
5. Do not recommend leaderboard-only promotion.
6. Assume returns have autocorrelation, volatility clustering, skew, kurtosis, and non-normal tails.
7. Assume trials are not independent.
8. The output must be implementable in Python by an engineering agent.

Research task:

Produce a rigorous but practical memo titled:

  "Project 3 Stage B Statistical Governance: DSR, PBO/CSCV, Reality Check, SPA, and RL Seed Uncertainty"

Required sections:

1. Executive summary
   - What must be implemented before trusting Stage B.
   - What can remain approximate in Stage A.
   - What must be forbidden.

2. Deflated Sharpe Ratio implementation
   - Explain the exact inputs needed.
   - Explain how to compute Sharpe from per-bar or per-step returns.
   - Explain annualization for:
     - 4h crypto bars
     - 1h bars
     - 15m bars
     - FX sessions if not 24/7
   - Explain how to handle skewness and kurtosis.
   - Explain how to set or estimate number of trials.
   - Explain effective number of trials when trials are correlated.
   - Explain how DSR should be interpreted for RL policies.
   - Provide Python-like pseudocode.
   - Provide acceptance criteria for Project 3 Stage B.

3. PBO/CSCV implementation for time-series RL
   - Explain why naive random k-fold is not acceptable.
   - Recommend a purged or contiguous combinatorially symmetric cross-validation design.
   - Explain how many folds/splits are realistic for 4h ETHUSDT and shorter 15m data.
   - Explain how to preserve temporal order and avoid leakage.
   - Explain how to compute PBO from rank degradation.
   - Explain how to handle multiple seeds and algorithms.
   - Provide Python-like pseudocode.
   - Provide acceptance criteria and failure interpretations.

4. White Reality Check and Hansen SPA-style family tests
   - Explain when to use them.
   - Explain null hypotheses in Project 3 language.
   - Explain block bootstrap or stationary bootstrap choices for dependent returns.
   - Explain how to group alternatives:
     - feature family
     - source family
     - synthetic generator family
     - training protocol family
   - Explain how to compare each alternative against a matched baseline.
   - Provide Python-like pseudocode.
   - Provide how to report p-values without overclaiming.

5. RL seed uncertainty
   - Recommend minimum and preferred seed counts.
   - Recommend paired seed tests.
   - Recommend median, IQM, bootstrap confidence intervals, performance profiles, probability of improvement.
   - Explain how to handle a candidate where seed 0 is strong but seeds 1 and 2 are weak.
   - Provide report-table templates.

6. Multiple-testing ledger
   - Define exactly what counts as a trial.
   - Include assets, timeframes, algorithms, seeds, feature presets, source families, cost scenarios, reward/action changes, synthetic generator families, augmentation ratios, pretraining schedules.
   - Explain how killed, failed, blocked, and diagnostic runs enter the accounting.
   - Recommend a conservative and a practical effective-trial-count method.

7. Stage B evaluator architecture
   - Proposed files/modules for a Python implementation.
   - Required input schemas:
     - run ledger
     - per-run returns
     - per-run trades
     - cost scenario outputs
     - candidate metadata
   - Required output schemas:
     - statistical_governance_report.json
     - statistical_governance_report.md
     - per_candidate_metrics.csv
     - family_test_results.csv
   - Fail-closed rules.

8. Concrete Project 3 go/no-go rules
   - Minimum rule set for Stage B promotion.
   - What blocks promotion.
   - What warnings are acceptable but must be disclosed.
   - What requires more seeds or more data.

9. References
   - Cite primary papers or authoritative sources for:
     - Deflated Sharpe Ratio
     - Probabilistic Sharpe Ratio if used
     - PBO / CSCV
     - White Reality Check
     - Hansen SPA
     - stationary/block bootstrap
     - deep RL empirical uncertainty and seed fragility
   - Include links.
   - Do not paste long copyrighted excerpts.

Style requirements:

- Be honest about limitations.
- Prefer implementation detail over broad theory.
- Clearly distinguish required, recommended, and optional.
- Clearly mark assumptions.
- Give enough pseudocode that a coding agent can implement the evaluator without guessing the statistics.
- Include a final checklist that can be pasted into a GitHub issue or work-plan doc.
```

---

# Optional Prompt 4 - Codex Integration Pass

Use this when Claude, Copilot, and ChatGPT 5.5 Pro finish.

```text
Act as Codex, the integration owner for Project 3. Review the outputs from Claude, Copilot, and ChatGPT 5.5 Pro. Do not assume they are correct. Verify files, tests, and runtime safety locally.

Tasks:

1. Check Dragon/Gamma/Omega worker status before editing.
2. Review Claude's Stage B approval gate worker:
   - inspect changed files
   - run tests
   - run the worker
   - verify outputs fail closed
3. Review Copilot's agent-multi dry-run comparator:
   - inspect changed files
   - run tests
   - run dry-run validation
   - confirm no training launched
   - confirm configs remain locked
4. Read ChatGPT 5.5 Pro's statistical-governance memo:
   - extract implementable requirements
   - identify any overclaims or risky assumptions
   - turn accepted parts into a work-plan addendum or implementation prompt
5. Patch only integration defects.
6. Do not touch Stage C.
7. Do not launch Phase 4 training.

Final output:

- worker status
- accepted outputs
- rejected or corrected outputs
- files changed by Codex
- tests run
- remaining blockers
```

