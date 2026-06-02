# Project 3 Market-State Representation Optimization Plan

Date: 2026-05-23 local / 2026-05-24 UTC

## Decision

Project 3 will treat market-state representation as a first-class optimization
object. The model family is not the first bottleneck. The first bottleneck is:

> Can we encode the current market state, before the weekly trading cutoff, in
> a way that helps the weekly retrained system choose useful inputs,
> preprocessing, no-trade flags, and asset/model exposure for the next week?

The active direction is therefore:

1. build several train-only state representations;
2. compare them cheaply on CPU before GPU;
3. feed only surviving profiles into SAC micro-NSGA;
4. later let DEAP/NSGA choose among state profiles, feature families,
   preprocessing, target assets, input assets, portfolio policies, and SAC
   hyperparameters.

Stage C remains locked. No state encoder may fit, select, tune, or refute on
rows at or after `2025-01-01`.

## State Unit

One state unit is:

```text
target_asset + timeframe + weekly_anchor + observation_window + decision_cutoff
```

The current contract maps:

- `patient`: target asset at weekly anchor;
- `patient_state`: market state before the weekly decision cutoff;
- `medicine`: selected input families, preprocessing, no-trade flags, exposure
  buckets, and supervisor settings;
- `outcome`: next-week market/trading outcome vector.

Default timing:

- 12-hour pretrade gap before the next week starts;
- 6-hour absolute minimum gap for later experiments;
- no weekend-border data after the cutoff;
- outcome stays exactly the next trading week.

Implemented base artifact:

```text
experiments/stage3x_market_state_causal_contract/
```

## Candidate State Profiles

The optimizer should not pick blindly from raw features. It should choose from
named state profiles with known semantics and evidence.

### Profile 00 - Engineered Summary

Cheap, interpretable baseline.

Components:

- cumulative return over the lookback;
- volatility / realized volatility;
- trend slope and momentum;
- max drawdown;
- downside deviation / CVaR proxy;
- skew / kurtosis or tail-risk proxy when stable;
- volume, liquidity, spread, and cost proxies when available;
- cross-asset relative strength, rolling correlations, and beta-like exposure;
- seasonal sin/cos fields;
- hours/bars to Friday force close;
- Monday entry context;
- known next-week event-calendar risk score;
- train-only regime/OOD summaries when already available.

This profile must always exist. It is the benchmark all learned encoders must
beat.

### Profile 01 - Engineered + PCA

First compression layer. Use PCA or robust PCA on standardized train-only state
features.

Why:

- fast;
- auditable;
- exposes redundancy;
- useful as a sanity check against neural embeddings;
- produces deterministic components and explained-variance metadata.

Default dimensions:

- 4h: `4, 8, 12`;
- 1h: `8, 16, 24`;
- choose by train-only explained variance and validation utility, not by test.

### Profile 02 - Engineered + Autoencoder

Nonlinear compression baseline.

Rules:

- fit only on train windows;
- freeze encoder before validation/test transformation;
- small MLP only at first;
- bottleneck dimensions: `8, 16, 32`;
- compare against PCA before spending GPU on RL.

Use this only if reconstruction/OOD/validation diagnostics beat PCA.

### Profile 03 - Engineered + TS2Vec/Contrastive Embedding

Sequence representation for full 1h/4h windows.

Reason:

- TS2Vec-style hierarchical contrastive learning is designed to produce
  representations at timestamp and subsequence level;
- it is a strong candidate for one-week or multi-week state windows;
- it can capture nonlinear temporal patterns that summary statistics miss.

Default:

- 1h: primary candidate, because one week has 168 bars;
- 4h: use 2-4 week lookback if one week has too little temporal detail.

### Profile 04 - Engineered + Patch/Masked Time-Series Embedding

PatchTST-style or masked-patch representation.

Reason:

- patching gives local temporal context and reduces attention cost;
- useful for 1h windows and longer 4h lookbacks;
- may work better than pointwise transformer inputs.

Initial use:

- CPU/pretraining contract only;
- no broad GPU SAC until it beats engineered/PCA profiles in state diagnostics.

### Profile 05 - Engineered + Regime Probabilities

Regime layer, not the whole state.

Candidates:

- HMM/GMM probabilities;
- hierarchical clustering;
- Wasserstein/DTW clustering;
- train-only cluster distances;
- regime entropy;
- transition probability / persistence score.

The output must include probabilities and uncertainty, not only a hard
`regime_id`.

### Profile 06 - Hybrid Full

Full candidate only after components work:

```text
engineered_summary
+ PCA or autoencoder bottleneck
+ contrastive/patch embedding
+ regime probabilities
+ OOD/anomaly score
+ event-calendar risk vector
```

This is not the first GPU target. It is a later survivor profile.

## Timeframe Policy

Both `1h` and `4h` must be tested, but not by a brute-force Cartesian product.

### 4h

