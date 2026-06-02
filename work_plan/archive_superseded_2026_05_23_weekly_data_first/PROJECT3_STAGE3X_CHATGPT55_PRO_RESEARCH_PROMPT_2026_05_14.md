# Project 3 Stage 3X ChatGPT 5.5 Pro Web Research Prompt

Use this prompt in ChatGPT 5.5 Pro Web if you want a parallel research review.

## Attachments

Attach these files, in priority order. If attachment limits are tight, attach
only the first six.

1. `financial-data/work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
2. `financial-data/work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md`
3. `financial-data/experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.md`
4. `financial-data/experiments/stage3x_target_relation_screen/selected_feature_contracts.json`
5. `financial-data/experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space_summary.md`
6. `financial-data/experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space.schema.json`
7. `financial-data/experiments/stage3x_absurdity_guard/stage3x_absurdity_guard_report.md`
8. `financial-data/experiments/stage_b_validation/hardening/stage_b_feature_action_audit.md`
9. `financial-data/experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.md`
10. `financial-data/work_plan/PROJECT3_CRYPTOQUANT_SUBSCRIPTION_DECISION_2026_05_13.md`

## Prompt

```text
You are an external senior quant/RL research reviewer. You do not have repo
access beyond the attached files.

Project 3 evaluates fixed PPO/SAC/DQN trading policies across assets,
timeframes, source families, feature families, seeds, costs, and splits. Stage C
is a one-shot heldout firewall using rows at/after 2025-01-01 and cannot be
used for tuning.

Current decision:
- No Stage B candidate is promotion-ready.
- Broad GPU work is blocked.
- Small SAC smoke planning is now allowed after CPU screening.
- The active branch is SAC-first actor-critic input optimization.
- DEAP/NSGA-II should optimize SAC only after feature/data/preprocessing
  contracts survive CPU screening.
- CryptoQuant is cancelled unless a pre-payment proof shows unique, useful
  historical coverage.

Current CPU screen:
- 54 genomes screened.
- 13 PASS_CPU_SCREEN.
- 12 selected feature contracts.
- The screen now blocks high-IC contracts when cost-aware proxy return is
  negative.

Research task:
Produce an implementation-grade memo reviewing:
1. Whether the CPU screen criteria are sufficient before SAC smoke testing.
2. Whether the selected contracts look like plausible next smoke candidates.
3. Additional cheap data/feature sanity checks before GPU:
   - rank IC variants;
   - mutual information;
   - regime-conditioned value;
   - turnover/cost sanity;
   - leakage guards;
   - feature redundancy/stability.
4. Safe SAC hyperparameter search ranges for DEAP/NSGA-II after smoke passes.
5. Multi-objective objectives and constraints for the first DEAP population.
6. What should still be killed/deferred to avoid wasting GPU or paid data money.

Rules:
- Do not suggest unlocking Stage C.
- Do not suggest changing PPO/SAC/DQN algorithm implementations.
- Do not suggest broad GPU reruns before SAC smoke passes.
- Clearly separate proven recommendations from speculative research.
- Prefer primary papers, official docs, or well-cited technical sources.

Output:
- Markdown memo;
- concrete checklist suitable for GitHub issues;
- links to references.
```
