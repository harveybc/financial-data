# Project 3 Phase 4 Synthetic Pretraining Protocol — Orchestrator Review and Execution Prompt

**Role for orchestrator:** Treat this document as a skeptical senior-quant-ML review and implementation directive for Phase 4 synthetic augmentation. It is intended to be incorporated into the Project 3 work plan only if it remains compatible with the existing Stage A/B/C governance, immutable run ledger, fixed PPO/SAC/DQN experiment design, and strict `2025-01-01` held-out firewall.

**Reviewed protocol:**

```text
valid anti-memorization regime_residual_bootstrap_v1
        ↓
synthetic pretraining
        ↓
real-data fine-tuning
        ↓
real validation only
```

**Primary decision:** Conditional approval. The protocol is acceptable only as a **Phase 4 training-protocol experiment** after the matching real-data-only baseline is frozen. It must not alter Stage A ranking, contaminate Stage C, tune against held-out data, or replace real-validation evidence.

---

## 1. Governance verdict

### 1.1 Should this protocol be allowed?

Yes, but only under a controlled Phase 4 branch.

The proposed protocol is scientifically reasonable because it uses synthetic data only for training/pretraining and evaluates exclusively on real validation data. However, it introduces a new optimization pathway and must be treated as another tested strategy family under multiple-testing controls.

The orchestrator must enforce this rule:

```text
Synthetic data may improve training robustness.
Synthetic data must never become evidence of tradability.
```

Real validation and the final locked Stage C evaluation remain the only valid performance evidence.

### 1.2 Required timing

Synthetic pretraining must not be used before the real-data-only Stage B baseline for the candidate is frozen.

Allowed before Stage B:

```text
- generator implementation
- generator smoke tests
- synthetic quality evaluation
- anti-memorization validation
- ledger/artifact wiring
- diagnostic reports
```

Forbidden before Stage B:

```text
- synthetic-pretrained agent-multi runs that influence Stage A ranking
- synthetic-pretrained results used to decide which candidates enter Stage B
- generator repair/tuning based on validation PnL
- augmentation-ratio tuning based on validation PnL
- pretraining-schedule tuning based on validation PnL
```

### 1.3 Practical state model

Use three operational states:

| State | Allowed? | Evidence status |
|---|---:|---|
| Phase 4 tooling before Stage B | Yes | Infrastructure only; cannot influence promotion |
| Synthetic-pretrained training before frozen real-only Stage B baseline | No, except quarantined exploratory runs | Diagnostic only |
| Synthetic pretraining after frozen real-only Stage B baseline | Yes | Paired real-validation comparison allowed |
| Any synthetic work after Stage C inspection | No | Invalid; held-out firewall breach |

---

## 2. Approved first candidate and scope

The first approved candidate should be intentionally narrow:

```yaml
candidate:
  asset: ethusdt
  timeframe: 4h
  algorithm: SAC
  feature_preset: tech_stat
  generator_family_id: regime_residual_bootstrap_v1
  synthetic_use: pretraining_only_then_real_finetune
  validation: real_validation_only
  heldout_start: '2025-01-01'
  stage_c_access: false
```

The experiment must not change SAC hyperparameters, reward definition, environment mechanics, action space, feature preset, cost model, slippage model, episode boundaries, or validation evaluator except where explicitly declared in the Phase 4 manifest.

---

## 3. Best paired comparison design

### 3.1 Mandatory arms

The orchestrator must require the following arms for the first launch:

| Arm | Name | Purpose | Promotion-eligible? |
|---:|---|---|---:|
| A | `real_only_standard` | Existing matched real-data baseline | Yes |
| B | `real_only_compute_matched` | Controls for extra training time/optimization budget | Yes |
| C | `synthetic_only_diagnostic` | Tests whether synthetic data contains useful structure | No |
| D | `synthetic_pretrain_then_real_finetune` | Main proposed protocol | Yes |

Promotion comparison is primarily:

```text
D_synthetic_pretrain_then_real_finetune
  vs
B_real_only_compute_matched
```