- one week has only 42 bars;
- engineered summary and regime probabilities are likely strong;
- learned sequence embeddings should use 2-4 weeks of lookback;
- lower trading frequency and lower cost pressure;
- good first target for OANDA FX and 4h crypto/perp research.

### 1h

- one week has 168 bars;
- better for sequence encoders and intraday state transitions;
- higher risk of overtrading and cost drag;
- must pass trade-frequency and Friday-force-close policy earlier.

Initial rule:

- CPU screen both 1h and 4h;
- GPU smoke only the top profile per family/timeframe unless CPU evidence shows
  meaningful diversity.

## Efficient Experiment Ladder

### M0 - Contract And Toy Mechanics

Purpose: prove state profiles are generated, hashed, split-safe, and
optimizer-addressable.

No real training.

Required outputs:

- state-profile schema;
- tiny fixture with 1h and 4h rows;
- train-only fit metadata for PCA/autoencoder/regime profiles;
- hashes for source data, selected columns, fitted encoder config, and encoder
  output;
- no Stage C rows;
- no post-cutoff data.

Pass means mechanical correctness, not profitability.

### M1 - CPU State Screen

Purpose: rank state profiles before GPU.

For each target asset/timeframe/profile:

- fit state encoder on train only;
- transform validation/test windows without refit;
- compute relation to next-week outcomes;
- compute stability across anchors;
- compute placebo/negative-control failures;
- compute leakage/refutation checks;
- emit profile shortlist.

Required diagnostics:

- rank IC / Spearman to next-week return and drawdown outcomes;
- mutual-information proxy;
- validation stability by regime and asset;
- missingness and constant checks;
- distance/OOD summaries;
- negative controls:
  - shuffled outcome;
  - future-leaked feature sentinel must fail;
  - irrelevant feature family should not dominate;
- no-trade / trade-frequency compatibility if proxy strategy is used.

### M2 - Causal Diagnostic Screen

Purpose: determine which input/state families are plausible causes of useful
next-week decisions, not just correlations.

Allowed methods:

- lag-only conditional dependence;
- blocked time-series DML;
- causal forest as diagnostic;
- invariant-risk screening across weekly anchors/regimes;
- placebo and sensitivity checks.

Forbidden conclusions:

- "causal proof of alpha";
- automatic feature deletion;
- Stage C tuning;
- broad GPU unlock by causal score alone.

Output should be a prior for DEAP/NSGA:

```text
state_profile_id
feature_family
effect_direction
effect_stability
refutation_status
optimizer_prior_weight
```

### M3 - Micro GPU Smoke

Purpose: verify that a state profile changes SAC behavior and produces valid
evidence.

Only after M1/M2.

Default maximum per generation:

- 12 contracts;
- 3 seeds;
- base cost only;
- 5000 timesteps per cell;
- 14d train / 7d validation / 7d test for mechanics;
- Stage C denied.

Hard stop if:

- missing evidence;
- missing feature/observation hash;
- no trades across all completed seeds;
- hard overtrading;
- broker-policy violation;
- impossible portfolio accounting;
- Stage C row or Stage C authorization.

Negative return is not a blocker at this stage. It is an optimizer objective.

### M4 - Micro-NSGA With State Genes

Expose these genes:

- `timeframe`: `1h`, `4h`;
- `market_state_profile_id`;
- `state_lookback_weeks`;
- `pca_dim`;
- `autoencoder_dim`;
- `embedding_family`;
- `regime_model_family`;
- `input_asset_mask`;
- `feature_family_mask`;
- `preprocessing_profile`;
- `SAC_hyperparameters`;
- `portfolio_no_trade_threshold`;
- `portfolio_allocation_policy`.

Keep micro-NSGA small until at least one profile shows non-degenerate behavior
across several anchors.

### M5 - Serious Weekly Walk-Forward

Only after M4 finds survivors.

Use repeated weekly anchors across regimes:

- train window: 1-4 years, parameterized;
- validation: previous week or recent bundle;
- test: exactly next week;
- aggregate across anchors, seeds, costs, and baselines.

This is where profit/risk claims begin to become meaningful.

## Three-GPU Scheduling

The GPUs should not run redundant variants in parallel.

While a micro generation is active:

- do not launch another GPU generation unless the dispatcher has capacity and
  the current generation has no mechanical failure;
- use CPU-only state screens in parallel with GPU smoke;
- synthesize each generation before launching the next.

Recommended division once state-profile GPU smoke begins:

- **dragon:** 4h engineered/PCA/regime profiles;
- **gamma:** 1h engineered/PCA/regime profiles;
- **omega:** learned embeddings / autoencoder / TS2Vec / Patch profile smoke.

This keeps families separate and avoids running three copies of the same idea.

GPU escalation rule:

1. CPU profiles rank all candidates.
2. Pick at most one survivor per profile family/timeframe.
3. Run 3-seed smoke.
4. Keep only profiles with valid evidence and non-degenerate behavior.
5. Expand anchors before expanding model complexity.

