# Stage 3.1 — Experiment Framework

## 2026-05-23 Active Replacement: Stage 3X Weekly Walk-Forward Framework

This document originally described a broad static Stage A/B/C matrix. That old
matrix is historical context only. Active work is governed by the weekly
retrained portfolio protocol and SAC-first micro-NSGA input optimization:

- `PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md`
- `PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
- `PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md`

Active experiment unit:

| Field | Meaning |
| --- | --- |
| `target_asset` | Asset traded by the environment and scored for P&L |
| `timeframe` | 5m, 15m, 1h, or 4h simulation step |
| `input_asset_mask` | Other tradable assets whose prices/features may enter the observation |
| `input_source_mask` | Free/paid source families included as inputs |
| `feature_family_mask` | Technical, statistical, decomposition, learned, macro, event, cross-asset, regime families |
| `feature_subset_mask` | Selected columns within each family |
| `preprocessing_profile` | Scaling, clipping, imputation, windowing, lagging, regime conditioning |
| `weekly_anchor_id` | Historical weekend retrain anchor |
| `training_window` | Initial default: 1 year for fast search, later 2-4 years as optimizer genes |
| `validation_week` | Week immediately after training or recent-week validation bundle |
| `test_week` | Next week only, matching intended live model lifetime |
| `model_family` | SAC first; PPO/DQN later as optimized comparators |
| `sac_hyperparameters` | Optimizer genes, not manually guessed constants |
| `broker_profile` | OANDA FX / confirmed crypto venue / other explicit broker profile |

Active split policy:

1. Micro tests may use tiny windows to verify mechanics quickly.
2. Optimization uses repeated weekly anchors: train on past data, validate on
   the next week, test on the following week.
3. Serious evidence aggregates many weekly tests across regimes, seeds, costs,
   and assets.
4. 2025-01-01+ Stage C rows remain locked until a final one-shot evaluation is
   explicitly approved.

Active pass/fail distinction:

- Mechanical blockers: Stage C leakage, missing evidence, bad hashes, missing
  feature/observation hashes, impossible accounting, all-no-trade, hard
  overtrading, broker-policy violations, Friday force-close violations.
- Optimizer objectives: one-week return, Sharpe, drawdown, CVaR, trade count
  inside policy bands, cost-to-gross-edge, feature count, redundancy,
  portfolio diversification.

Tiny smoke runs are allowed to be economically negative. They are not promoted;
they only prove that the experimental machine is wired correctly. The optimizer
then searches for profit/risk improvement over many weekly anchors.

**Stage goal:** Design and execute systematic RL experiments varying trading asset, simulation timeframe, feature input set, and feature engineering technique. Produce evidence about which combinations yield best policies.

**Inputs:** Phase 1 + Phase 2 complete. All raw data + feature library available.

**Outputs:**
- Pre-registered experimental design
- Stage A screening results (broad, low-budget)
- Stage B validation results (top configs, high-budget)
- Stage C held-out results (single eval per candidate)
- SOTA hardening artifacts: availability contract, leakage audit, cost model, baseline/null strategy comparisons, and feature-family ablation plan

**Machine assignment (use all 3 in parallel):**
- **Dragon (RTX 4090, fastest):** Heavy training jobs, primary candidate refinement
- **Gamma (RTX 5070 Ti, fast):** Parallel training, secondary candidates
- **Omega (RTX 4070, slowest):** Light training + evaluation + reports

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

## 1. Pre-Registered Experimental Design

The active pre-registration must describe the weekly walk-forward design above.
Older static-matrix hypotheses below are retained only as examples of feature
families and controls that may be converted into weekly-anchor experiments.

Before any runs, produce `experiments/design/pre_registered_design.md` with:

### 1.0 Historical SOTA Hardening Gate (Adopted 2026-05-02)

The old critique document is archived under
`work_plan/archive_superseded_2026_05_23_weekly_data_first/PROJECT3_SOTA_CRITIQUE_AND_IMPROVEMENT_PROPOSAL.md`.
Its controls remain useful as historical governance references, but the active
operating plan is the weekly-retrained Stage 3X protocol above.

- Current Stage A first-wave runs are valid as infrastructure smoke and preliminary screening evidence.
- No configuration can advance to Stage B until the P0 hardening checks below pass.
- Any result produced before these checks is labeled `pre_hardening_screening` unless revalidated.

Required P0 artifacts:

| Artifact | Purpose | Blocking rule |
| --- | --- | --- |
| `artifacts/run_ledger.jsonl` / `artifacts/run_ledger.parquet` | Immutable record of every run event, including failures and discarded seeds | Any Stage B packet referencing runs absent from the ledger is invalid |
| `configs/experiment_registry.schema.json` | Machine-readable schema for trial ids and ledger events | Missing required trial metadata blocks promotion |
| `features/AVAILABILITY_CONTRACT.md` | Defines event time, availability time, vintage/revision policy, release lag, and staleness semantics | Missing availability metadata blocks Stage B promotion for cross-source features |
| `configs/availability_contract.schema.json` | Machine-readable contract for provider availability metadata | Non-price feature families without a valid contract are exploratory only |
| `experiments/design/leakage_audit.md` | Defines held-out exclusion, fitted-transform, macro vintage, and negative-control checks | Any P0 leakage failure blocks promotion |
| `experiments/design/cost_model.md` | Defines optimistic/base/pessimistic friction scenarios | Zero-cost-only candidates cannot be promoted |
| `configs/cost_scenarios.yaml` | Machine-readable cost scenarios used by promotion evaluators | Missing base/pessimistic cost evidence blocks promotion |
| `experiments/design/feature_family_ablation_plan.md` | Defines family-level attribution and subscription marginal-value tests | All-feature winners require family-level support |
| `experiments/design/stage_b_promotion_gate.yaml` | Defines the final Stage A to Stage B go/no-go rules | Candidates not satisfying the gate remain `watch` or `blocked` |

Additional mandatory controls:

- Compare every promoted RL candidate against no-trade/cash, buy-and-hold, random or turnover-matched random, simple momentum, simple reversal, and at least one supervised diagnostic baseline where feasible.
- Report raw Sharpe, net Sharpe, Deflated Sharpe Ratio, seed mean/std, and PBO/CSCV-style diagnostics where feasible.
- Report paired uplift versus matched baselines; unpaired leaderboard rank alone is not promotion evidence.
- Add Reality Check / SPA-style family-level testing where feasible for large candidate families.
- Report seed dispersion, median/IQM-style aggregate, and bootstrap confidence intervals where feasible.
- Report cost sensitivity under optimistic, base, and pessimistic scenarios.
- Report regime-sliced performance for Stage B candidates.
- Keep PPO/SAC/DQN fixed for the core Phase 3 experiment. TradingAgents, Decision Transformer, CQL/IQL, and time-series foundation-model lanes remain deferred until core baselines are reproducible.

### 1.1 Hypotheses

| Hypothesis | Description | Test |
|------------|-------------|------|
| H1 | Including macro features improves RL policy on FX | Compare FX policies with/without forward-filled FRED |
| H2 | Including on-chain features improves RL policy on crypto | BTC/ETH with/without Glassnode + CoinMetrics features |
| H3 | Signal decomposition features (wavelet, EMD) add value over technical alone | Add wavelet/EMD to baseline |
| H4 | Learned representations (autoencoders) outperform raw features | AE embeddings vs raw feature concatenation |
| H5 | Lower simulation timeframes (5m) provide more learnable signal than higher (4h) | Compare same asset across timeframes |
| H6 | Cross-asset features (e.g., VIX for equity-correlated assets) help | Add cross-asset features |
| H7 | Tokenized observations (KMeans codes) work for transformer policies | Token vs continuous embeddings |
| H8 | Feature-family gains remain positive after base transaction costs | Compare gross vs net performance under cost scenarios |
| H9 | Paid/subscription families add measurable marginal value over best free stack | Matched ablation: best free stack vs best free + paid family |

### 1.2 Trading asset universe

Initial scope (Stage A screening):
- BTC/USDT (primary crypto)
- ETH/USDT (secondary crypto)
- EUR/USD (primary FX)
- USD/JPY (secondary FX)

Plus 1-2 from each: GBP/USD, AUD/USD, BTCUSDT_perp.

Stage B can include more if Stage A reveals interesting candidates.

### 1.3 Simulation timeframes

All 4: 5m, 15m, 1h, 4h.

### 1.4 Feature input sets

Define discrete "feature presets" for systematic comparison:

| Preset | Description | Features included |
|--------|-------------|-------------------|
| `baseline_12` | Project 2 baseline | 12 technical features (returns, log_returns, RSI, MACD hist, BB pos, volume ratio, EMA cross, ATR norm, OBV delta, momentum_5, momentum_20, vol_20) |
| `tech_full` | All technical features | All Stage 2.2 technical features (~80 features) |
| `tech_stat` | Technical + statistical | tech_full + Stage 2.2 statistical |
| `tech_stat_decomp` | Plus signal decomposition | + Stage 2.3 wavelet + EMD + fracdiff |
| `learned_lstm` | LSTM autoencoder embedding (32-dim) | Latent vector replaces raw features |
| `learned_transformer` | Transformer AE embedding | Same |
| `learned_cvae` | CVAE embedding | Same |
| `tech_macro` | Technical + cross-asset macro | tech_full + forward-filled FRED |
| `crypto_full` | Crypto-specific full | tech_full + on-chain (Glassnode + CoinMetrics) + funding rates |
| `fx_full` | FX-specific full | tech_full + COT positioning + bond spreads + macro |
| `kitchen_sink` | Everything | All available features (high-dimensional, may overfit) |

This produces ~10 distinct feature presets per (asset, timeframe).

Feature presets must map to the family ids in `experiments/design/feature_family_ablation_plan.md`. The Stage A summary must rank feature families by marginal contribution, not only individual run performance.

### 1.5 RL algorithms (held fixed)

Use Project 2 best configurations exactly. From Project 2 Part II-7 pilot results:

- **PPO** (BTC 1h technical): val Sharpe 2.4 (was buy-and-hold artifact, but algo config is solid)
- **SAC** (BTC 1h technical)
- **DQN** (BTC 1h technical)

For each (asset, timeframe, feature_preset), test ALL 3 algorithms.

### 1.6 Total experiments matrix

Stage A screening:
- 6 assets × 4 timeframes × 10 feature presets × 3 algos × 3 seeds = **2160 runs**
- Each run: ~100k timesteps (cheap, fast)
- Estimated total compute: substantial but feasible across 3 GPUs

Stage A is too large for full execution. Apply staged screening:

**Stage A reduced (more practical):**
- 4 assets × 2 timeframes (1h, 4h — biggest impact, less compute) × 10 presets × 3 algos × 2 seeds = **480 runs**
- Each ~100k timesteps

**Stage B validation:**
- Top 20 configurations from Stage A
- Each run: 1M-2M timesteps × 3 seeds = 60 jobs
- Heavy compute, but bounded

**Stage C held-out:**
- Top 5 from Stage B per asset class (crypto, FX, mixed) = 15 candidates
- Single deterministic rollout each on 2025 held-out

### 1.7 Kill criteria (Rule P3.4)

A configuration is "killed" (not promoted to Stage B) if Stage A screening shows:
- Mean validation Sharpe < 0 across seeds
- Mean validation Sharpe within ±0.1 of buy-and-hold (no edge)
- Run errors / NaN losses / training diverges
- Positive gross returns but non-positive net returns under the base cost scenario
- Missing required availability/vintage/staleness metadata for any promoted cross-source family
- Any fitted-transform leakage audit failure
- Underperformance versus a simple baseline after costs without a documented reason to keep it

A configuration is "killed" at Stage B if:
- Mean validation Sharpe < 0.3 (per Project 2 KPI bar)
- Excessive drawdown (>30%) on validation
- DSR/PBO evidence indicates likely overfit selection
- Performance survives only optimistic costs but fails base or pessimistic costs
- Regime-sliced diagnostics show catastrophic concentrated failure without a clear risk note

Kill criteria documented BEFORE runs. Post-hoc relaxation forbidden.

### 1.8 Multiple-testing correction

With 480+ Stage A runs, expect false positives. Apply:

- **Deflated Sharpe Ratio (Lopez de Prado):** account for variance + skewness + kurtosis + number of trials
- **DSR threshold:** require DSR p-value < 0.01 (stricter than 0.05) to claim significance
- **PBO/CSCV diagnostic:** add Probability of Backtest Overfitting or CSCV-style diagnostic where feasible, especially for Stage B promotions
- **Seed variance:** every ranking includes mean, standard deviation, and worst-seed metrics
- **Family-level trial count:** report the number of trials per feature family and per asset class

```python
def deflated_sharpe_ratio(observed_sharpe, n_trials, returns):
    """Lopez de Prado DSR with multiple testing correction."""
    # ... formula from Lopez de Prado (2018)
    pass