The synthetic-pretrained candidate must beat the compute-matched real-only baseline, not merely the standard real-only baseline.

### 3.2 Why compute matching is mandatory

Synthetic pretraining adds optimization steps. If the synthetic-pretrained policy beats the standard baseline but loses to the compute-matched real-only baseline, the correct conclusion is:

```text
Extra training helped. Synthetic data did not prove incremental value.
```

Therefore, the compute-matched real-only control is a hard requirement.

### 3.3 Optional arms

The following arms are optional and should be launched only if explicitly pre-registered and counted as separate trials:

```text
real_plus_synthetic_0_25x
real_plus_synthetic_0_50x
real_plus_synthetic_1_00x
```

For the first Phase 4 agent-multi launch, prefer only A/B/C/D. Running all augmentation ratios immediately increases multiple-testing burden and makes interpretation weaker.

### 3.4 Seed policy

Minimum smoke-test seed set:

```yaml
seeds: [0, 1, 2, 3, 4]
```

Preferred promotion-level seed set, if compute permits:

```yaml
seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

Promotion must not be based on one lucky seed. Report paired deltas by seed.

### 3.5 Cost/slippage scenarios

Every arm must run under the same cost/slippage scenarios:

```yaml
cost_scenarios:
  - base
  - plus_50pct
  - plus_100pct
```

Synthetic augmentation is not promotion-eligible if the validation uplift disappears under realistic or pessimistic costs.

---

## 4. Metrics and statistical accounting

### 4.1 Required paired metrics

For each seed and cost scenario, compute:

```text
delta_seed_i =
  metric(D_synthetic_pretrain_then_real_finetune, seed_i)
  -
  metric(B_real_only_compute_matched, seed_i)
```

Report at minimum:

```text
- median paired delta
- mean paired delta
- paired bootstrap confidence interval
- number of winning seeds
- worst-seed delta
- top-seed-minus-median concentration
- net return after costs
- Sharpe
- Sortino
- Calmar
- Deflated Sharpe Ratio
- max drawdown
- drawdown duration
- turnover
- cost paid
- slippage sensitivity
- action distribution drift
- exposure distribution
```

### 4.2 DSR/PBO controls

The orchestrator must classify every synthetic augmentation attempt as a separate tested strategy specification for DSR/PBO accounting.

Each of the following creates or contributes to a separate trial:

```text
- generator_family_id
- generator_config_hash
- synthetic_ablation_id
- training_protocol_id
- augmentation ratio
- pretraining schedule
- fine-tuning schedule
- seed set
- cost scenario
- feature preset
- algorithm
- asset/timeframe
```

Do not hide failed variants. Failed, killed, diagnostic, and non-promoted runs must remain in the immutable ledger.

### 4.3 Trial ledger schema

The orchestrator should require a table like:

```text
trial_id
candidate_id
asset
timeframe
algorithm
feature_preset
generator_family_id
generator_config_hash
synthetic_ablation_id
training_protocol_id
augmentation_ratio
pretrain_timesteps
finetune_timesteps
seed
cost_scenario
validation_sharpe
validation_sortino
validation_calmar
validation_max_drawdown
validation_turnover
valid_for_training
included_in_dsr
included_in_pbo
stage_c_accessed
```

Required values:

```text
included_in_dsr = true
included_in_pbo = true, where applicable
stage_c_accessed = false
```

---

## 5. Classification: data-family, model-family, or training-protocol-family?

Classify synthetic pretraining primarily as a **training-protocol-family**, with a nested **synthetic-data-generator-family**.

Do not classify it as a model-family because PPO/SAC/DQN remain fixed.

Do not classify it only as a data-family because the proposed protocol changes the training curriculum:

```text
synthetic pretraining
        ↓
real-data fine-tuning
```

This changes optimization order, critic initialization, actor exploration behavior, replay distribution, and convergence dynamics.

Use this taxonomy:

```yaml
strategy_family: ETHUSDT_4h_SAC_tech_stat
training_protocol_family:
  - real_only
  - real_only_compute_matched
  - synthetic_pretrain_then_real_finetune
  - real_plus_synthetic_mixed
