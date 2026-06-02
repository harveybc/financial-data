# Project 3 Post-No-Promotion Agent Specs

Generated: 2026-05-14

Context:

- Stage B execution completed successfully.
- Session-calendar diagnostic queue: `270/270` done, `0` failed.
- Full local evidence universe: `1220` evidence files, `1220` traces found,
  `0` evidence failures.
- Candidate statistical gates: `0/100` pass.
- DSR under `N_raw`: `0/633` pass.
- Stage C remains locked.
- Diagnostic ranking top candidate:
  `ethusdt_4h_sac_tech_stat_full_candidate`.
- Feature/action audit shows `12` distinct data hashes, but the top `11`
  `tech_stat` variants have identical action/trade/performance signatures.
- All top audited runs have missing `feature_list_hash` in evidence.

The next objective is not Stage C and not a broad GPU rerun. The next objective
is to determine why distinct feature inputs produce identical policy behavior,
then prepare a small counted diagnostic only if a concrete defect or missing
state variable is found.

## Copilot Agent Spec - agent-multi

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi repo.

Repository:
- cd /home/harveybc/Documents/GitHub/agent-multi

Rules:
- Do not launch training.
- Do not touch Stage C.
- Do not modify PPO/SAC/DQN algorithms.
- Do not weaken any lock or fail-closed behavior.

Read first:
1. docs/STAGE_B_EVIDENCE_CONTRACT.md
2. pipeline_plugins/_return_trace.py
3. pipeline_plugins/rl_pipeline.py
4. pipeline_plugins/rl_pipeline_with_validation.py
5. tests/unit/test_return_trace.py
6. tools/project3_stageb_run_plan.py

Financial-data findings to account for:
- Stage B evidence files currently have `feature_list_hash = null`.
- financial-data audit:
  `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_b_validation/hardening/stage_b_feature_action_audit.md`
- Top 11 distinct feature files produced identical action/trade/performance
  signatures, so we need better evidence that the agent actually sees the
  intended feature list and observation state.

Tasks:
1. Ensure every `project3_return_trace_evidence_v1` writes a non-null,
   deterministic `feature_list_hash`.
   - Hash the exact ordered feature list consumed by the model.
   - If the config does not explicitly contain the list, derive it from the
     resolved observation/feature columns used by the environment.
   - Fail closed if no feature list can be resolved for Stage B configs.
2. Add evidence fields, if not already present:
   - `feature_columns`
   - `feature_column_count`
   - `observation_state_fields`
   - `observation_state_hash`
3. Audit gym-fx / environment observation state for force-close context:
   - `bars_to_force_close`
   - `hours_to_force_close`
   - `is_force_close_zone`
   - `is_monday_entry_window`
   If absent, implement them as optional Stage B observation fields controlled
   by config. Do not change PPO/SAC/DQN algorithm code.
4. Add tests:
   - feature_list_hash is non-null and deterministic;
   - changing feature column order changes the hash;
   - missing feature list in a Stage B config fails closed;
   - observation state contains force-close fields when enabled;
   - Stage C flags still require explicit final-stage authorization.
5. Provide a dry-run config snippet showing how financial-data should enable
   the force-close observation fields.

Output:
- files changed;
- tests run;
- exact evidence fields added;
- confirmation no training launched and Stage C not touched.
```

## Claude Agent Spec - financial-data

```text
You are Claude acting as a senior quantitative engineering reviewer inside the
financial-data repo.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- /home/harveybc/anaconda3/envs/tensorflow/bin/python

Rules:
- Do not launch training.
- Do not touch Stage C.
- Do not weaken Stage B hard gates.

Read first:
1. experiments/stage_b_validation/hardening/stage_b_feature_action_audit.md
2. experiments/stage_b_validation/hardening/stage_b_diagnostic_candidate_ranking.md
3. experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json
4. work_plan/PROJECT3_DATA_CONTEXT_AND_PAID_SOURCE_GAP_SPEC_2026_05_13.md
5. _scripts/workers/stage_b_feature_action_audit_worker.py
6. _scripts/workers/stage_b_diagnostic_ranker_worker.py

Tasks:
1. Review the new feature/action audit worker for correctness.
2. Add tests for:
   - non-finite diagnostic scores are sanitized;
   - identical action/performance signatures across distinct data hashes are
     flagged;
   - missing `feature_list_hash` appears as a warning, not as a Stage C pass;
   - baseline/no-trade candidates cannot rise above trade-clean candidates.
3. Extend the audit if needed to compute:
   - per-candidate action entropy or rounded action diversity;
   - position flip rate;
   - forced-close-window exposure if timestamps allow;
   - whether session-calendar columns changed action behavior vs. the
     matching non-calendar variant.
4. Produce a final recommendation:
   - kill / repair / rerun / defer for each top ranked candidate family;
   - exact minimal next diagnostic matrix, if any.

Output:
- files changed;
- tests run;
- top findings;
- exact recommendation;
- confirmation no training launched and Stage C not touched.
```

## ChatGPT 5.5 Pro Web Spec

Attach only if possible:

1. `PROJECT3_DATA_CONTEXT_AND_PAID_SOURCE_GAP_SPEC_2026_05_13.md`
2. `stage_b_feature_action_audit.md`
3. `stage_b_diagnostic_candidate_ranking.md`
4. `stage_b_decision_readiness.md`

Prompt:

```text
You are an external senior quant/RL research reviewer. You do not have repo
access except the attached files.

Project 3 evaluates fixed PPO/SAC/DQN trading policies across data, feature,
asset, seed, split, and cost variants. Stage C is a one-shot heldout firewall
using rows at/after 2025-01-01 and must not be used for tuning.

Latest facts:
- Stage B execution completed successfully.
- Full evidence universe: 1220 evidence files, 0 evidence failures.
- Candidate statistical gates: 0/100 pass.
- DSR under N_raw: 0/633 pass.
- Stage C is locked.
- A diagnostic ranking exists, but no candidate is promotable.
- Feature/action audit shows 12 distinct data hashes among top candidates, but
  11 top tech_stat variants have identical action/trade/performance signatures.
- CSV session-calendar features were tested and did not produce a Stage B-ready
  candidate.
- CryptoQuant subscription was cancelled because full historical/API access
  would cost about USD 1000/month and current exported coverage is not enough
  for Stage B.

Task:
Produce an implementation-grade research memo answering:
1. Why distinct feature files might produce identical RL behavior.
2. What observation-state, reward, action-space, and environment diagnostics
   should be performed before another GPU matrix.
3. How to redesign feature/source families using free or already owned data.
4. How to test force-close / Friday-risk context without changing PPO/SAC/DQN.
5. What minimal next counted diagnostic matrix is justified.
6. What should be killed/deferred to avoid wasting GPU and money.

Rules:
- Do not suggest unlocking Stage C.
- Do not suggest changing PPO/SAC/DQN algorithms.
- Do not suggest paying for CryptoQuant unless you define a pre-payment proof
  requirement.
- Separate mathematical promotion gates from research triage metrics.

Output:
- Markdown memo;
- concrete next-step checklist;
- references if you cite methods.
```
