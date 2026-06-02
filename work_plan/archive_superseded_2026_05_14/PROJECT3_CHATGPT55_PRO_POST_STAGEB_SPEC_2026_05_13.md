# ChatGPT 5.5 Pro Web Handoff Spec: Project 3 Post-Stage-B Research Review

Generated: 2026-05-13

This is the exact prompt and attachment plan for ChatGPT 5.5 Pro Web. The web
model has no repository access, so attach the files listed below.

## Attachment Plan

### Minimum Attachments

If upload limits are tight, attach only these two files:

1. `financial-data/work_plan/PROJECT3_CHATGPT55_PRO_CONTEXT_PACKET_2026_05_13.md`
2. `financial-data/experiments/stage_b_validation/hardening/stage_b_decision_readiness.md`

### Recommended Attachments

Attach these for a useful review:

1. `financial-data/work_plan/PROJECT3_CHATGPT55_PRO_CONTEXT_PACKET_2026_05_13.md`
2. `financial-data/work_plan/PROJECT3_PRAGMATIC_NEXT_DECISION_SPEC_FOR_ORCHESTRATOR.md`
3. `financial-data/experiments/stage_b_validation/hardening/stage_b_decision_readiness.md`
4. `financial-data/experiments/stage_b_validation/hardening/stageb_no_pass_root_cause.md`
5. `financial-data/experiments/stage_b_validation/hardening/trade_behavior_report.md`
6. `financial-data/experiments/stage_b_validation/hardening/cost_fragility_report.md`
7. `financial-data/experiments/stage_b_validation/hardening/stage_b_post_pragmatic_finalization.md`
8. `financial-data/experiments/stage_b_validation/pragmatic_run_plan/stageb_pragmatic_run_plan_summary.md`

These are all small Markdown files and should fit comfortably.

### Optional Attachments

Only attach these if ChatGPT Pro can handle larger files and you want detailed
data-table analysis:

1. `financial-data/experiments/stage_b_validation/hardening/trade_behavior_report.csv`
2. `financial-data/experiments/stage_b_validation/hardening/cost_fragility_report.csv`

Do **not** attach these large JSON files unless specifically needed:

1. `financial-data/experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.json`
2. `financial-data/experiments/stage_a_screening/stage_b_approval/stage_b_approval_packet.json`

They are large and likely less useful than the compact context packet plus
Markdown summaries.

## Prompt To Paste Into ChatGPT 5.5 Pro