synthetic_generator_family:
  - regime_residual_bootstrap_v1
synthetic_ablation_id:
  - pretrain_v1
  - ratio_0_25x
  - ratio_0_50x
  - ratio_1_00x
```

---

## 6. Avoiding synthetic overfitting and hidden hyperparameter search

### 6.1 Freeze the manifest before training

Before any agent-multi command is launched, freeze:

```text
candidate_id
asset
timeframe
algorithm
feature_preset
train_window
validation_window
heldout_boundary
generator_family_id
generator_config_hash
synthetic_ablation_id
pretraining_steps
fine_tuning_steps
augmentation_ratio
sampling_weights
seed_list
cost_scenarios
promotion_metrics
kill_rules
```

No field above may be changed after validation results are inspected.

### 6.2 Do not tune augmentation ratios on validation

Forbidden pattern:

```text
run 0.25x, 0.50x, 1.00x
select the best validation Sharpe
report only the winner
```

Allowed pattern:

```text
pre-register each ratio as a separate trial
run all declared arms
report all results
charge all arms to DSR/PBO accounting
```

### 6.3 Do not tune pretraining length on validation

Forbidden pattern:

```text
try 50k synthetic pretrain
try 100k synthetic pretrain
try 250k synthetic pretrain
choose validation winner
```

Allowed pattern:

```text
choose one pretraining schedule using train-only reasoning
freeze it in the manifest
run validation once as a registered variant
```

If schedule selection is unavoidable, it must happen through train-only inner splits and still be counted in the trial ledger.

### 6.4 Preserve synthetic-origin metadata

The synthetic-origin flag must be preserved end-to-end:

```text
synthetic_origin = 1 for synthetic rows
synthetic_origin = 0 for real rows
```

This supports later diagnostics:

```text
- Did replay/sample weighting overuse synthetic rows?
- Did the policy learn abnormal action patterns on synthetic-origin observations?
- Did synthetic-origin experience dominate early critic learning?
- Did synthetic rows leak into validation?
```

### 6.5 Do not erase failed versions

Every generator version must remain in the ledger, including failed versions.

A failed generator may be useful as a diagnostic or stress-test artifact, but it must be permanently barred from real policy training unless a new version passes all gates and receives a new artifact ID.

---

## 7. Go/no-go checklist before any agent-multi training launch

### 7.1 Generator-validity gate

Launch only if all are true:

```text
[ ] augmentation_summary.json has project3_valid_for_training = true
[ ] SYNTHETIC_LEDGER.csv has valid = true for the generator/evaluator pair
[ ] generator_family_id = regime_residual_bootstrap_v1
[ ] generator_config_hash is recorded
[ ] synthetic_ablation_id is recorded
[ ] train_start and train_end are recorded
[ ] heldout_boundary = 2025-01-01
[ ] project3_mode = true
[ ] no source file opened from forbidden_paths.txt
[ ] no row at or after 2025-01-01 appears in training panels
```

### 7.2 Synthetic quality gate

Require all currently accepted Stage 4.2 gates to pass:

```text
[ ] algebraic_violations = 0
[ ] prices are positive
[ ] volume is nonnegative
[ ] HIGH >= max(OPEN, CLOSE)
[ ] LOW <= min(OPEN, CLOSE)
[ ] typical_price recomputation consistency passes
[ ] KS return-distribution gate passes
[ ] normalized Wasserstein gate passes
[ ] real-vs-synthetic classifier AUC gate passes
[ ] duplicate-window gate passes under the current accepted evaluator definition
[ ] nearest-neighbor overlap gate passes
[ ] copied-subsequence gate passes
[ ] synthetic-vs-validation exact-copy check passes
[ ] synthetic-vs-heldout exact-copy check passes
```

Important evaluator policy:

```text
If the duplicate-window metric definition is changed, that is a new evaluator version.
Do not loosen evaluator gates ad hoc immediately before agent-multi training.
```

### 7.3 Real-only baseline readiness gate

Require:

```text
[ ] Stage A candidate is registered in immutable run ledger
[ ] real-data-only Stage B baseline is complete or frozen for execution
[ ] simple baselines exist
[ ] feature/source-family ablations exist
[ ] leakage audit passes
[ ] cost/slippage baseline exists
[ ] no Stage C access has occurred
```

### 7.4 Paired manifest gate

Require a single immutable manifest before launch:

```yaml
phase4_pair_manifest:
  candidate:
    asset: ethusdt
    timeframe: 4h
    algorithm: SAC
    feature_preset: tech_stat

  generator:
    family_id: regime_residual_bootstrap_v1
    config_hash: REQUIRED
    evaluator_version: REQUIRED
    synthetic_ablation_id: pretrain_v1
    valid_for_training: true

  arms:
    - real_only_standard
    - real_only_compute_matched
    - synthetic_only_diagnostic
    - synthetic_pretrain_then_real_finetune

  seeds:
    - 0
    - 1
    - 2
    - 3
    - 4

  cost_scenarios:
    - base
    - plus_50pct
    - plus_100pct

  promotion_primary_comparison:
    candidate_arm: synthetic_pretrain_then_real_finetune
    baseline_arm: real_only_compute_matched

  validation:
    real_only: true

  heldout:
    boundary: '2025-01-01'
    access_allowed: false