## No-Redundancy Rules

Do not run both profiles if they are equivalent under CPU diagnostics:

- same selected features;
- same state hash;
- same top PCA/embedding neighbor structure;
- same regime assignment for >95% of anchors;
- same proxy actions/trades;
- no meaningful change in feature family importance.

Do not send learned embeddings to GPU if they fail to beat engineered/PCA on:

- validation stability;
- negative controls;
- OOD sanity;
- next-week relation metrics;
- behavior sensitivity in proxy tests.

## Required New Workers

### financial-data

1. `_scripts/workers/stage3x_market_state_profile_worker.py` **implemented**
   - generate engineered/PCA/regime profile contracts;
   - optional stubs for autoencoder/TS2Vec/Patch profiles until dependencies
     are confirmed;
   - output profile hashes and fit metadata.

2. `_scripts/workers/stage3x_market_state_profile_screen_worker.py` **implemented**
   - CPU rank profiles by next-week outcomes;
   - run negative controls;
   - emit shortlist for optimizer.

3. `_scripts/workers/stage3x_market_state_causal_screen_worker.py`
   - consume the causal contract;
   - estimate diagnostic effects by family;
   - emit optimizer prior weights and refutation status.

4. Extend `_scripts/workers/stage3x_micro_nsga_nextgen_worker.py`
   - include `market_state_profile_id`;
   - include profile hash;
   - include state encoder metadata in selected contracts.

### agent-multi / gym-fx

Only after financial-data profile contracts exist:

1. extend config generation to preserve `market_state_profile_id` and
   `market_state_profile_hash`;
2. ensure observation evidence includes the market-state fields/hash;
3. add no-training fixtures proving profile columns reach the environment
   observation;
4. no SAC/PPO/DQN algorithm source edits.

## Agent Allocation

### Codex

Owns:

- this plan;
- financial-data integration;
- first CPU profile worker if small enough;
- acceptance checks;
- G18/G19 orchestration;
- final docs and status.

### Claude

Best task:

- implement or review the financial-data CPU profile/screen/causal workers;
- focus on leakage, split safety, negative controls, and deterministic hashes.

### Copilot

Best task:

- implement agent-multi/gym-fx profile plumbing after financial-data emits the
  profile contract;
- prove market-state columns reach observations;
- preserve evidence fields in traces.

### ChatGPT 5.5 Pro Web

Use only for research review:

- verify state-representation choices;
- recommend minimal dependencies for TS2Vec/Patch/autoencoder;
- critique causal assumptions and failure modes.

Do not ask ChatGPT Web to mutate code.

## Acceptance Criteria

Before state profiles may drive GPU smoke:

- state-profile worker passes tests;
- profile screen passes tests;
- causal screen or diagnostic stub passes tests;
- all artifacts emit `stage_c_access=DENIED`;
- every fit object records train-only fit window;
- every profile records source hash, selected columns, encoder config hash, and
  output hash;
- negative controls fail as expected;
- selected profiles are nonredundant;
- G18 or any active GPU generation is synthesized before new GPU expansion.

## Implementation Status

Updated: 2026-05-23 local / 2026-05-24 UTC.

- Market-state causal contract: implemented and generated.
- Market-state profile worker: implemented.
- Market-state profile screen worker: implemented.
- Tests:
  - `test_stage3x_market_state_profile_worker.py`
  - `test_stage3x_market_state_profile_screen_worker.py`
  - full `test_stage3x*.py` slice passed.
- Generated profile artifacts:

```text
experiments/stage3x_market_state_profile/stage3x_market_state_profiles.json
experiments/stage3x_market_state_profile/stage3x_market_state_profiles.md
experiments/stage3x_market_state_profile/stage3x_market_state_profile_screen.json
experiments/stage3x_market_state_profile/stage3x_market_state_profile_screen.md
experiments/stage3x_market_state_profile/selected_market_state_profiles.json
```

Current counts:

- total profiles: `144`
- implemented CPU profiles: `72`
- learned-encoder stubs: `72`
- eligible CPU profiles: `72`
- selected nonredundant profiles: `12`
- Stage C access: `DENIED`
- training launched by these workers: `false`

The selected profile packet is now ready for agent-multi/Copilot plumbing:

```text
experiments/stage3x_market_state_profile/selected_market_state_profiles.json
```

Do not launch a GPU smoke expansion for these profiles until the current G18
micro-NSGA generation is synthesized or Codex explicitly accepts spare capacity.

## References

- TS2Vec: hierarchical contrastive time-series representation learning.
- PatchTST: patch-based transformer representation and forecasting.
- TimesURL: self-supervised universal time-series representation.
- EconML DML/CausalForestDML: ML-based heterogeneous treatment-effect
  diagnostics.
- Tigramite/PCMCI and time-series causal inference literature: causal discovery
  and effect estimation with temporal order.