```text
You are an external senior quantitative trading, financial ML, and RL research
reviewer. You do not have repository access. Use only the prompt and attached
files. Treat this as a post-experiment research and decision memo, not a coding
task.

Project 3 context:
- We evaluate fixed PPO/SAC/DQN reinforcement-learning trading policies.
- We vary assets, timeframes, feature/source families, seeds, splits, and cost
  scenarios.
- Stage A was broad screening and is not final evidence.
- Stage B is stricter validation using per-bar/per-step return traces,
  matched baselines, seed checks, cost checks, and statistical gates.
- Stage C is a one-shot heldout firewall using rows at or after 2025-01-01.
  Stage C must not be used for tuning, repeated evaluation, prompt context, or
  diagnosis.
- Synthetic Phase 4 is training-only. Synthetic-only metrics are diagnostic and
  cannot prove tradability.
- Do not suggest changing PPO/SAC/DQN algorithms.

Latest Stage B result:
- 900/900 pragmatic configs completed.
- 950 total evidence files validated including legacy; 0 evidence failures.
- Candidate gates: 0 pass / 322 fail.
- DSR: 0 pass / 499 fail.
- Stage B ready candidates: 0.
- Stage C decision: BLOCK_STAGE_C.
- Main blockers include:
  - NON_POSITIVE_RETURN
  - NO_TRADES
  - NEGATIVE_SHARPE
  - DSR_RIGOROUS_FAIL
  - FAMILY_REALITY_CHECK_FAIL
  - SEED_UNCERTAINTY_BLOCKED
  - PBO_DEFERRED_OR_FAIL
  - FINAL_EXCESSIVE_TRADES_HARD
  - FINAL_NO_TRADES
  - FINAL_ALWAYS_IN_MARKET_LOSING

Important nuance:
- This does not prove RL cannot trade.
- It proves no current candidate is safe to send to Stage C.
- The next decision must separate bad economics, infrastructure/action/reward
  defects, feature-family weakness, missing evidence, and statistical
  non-significance.

Your task:
Produce a skeptical, implementation-grade memo for what Project 3 should do
next. Be concrete. Avoid generic praise. Give decisions and work items.

Required sections:

1. Executive recommendation
   - Should Stage C remain blocked?
   - Should Project 3 continue?
   - What is the next highest-value work?

2. Failure interpretation
   Analyze the meaning of:
   - no-trade failures;
   - excessive-trade failures;
   - always-in-market losing failures;
   - negative/non-positive return failures;
   - DSR/PBO/family/seed failures;
   - missing evidence/cost-scenario failures.

3. Infrastructure vs economics diagnosis
   Provide exact tests or checks to distinguish:
   - environment/action-mapping bug;
   - reward/cost-model pathology;
   - trace/accounting bug;
   - baseline design artifact;
   - genuinely bad strategy economics.

4. Trade behavior policy
   Propose practical hard/warning gates for:
   - minimum trades;
   - maximum trades/year;
   - exposure fraction;
   - always-in-market behavior;
   - cost fragility.
   Explain what should block Stage C versus what should only guide research.

5. Feature/source research plan
   Recommend what to test next for:
   - crypto spot;
   - crypto perps;
   - FX;
   - macro;
   - on-chain;
   - order-flow/microstructure.
   Include which sources/features are likely highest value and which are likely
   noise or leakage risks.

6. Feature engineering and representation plan
   Recommend concrete next experiments for:
   - technical/statistical features;
   - decomposition features;
   - regime/OOD features;
   - PCA;
   - autoencoders;
   - VAE/CVAE;
   - contrastive time-series encoders;
   - CNN/LSTM/Transformer embeddings.
   Separate proven near-term engineering from speculative research.

7. Synthetic data plan
   Evaluate whether synthetic data should be used next and how:
   - stationary/block bootstrap;
   - regime residual bootstrap;
   - TimeGAN/COT-GAN;
   - TimeVAE/CVAE;
   - diffusion/score methods.
   Keep synthetic data training-only and count every trial.

8. Statistical validation critique
   Critique the current gate stack:
   - DSR/PSR;
   - N_raw vs N_eff;
   - PBO/CSCV;
   - White Reality Check / Hansen SPA;
   - paired seed uncertainty;
   - baseline/family tests.
   State what is mathematically required versus what is engineering policy.

9. Recommended next run matrix
   Propose a small, counted, Stage-B-only diagnostic run matrix:
   - exact hypotheses;
   - assets/timeframes;
   - feature/source variants;
   - seeds;
   - costs;
   - baselines;
   - stop/kill rules.
   It must not use Stage C.

10. Kill / repair / rerun / defer table
   For each failure class, state:
   - kill now;
   - repair infrastructure first;
   - rerun targeted;
   - research-only;
   - defer.

11. GitHub issue checklist
   Convert recommendations into implementation-ready issues with:
   - title;
   - goal;
   - required artifacts;
   - acceptance criteria;
   - files/modules likely affected, if inferable from attached docs.

Rules:
- Do not suggest changing PPO/SAC/DQN algorithms.
- Do not suggest using Stage C for tuning or diagnosis.
- Do not suggest repeated Stage C evaluation.
- Do not use synthetic validation as tradability evidence.
- Prefer primary papers, official docs, or well-cited technical sources.
- If a recommendation depends on unavailable information, state the exact
  artifact needed.
- Be skeptical and concrete.

Output:
- Markdown memo.
- Include links/references.
- Include prioritized actions for Codex/Claude/Copilot after the memo.
```