```

No manifest, no training.

### 7.5 Agent-multi execution hygiene gate

Before launching any job:

```text
[ ] same SAC hyperparameters as real-only baseline
[ ] same environment version
[ ] same reward function
[ ] same action space
[ ] same episode boundaries
[ ] same feature files except declared synthetic training data
[ ] same validation evaluator
[ ] same transaction-cost model
[ ] same slippage model
[ ] synthetic_origin flag preserved
[ ] synthetic rows not present in validation
[ ] validation data is real only
[ ] Stage C data path blocked
[ ] run writes to immutable ledger
[ ] failed/killed runs remain in ledger
[ ] GPU lockfile protocol is used for heavy jobs
```

---

## 8. Promotion and kill rules

### 8.1 Promotion rules

Promote the synthetic pretraining protocol only if all are true:

```text
[ ] D beats A_real_only_standard on real validation after costs
[ ] D beats B_real_only_compute_matched on real validation after costs
[ ] D improvement is not concentrated in one seed
[ ] D survives base and at least one pessimistic cost scenario
[ ] D does not materially increase max drawdown
[ ] D does not materially increase turnover
[ ] D improves or preserves DSR after accounting for all trials
[ ] D does not show synthetic-origin exploitation artifacts
[ ] all failed/killed variants remain logged
[ ] all manifests/config hashes/artifact IDs are frozen before Stage C consideration
```

### 8.2 Kill rules

Kill or quarantine the synthetic-pretraining candidate if any are true:

```text
[ ] any 2025-01-01+ data was used in generator fitting, repair, selection, or prompt context
[ ] synthetic rows appear in validation
[ ] synthetic rows appear in Stage C
[ ] augmentation ratio was selected after validation inspection
[ ] pretraining length was selected after validation inspection
[ ] compute-matched real-only baseline is missing
[ ] performance wins only before costs
[ ] uplift is concentrated in one seed
[ ] turnover explodes
[ ] max drawdown materially worsens
[ ] DSR/PBO trial accounting omits failed variants
[ ] run ledger is incomplete
```

---

## 9. Forbidden practices

The orchestrator must treat the following as hard violations:

```text
1. Launching synthetic-pretrained agent-multi runs before the real-only baseline is frozen.
2. Using synthetic-pretrained results to decide which Stage A candidates enter Stage B.
3. Training, fitting, repairing, or selecting the generator using data >= 2025-01-01.
4. Letting synthetic data touch Stage C.
5. Using synthetic-only performance as evidence of tradability.
6. Tuning augmentation ratio on validation and reporting only the best ratio.
7. Tuning pretraining length on validation and reporting only the best length.
8. Changing SAC hyperparameters inside Phase 4.
9. Dropping bad seeds.
10. Dropping failed generator versions from the ledger.
11. Erasing synthetic_origin flags.
12. Recomputing technical/statistical indicators from synthetic data using future windows.
13. Reporting a synthetic win without a compute-matched real-only baseline.
14. Promoting a synthetic candidate that wins only before costs.
15. Promoting a synthetic candidate whose improvement is concentrated in one seed.
16. Running Stage C more than once after seeing results.
17. Loosening anti-memorization gates ad hoc after seeing that a desired generator fails.
18. Treating synthetic validation or synthetic-only backtest performance as real evidence.
```

---

## 10. Final approved first experiment

If all gates pass, the orchestrator may launch exactly this first experiment:

```yaml
approved_phase4_first_experiment:
  candidate:
    asset: ethusdt
    timeframe: 4h
    algorithm: SAC
    feature_preset: tech_stat

  generator:
    family_id: regime_residual_bootstrap_v1
    valid_for_training: true
    anti_memorization_valid: true

  arms:
    A: real_only_standard
    B: real_only_compute_matched
    C: synthetic_only_diagnostic
    D: synthetic_pretrain_then_real_finetune

  seeds: [0, 1, 2, 3, 4]

  cost_scenarios:
    - base
    - plus_50pct
    - plus_100pct

  promotion_comparison:
    primary: D_vs_B
    secondary: D_vs_A

  evaluation:
    validation_data: real_only
    synthetic_data_as_evidence: false
    stage_c_access: false