```

---

## 2. Stage A — Screening Execution

### 2.1 Run infrastructure

Reuse + extend `agent-multi/tools/seed_sweep.py` from Project 2 Part III plan.

**GPU lockfile requirement (mandatory, master plan Rule M.14):** every RL training run on Dragon or Gamma MUST acquire `/tmp/gpu_busy.lock` before instantiating models. This is the longest-running GPU stage of the project — Tier 1 supervisors will skip ticks during training, which is expected. Cron interval on Dragon and Gamma should be **30 min** during this stage (per `01_AGENT_INFRASTRUCTURE.md` §4.5).

`agent-multi/tools/seed_sweep.py` is extended in this stage to wrap each training invocation with the gpu_lock helper:

```python
import sys
sys.path.insert(0, "/home/harveybc/Documents/GitHub/financial-data/_scripts/lib")
from gpu_lock import acquire_gpu_lock, release_gpu_lock

acquire_gpu_lock(
    command=f"agent_multi train --algo {algo} --asset {asset} --timeframe {tf} --seed {seed}",
    expected_duration_minutes=30 if total_timesteps == 100_000 else 240,  # screening vs validation
    stage="3.1",
)
try:
    run_training(...)
finally:
    release_gpu_lock()
```

The dispatcher (Tier 2) is responsible for SSH and conda activation. Example invocation that the dispatcher composes:

```bash
# Per (asset, timeframe, feature_preset, algo, seed) run:
ssh dragon "source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && \
  cd /home/harveybc/Documents/GitHub/agent-multi && \
  python -m agent_multi train \
    --algo ppo \
    --asset btcusdt \
    --timeframe 1h \
    --feature_preset tech_full \
    --total_timesteps 100000 \
    --seed 0 \
    --output_dir /home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/runs/<run_id>/"
