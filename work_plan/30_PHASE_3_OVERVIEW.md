# Phase 3 Overview — Systematic Experiments

**Phase goal:** Use Project 2's best RL agents (PPO, SAC, DQN configurations) to systematically evaluate which combinations of (trading asset, simulation timeframe, feature input set, feature engineering technique) produce the best RL trading policies on held-out data.

**Phase output:** Evidence-based ranking of data sources and feature techniques. `PROJECT_3_FINAL_REPORT.md` answers: which data combinations actually improve RL trading agent performance?

---

<!-- AGENT_INFRA_NOTE_v2 -->
## Agent Infrastructure Note

This stage is executed by the multi-tier agent system defined in `01_AGENT_INFRASTRUCTURE.md` (architecture v2). Read that document before executing this stage. Key rules:

- **Tier 2 (OpenCode Go on Omega) dispatches** the per-machine tasks listed below; you (the user) do not run them by hand.
- **Tier 1 supervisors** (Hermes + Gemma 3 31B on Dragon and Gamma, cron-invoked, GPU-lockfile-aware) watch worker logs and produce status reports.
- **Heavy GPU jobs MUST acquire `/tmp/gpu_busy.lock`** via `_scripts/lib/gpu_lock.py` before starting. See infrastructure doc §4.
- **Auto-validation is full auto** (master plan Rule M.15). When you confirm a manual prerequisite is done, the agents proceed through validation, deliverable generation, and downstream prep automatically. Only blockers ping you.
- **Escalation routing (v2 simplified — no automated frontier API):**
  - Code/data anomalies, scope ≤2 files, severity ≤ high → Tier 3 (local Hermes + Gemma 31B, bounded: max 3 attempts, max 2 files, 30 min/attempt). If Tier 3 confidence <0.7 or attempts exhausted → hands off to Tier 4.
  - Plan decisions, synthesis, final-report writing, blocker severity, or scope >2 files → Tier 4 (you, with ChatGPT 5.5 Pro via Codex / Copilot Opus 4.7 / Claude Pro Max as your tools).
  - **No automated frontier API calls anywhere.** Frontier models are human-driven only.

The "machine assignment" tables below describe which machine runs which workers. The dispatcher (Tier 2) handles SSH, conda activation, and result collection.
---

## 1. Project 3 vs Project 2 — What Changes

Project 2 evaluated: "Can RL find tradeable signal in BTC/ETH 1h with 12 technical features?"

Project 3 evaluates: "With comprehensive data and state-of-the-art features, which combinations of (asset, timeframe, feature set) yield best RL policies?"

The RL algorithm itself (PPO, SAC, DQN) is held FIXED at Project 2's best-performing configuration. Project 3 varies inputs, not algorithms.

---

## 2. Conceptual Distinction Reminder

Per master plan §2: each experiment specifies:

1. **Trading asset** — single asset whose price is traded (drives env step mechanics, P&L, episode boundaries)
2. **Simulation timeframe** — bar interval at which env steps (5m, 15m, 1h, or 4h)
3. **Feature input set** — which sources contribute to observation space
   - May include trading asset's own technical/statistical/decomposition/learned features
   - May include cross-source forward-filled features
4. **Feature engineering technique selection** — which Stage 2.2/2.3/2.4 outputs are used

These are 4 independent variables. Phase 3 systematically explores combinations.

---

## 3. Phase 3 Stages

| Stage | Document | Purpose |
|-------|----------|---------|
| 3.1 | `31_STAGE_3.1_EXPERIMENT_FRAMEWORK.md` | Define experimental design, execute experiments |
| 3.2 | `32_STAGE_3.2_RESULTS_SYNTHESIS.md` | Aggregate findings, produce final report |

---

## 4. Phase 3 Standing Rules

### Rule P3.1: Use Project 2 best configurations

For RL algorithms (PPO, SAC, DQN), use the best-performing hyperparameter configurations identified in Project 2 (Part II-7 pilots + post-pilot tuning). Document exact configs in Stage 3.1.

DO NOT redo Project 2's hyperparameter optimization. Phase 3 isolates the effect of data/features, not algorithm tuning.

### Rule P3.2: Held-out discipline strict

Per Rule M.3: 2025-01-01 onward is held-out. Each final candidate evaluated ONCE on held-out. NO re-running on held-out after seeing results.

### Rule P3.3: Pre-register experimental design

Before running any experiments, Stage 3.1 produces a pre-registered experimental design specifying:
- Total number of experiments
- Hypotheses being tested
- Kill criteria (when to abandon a configuration)
- Multiple-testing correction (Deflated Sharpe Ratio per Lopez de Prado)

This protects against post-hoc cherry-picking.

### Rule P3.4: Sample efficiency in experimentation

With ~10+ trading assets × 4 timeframes × multiple feature combinations × 3 seeds, the combinatorial space is enormous. Use staged screening:

- **Stage A (screening):** Quick low-budget runs (small total_timesteps) on broad coverage to identify promising configurations
- **Stage B (validation):** Full-budget runs (high total_timesteps) on top configurations from Stage A
- **Stage C (held-out):** Single deterministic rollout on 2025 data per validated candidate

### Rule P3.5: Cancel mediocre subscriptions per Rule M.10

After Phase 3 experiments complete, evaluate each paid subscription's contribution. If a subscription's data showed no marginal improvement vs free data alone, flag for cancellation.

This is the final test of the Rule M.10 mediocrity rejection criterion.

---

## 5. Phase 3 Output Structure

```
/home/harveybc/Documents/GitHub/financial-data/experiments/
├── README.md
├── design/
│   ├── pre_registered_design.md
│   ├── kill_criteria.md
│   └── multiple_testing_correction.md
├── stage_a_screening/
│   ├── runs/
│   │   └── <run_id>/...
│   └── stage_a_summary.md
├── stage_b_validation/
│   ├── runs/
│   │   └── <run_id>/...
│   └── stage_b_summary.md
├── stage_c_held_out/
│   ├── runs/
│   │   └── <run_id>/...
│   └── stage_c_results.md
└── synthesis/
    ├── PROJECT_3_FINAL_REPORT.md
    ├── data_source_value_ranking.md
    ├── feature_technique_value_ranking.md
    └── subscription_cancellation_recommendations.md
```

---

## 6. Phase 3 User Gates

- After 3.1 design: User approves experimental design before any runs
- After Stage A screening: User reviews top configurations, approves Stage B
- After Stage B validation: User reviews validated configs, approves held-out test
- After Stage C: User reviews held-out results, approves final report

This 4-gate structure ensures user retains control of experimental scope and prevents runaway compute spend.

---

## 7. Approval to Begin Phase 3

User approves Phase 3 overview after Phase 2 completion. Agent reads `31_STAGE_3.1_EXPERIMENT_FRAMEWORK.md` and begins design.