```

---

## 11. Orchestrator deliverables

After execution, produce:

```text
PHASE4_SYNTHETIC_PRETRAINING_PAIR_REPORT.md
PHASE4_SYNTHETIC_PRETRAINING_PAIR_RESULTS.csv
PHASE4_SYNTHETIC_PRETRAINING_LEDGER_AUDIT.md
PHASE4_SYNTHETIC_PRETRAINING_STAGEC_FIREWALL_AUDIT.md
PHASE4_SYNTHETIC_PRETRAINING_DSR_PBO_ACCOUNTING.md
```

The report must explicitly answer:

```text
1. Did synthetic pretraining beat real-only standard?
2. Did synthetic pretraining beat real-only compute-matched?
3. Did the result survive costs?
4. Was the improvement paired across seeds?
5. Was the improvement concentrated in one seed?
6. Did turnover or drawdown worsen?
7. Were all failed variants logged?
8. Was Stage C untouched?
9. Should the synthetic protocol be promoted, killed, or kept diagnostic?
```

---

## 12. References and project anchors

Project anchors:

- `40_PHASE_4_SYNTHETIC_DATA_AUGMENTATION.md` — Phase 4 is a deferred optional phase; synthetic-only metrics are diagnostic; promotion requires beating matched real-data-only configurations on real validation under identical asset, timeframe, feature preset, algorithm, seed set, split, cost scenario, and reward/action configuration.
- `30_PHASE_3_OVERVIEW.md` — Project 3 holds PPO/SAC/DQN configurations fixed and varies data, feature sets, assets, and timeframes.
- `00_PROJECT_3_MASTER_PLAN.md` — Project 3 is data-centric, systematic, and governed by explicit phase separation.
- `20_PHASE_2_OVERVIEW.md` and Stage 2 deliverables — feature engineering and model-ready feature artifacts are already organized by asset/timeframe and feature family.
- `01_AGENT_INFRASTRUCTURE.md` — heavy GPU jobs must use the GPU lockfile protocol.

External references:

- Bailey, D. H., & López de Prado, M. (2014). **The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality.** SSRN. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2014). **The Probability of Backtest Overfitting.** SSRN. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

---

## 13. Skeptical bottom line

Synthetic pretraining is conditionally approved as a Phase 4 training-protocol experiment. It is not a new evidence standard.

The candidate earns value only if it improves the same real-data candidate against a matched and compute-matched real-only baseline on real validation data, survives costs, survives paired seed comparison, and is charged as another tested strategy family under DSR/PBO accounting.