```

### 2.1.1 Autonomous backlog refill policy

Stage A must not stop just because a hand-written queue is empty. The Omega supervisor owns a deterministic queue refill worker:

```bash
python _scripts/workers/stage31_expand_matrix_queue_worker.py --target-pending 48
```

This worker reads the Stage 3.1 matrix and appends safe pending jobs to:

- `experiments/stage_a_screening/queues/dragon.json`
- `experiments/stage_a_screening/queues/gamma.json`
- `experiments/stage_a_screening/queues/omega.json`

Standing execution policy:

- Dragon keeps a rolling backlog of crypto GPU jobs covering BTC/USDT, ETH/USDT, major spot/perp assets, 15m/1h/4h, PPO/SAC/DQN, baseline/technical/statistical/decomposition/learned/SOTA feature presets, and multiple seeds.
- Gamma keeps a rolling backlog of FX GPU jobs covering EUR/USD and USD/JPY first, then additional FX pairs as local feature inputs become available.
- Omega keeps a rolling backlog of light CPU jobs covering FX assets, 1h/4h, DQN/PPO, and lower timestep budgets so it can contribute while still acting as coordinator.
- The supervisor checks runnable statuses only: `pending`, `queued`, `retry`, and `needs_retry`. Completed, running/training, skipped, failed, and blocked jobs are not counted as usable backlog.
- When any machine is idle and has runnable backlog, the supervisor starts the next worker without waiting for a human status request.
- When a matrix slice is exhausted, the supervisor expands to the next safe asset/timeframe/preset/algorithm/seed slice rather than declaring no work.
- A machine may be idle only for a documented reason: GPU lock held by another valid job, SSH unreachable, missing local inputs, active blocker, exhausted full approved matrix, or user-approved pause.
- Every worker report must name the work-plan stage, active run id, expected/generated deliverable path, and current status.

The queue refill report is written to `_logs/supervisor_reports/stage31_queue_expansion.md` and `_metadata/stage31_queue_expansion.json`. This report is part of status review and should be committed when the experiment design or queue policy changes.

### 2.2 Run registry

Each run produces `summary.json` with metrics, config, git_sha. All summaries aggregate to `experiments/stage_a_screening/index.csv`.

### 2.3 Parallel execution

Distribute runs across 3 machines:
- Dragon: PPO BTC + ETH all timeframes all presets
- Gamma: SAC + DQN crypto + PPO FX
- Omega: SAC + DQN FX + parallel light jobs

Approximate parallelism: 3 jobs per machine simultaneously × 3 machines = 9 concurrent runs.

### 2.4 Stage A deliverable

`experiments/stage_a_screening/stage_a_summary.md`:

- Total runs: [N]
- Successful: [N]
- Failed: [N] with reasons
- Top 20 configs by mean validation Sharpe (with DSR correction)
- Top configs by net Sharpe under base cost scenario
- Baseline comparisons: no-trade, buy-and-hold, random/turnover-matched random, simple momentum, simple reversal, supervised diagnostic baseline where feasible
- Leakage-audit status for every promoted candidate
- Availability/vintage/staleness status for cross-source features
- Cost scenario sensitivity for promoted candidates
- Feature-family marginal contribution ranking
- Heatmap: feature preset × asset class showing which presets work where
- Kill list: configs not promoted to Stage B and reasons

User reviews. Approves Stage B candidates.

---

## 3. Stage B — Validation Execution

### 3.1 Validation runs

For each of top 20 configs from Stage A:
- 1M-2M total_timesteps (full budget)
- 3 seeds
- d5 fitness during GA hyperparameter search if applicable
- d6 NEVER touched (held-out)

### 3.2 Validation gate

For Stage B to proceed past validation:
- Mean validation Sharpe ≥ 0.3 across 3 seeds
- Std validation Sharpe < 0.5 (i.e., not high variance)
- No degenerate policy (e.g., always-long, always-short, no-trade)
- Positive net performance under base cost and acceptable degradation under pessimistic cost
- No P0 leakage or availability contract failure
- Not dominated by simple non-RL baselines after costs
- PBO/CSCV diagnostic does not indicate obvious backtest overfitting, where feasible

### 3.3 Stage B deliverable

`experiments/stage_b_validation/stage_b_summary.md`:

- Top 5 candidates per asset class promoted to Stage C
- Hyperparameter sensitivity analysis
- Robustness checks (across seeds, across feature subsets)
- Regime-sliced returns, drawdown, turnover, and action distribution
- Cost scenario matrix for all promoted candidates
- Final frozen candidate list before held-out evaluation

User reviews. Approves Stage C held-out test.

### 3.4 Stage B orchestration addendum (2026-05-12)

Current Stage B validation is no longer a planned/manual launch step. It is an
active locked execution lane with fail-closed telemetry:

- Locked run plan:
  `experiments/stage_b_validation/run_plan/stage_b_locked_run_plan.json`
- Per-machine live status:
  `_scripts/workers/stage_b_machine_live_status_worker.py`
- Cluster live status:
  `_scripts/workers/stage_b_cluster_live_status_worker.py`
- Locked executor:
  `_scripts/workers/stage_b_locked_run_executor.py`
- Idle redispatcher:
  `_scripts/workers/stage_b_idle_redispatcher.py`
- Run-plan status/audit:
  `_scripts/workers/stage_b_run_plan_status_worker.py`
- Statistical trace audit:
  `_scripts/workers/stageb_dsr_pbo_evaluator.py`

Operational rules added during execution:

- Status reports must include per-machine current task, percent complete,
  trade count, profit, done count, pending count, failed count, and no-trade
  anomaly state.
- A running job with zero trades at or after 20% progress is a hard anomaly and
  must be aborted or quarantined; zero-trade runs cannot promote.
- Excessive final turnover and always-in-market behavior are warning/hard-gate
  diagnostics in Stage B summaries. They do not automatically promote or kill a
  run without the economic and statistical gates below, but they must be
  reported before any Stage C consideration.
- Idle Dragon/Gamma/Omega capacity must be redispatched from remaining locked
  backlog whenever safe. The final leftover task must also be movable; a
  one-task imbalance is not a valid idle reason.
- SSH launch timeouts are not sufficient evidence of failure if the remote
  executor or `agent-multi --load_config` process is verified as active.

Current Stage B statistical state:

- `agent-multi` emits return trace CSVs and `evidence.json` sidecars for Stage B
  runs.
- `stageb_dsr_pbo_evaluator.py` can scan Stage B run traces and writes:
  `experiments/stage_b_validation/hardening/stageb_dsr_pbo_report.{json,md}`.
- The current evaluator is a preliminary trace audit plus approximate
  contiguous-fold PBO diagnostic. It is not yet a full purged CSCV implementation
  and not a White Reality Check / Hansen SPA family test.
- As of the first Stage B trace audit, Stage B traces exist, but no candidate
  should be promoted until all active locked runs finish and the final evaluator
  report clears B3/B4.

Immediate next orchestration sequence after active runs finish:

1. Refresh live status and confirm no active Stage B process remains:
   `python _scripts/workers/stage_b_cluster_live_status_worker.py`.
2. Sync remote Stage B run artifacts from Dragon and Gamma back to Omega before
   statistical or run-plan audits. The local audit files are authoritative only
   after this sync because remote GPU runs write progress, summaries, traces,
   and evidence sidecars on the executing machine first.
3. Refresh the run-plan audit:
   `python _scripts/workers/stage_b_run_plan_status_worker.py`.
4. Run the Stage B statistical evaluator:
   `python _scripts/workers/stageb_dsr_pbo_evaluator.py`.
5. Re-run the Stage B approval gate:
   `python _scripts/workers/stage_b_approval_gate_worker.py`.
6. Generate `experiments/stage_b_validation/stage_b_summary.md` only after the
   evaluator and approval gate are refreshed.
7. If no candidate clears B3/B4, Stage 3.1 closes as "no Stage C candidate" and
   Stage 3.2 becomes a negative/diagnostic synthesis, not a held-out launch.
8. If at least one candidate clears B3/B4 and the economic gates, freeze the
   candidate manifest and request explicit user approval before any Stage C
   held-out execution.

---

## 4. Stage C — Held-Out Execution

### 4.1 Held-out evaluation

For each Stage B winner:
- Load best policy checkpoint (best of 3 seeds by validation Sharpe)
- Single deterministic rollout on d6 = 2025-01-01 to 2025-12-31
- Compute final metrics: Sharpe, Sortino, Calmar, max DD, win rate, trade count, transaction cost ratio
- Report optimistic, base, and pessimistic cost scenarios
- Do not change feature selection, transforms, hyperparameters, prompts, or candidate list after seeing held-out results

### 4.2 Statistical evaluation

For each held-out result:
- Bootstrap confidence intervals (1000× trade-level resampling)
- Compare to buy-and-hold + random walk + Project 2 best result
- Apply DSR with full multiple-testing correction

### 4.3 Stage C deliverable

`experiments/stage_c_held_out/stage_c_results.md`:

- Final results table per candidate
- Statistical significance per result
- Qualitative analysis (what worked, what didn't)

User reviews. Synthesis Stage 3.2 begins.

---

## 5. Stage 3.1 Deliverable

`STAGE_3.1_DELIVERABLE.md`:

```markdown
# Stage 3.1 Deliverable — Experiment Framework

## Pre-registered design

[reference to design document]

## Stage A screening

- Total runs executed: [N]
- Top 20 configs identified
- DSR correction applied

## Stage B validation

- 20 configs full-budget tested
- Top 5 per asset class promoted

## Stage C held-out

- 15 candidates evaluated on 2025 held-out
- Statistical significance per result documented

## User Gate

User reviews. Approves Stage 3.2 (Results Synthesis) start.
```

---

## 6. User Gate

User approves moving to Stage 3.2 final synthesis.
