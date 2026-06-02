# Spec Kit / Copilot Prompt: Financial OHLCV Synthetic Data Generator Plugin Suite

## Codex Review And Project 3 Integration

This prompt is approved as a strong starting point, with one important project-governance constraint:

**This work belongs in a deferred Project 3 Phase 4 / Stage 4.1 synthetic-data augmentation lane, not in the current Phase 3 promotion evidence.**

Synthetic data can be valuable for robustness testing, stress-scenario generation, low-resource augmentation, and policy pretraining, but it must never replace real-data validation. A strategy trained with synthetic augmentation may only be considered better if it improves on real validation data and later survives the locked real 2025 held-out evaluation. Synthetic-only performance is diagnostic, not promotional.

Project 3 usage policy:

1. Complete Phase 3 Stage A/B governance first: ledger, simple baselines, feature-family ablation, leakage audit, cost gates, and promotion packets.
2. Select a small set of candidate assets/timeframes/features from real-data evidence.
3. Train synthetic generators only on the in-sample training window used by the candidate.
4. Generate augmentation data for training or pretraining only.
5. Evaluate the augmented policy on real validation data using the same promotion packet rules as non-augmented policies.
6. Use the 2025 held-out window only once per final locked candidate.
7. Treat synthetic generation as a feature/source family with its own ablation id, cost, risk, and failure modes.

Recommended Project 3 integration artifacts:

- `40_PHASE_4_SYNTHETIC_DATA_AUGMENTATION.md` - deferred optional phase plan.
- `experiments/design/synthetic_augmentation_protocol.md` - exact protocol for train-only generator fitting, augmentation ratios, and real-data validation.
- `experiments/design/synthetic_generator_ablation_plan.md` - baseline-vs-augmentation comparisons by generator family.
- `experiments/synthetic_data/` - generated data, generator metadata, quality reports, and downstream utility reports.

High-level generator priority:

| Priority | Generator family | Why |
|---:|---|---|
| P0 | Moving/stationary block bootstrap over transformed OHLCV primitives | Strong baseline, cheap, preserves local dependence, hard to fool yourself with. |
| P0 | Regime-conditional bootstrap | Low-risk extension; useful for high-volatility, trend, range, and drawdown regimes. |
| P1 | GARCH/EGARCH/GJR-style returns + empirical OHLC range/volume model | Classic financial baseline for volatility clustering and fat tails. |
| P1 | TimeVAE / time-causal VAE | Stable neural baseline, easier to test than GANs, useful before adversarial models. |
| P2 | TimeGAN / COT-GAN / Sig-Wasserstein GAN | Potentially powerful but unstable; only after baseline evaluators are trustworthy. |
| P2 | Financial diffusion models | Promising SOTA lane, but GPU-heavy and easy to overfit; defer until the protocol is proven. |

Absolute prohibition:

- Do not train the generator on validation or held-out data.
- Do not directly synthesize technical indicators as independent columns.
- Do not use synthetic data to claim live-trading performance.
- Do not select generators by looking at Stage C/2025 held-out results.
- Do not promote a synthetic-augmented model unless it beats the same real-data-only configuration under matched seeds, costs, assets, timeframes, and feature families.

## Post-Implementation Correction Addendum - 2026-05-03

The first `synthetic-datagen` implementation proved the plugin path works, but also exposed two failure modes that future Copilot/Spec Kit agents must handle as hard requirements:

1. **Generated Project 3 training panels must exclude Stage C rows.**
   - Raw source files may contain `2025-01-01+` data for storage.
   - Generator fitting, validation, augmentation panels, downstream training configs, and generator-selection logic must not consume or emit `2025-01-01+` rows in Project 3 mode.
   - Use `project3_heldout_boundary = 2025-01-01 00:00:00` separately from any downstream train/validation boundary such as `2021-09-28`.

2. **Quality gates must fail closed.**
   - Algebraic validity, distribution gates, and memorization gates are all fatal by default.
   - If any gate fails, write `project3_valid_for_training = false`, append a ledger `evaluate` row with `valid=false`, and do not create a training-ready augmented CSV.
   - If an old augmented CSV exists at the expected output path, quarantine it with an `.invalid_quality_gates` suffix.
   - A failed generator may remain as a diagnostic/stress artifact only.

Observed first-run result:

- `stationary_bootstrap_v1` passed OHLC algebra and simple return-distribution gates.
- It failed memorization gates (`duplicate_window_rate`, `nn_overlap_rate`, and `copied_subseq_ratio`).
- Therefore its first ETHUSDT 4h output is diagnostic-only and must not be used for SAC/PPO/DQN training until the generator or thresholds are explicitly redesigned and re-approved.

## How to use this prompt

Use this as a staged prompt sequence for GitHub Spec Kit or a Copilot agent working inside `github.com/harveybc/synthetic-datagen`.

Recommended sequence:

1. Initialize Spec Kit in the existing repo if it is not already initialized.
2. Paste the Constitution section into `/speckit.constitution`.
3. Paste the Feature Specification section into `/speckit.specify`.
4. Paste the Technical Plan section into `/speckit.plan`.
5. Run `/speckit.clarify` with the Clarification Focus section.
6. Run `/speckit.tasks`.
7. Run `/speckit.implement`, but implement in phases and validate after each phase.

---

# 1. Constitution Prompt

```text
/speckit.constitution

Act as a senior Python software architect, machine-learning engineer, quantitative finance researcher, and scientific software quality specialist. This repository is a plugin-first synthetic time-series data generation system for financial research. All work must preserve existing behavior and must extend the codebase in a backward-compatible manner.

Core engineering principles:

1. Plugin-first architecture
   - All new model, preprocessing, reconstruction, evaluation, and optimization behavior must be exposed through Python entry-point plugin groups.
   - Do not hard-code plugin implementations into the CLI dispatcher.
   - Existing plugin groups and existing plugins must continue to work.
   - Add new plugin groups only when the behavior is genuinely cross-cutting and cannot be cleanly represented through the existing trainer/generator/evaluator/optimizer groups.

2. Backward compatibility
   - Do not break the existing `typical_price` workflow.
   - Existing commands for train, generate, evaluate, and optimize must remain valid.
   - Existing pyproject entry points must remain valid.
   - Existing tests must continue passing.

3. Configuration compatibility
   - Preserve and improve config merging behavior similar to Harvey's plugin repositories.
   - The final effective configuration must be deterministic, inspectable, serializable, and saveable.
   - Merge precedence must be explicit and tested:
     plugin default parameters < repository defaults < local/remote config file < CLI explicit args < unknown CLI overrides.
   - Unknown CLI args must be parsed as override keys when safe.
   - Every plugin may expose `plugin_params` and those defaults must be included in the merge pipeline.
   - The implementation must log or report the final effective config without exposing secrets.

4. Financial-data correctness
   - Do not generate deterministic technical indicators directly as independent synthetic columns.
   - Generate only primitive financial paths and context variables first.
   - Primitive market fields are `DATE_TIME`, `OPEN`, `HIGH`, `LOW`, `CLOSE`, and `VOLUME`.
   - `typical_price` is derived from OHLC and must be recomputed.
   - Returns, log returns, moving averages, MACD, RSI, stochastic indicators, Bollinger bands, ATR/NATR, OBV, VWAP, MFI, rolling moments, realized variance, autocorrelations, Hurst proxies, z-scores, and regime flags are deterministic or semi-deterministic feature-engineering outputs and must be recomputed by a causal feature engine after synthetic OHLCV reconstruction.

5. No leakage
   - All transforms, scalers, seasonal profiles, regime labelers, and model parameters must be fit on the training split only.
   - Validation and held-out periods must never be used to fit a generator, transform, scaler, or feature selector.
   - The synthetic-data generator must never be trained on data that belongs to a downstream RL held-out period.
   - Generated validation or generated held-out data must never be used as evidence of live trading performance.

6. Constraint-preserving generation
   - Generated prices must be positive.
   - Generated volume must be non-negative.
   - Generated OHLC bars must satisfy `HIGH >= max(OPEN, CLOSE)` and `LOW <= min(OPEN, CLOSE)`.
   - These constraints must be enforced by parameterization and by validation tests, not only by post-hoc clipping.

7. Scientific evaluation
   - Synthetic quality must be evaluated with algebraic validity, stylized financial facts, distributional distances, memorization/privacy checks, and downstream utility.
   - Distribution similarity alone is not sufficient.
   - The decisive utility test is real-data validation performance of downstream models or RL policies trained with and without synthetic augmentation.

8. Reproducibility
   - Every generator must be seed-deterministic when configured for deterministic generation.
   - Every output must include metadata: git commit if available, plugin names, plugin versions, config hash, input data hashes, split boundaries, random seed, training period, and generation period.

9. Testing and quality
   - Use pytest.
   - Add unit tests for config merging, plugin discovery, OHLC reconstruction, algebraic validation, train-only transforms, deterministic seeds, and backward compatibility.
   - Add integration tests with small synthetic fixtures.
   - Add no network dependency to tests.
   - Add pydoc-compatible docstrings to new public classes/functions and concise inline comments for each important logical operation.

10. GPU and runtime safety
   - Heavy TensorFlow/PyTorch jobs must be optional and must respect GPU memory-growth settings.
   - Provide CPU-safe baseline generators first.
   - If GPU lockfile infrastructure is available in the runtime environment, the implementation must be compatible with it and must not bypass it.

11. Implementation discipline
   - Inspect the repository before editing.
   - Do not replace existing files wholesale unless necessary.
   - Modify the smallest set of files that provides a coherent plugin suite.
   - Do not paste unchanged code in final summaries.
   - Deliver a clear list of changed files, new files, tests, and validation results.
```

---

# 2. Feature Specification Prompt

```text
/speckit.specify

Build a new financial OHLCV synthetic-data generator plugin suite for `github.com/harveybc/synthetic-datagen`.

The repository currently generates synthetic `typical_price` time series with plugin-based trainers, generators, evaluators, and optimizers. This feature must extend the repository so it can generate Project-3-compatible synthetic financial market paths from multiyear OHLCV data while preserving existing behavior.

Primary user story:

As a quantitative ML researcher working on algorithmic trading, I want to train synthetic-data generators on 8 years of real OHLCV-like financial data and generate valid synthetic market paths that are similar to real data, causally safe, reproducible, and useful for downstream RL/predictor training, without directly generating inconsistent technical-indicator columns.

Input data characteristics:

- Real input files may be CSV or Parquet.
- Tables contain `DATE_TIME`, `typical_price`, `OPEN`, `HIGH`, `LOW`, `CLOSE`, `VOLUME`, and many derived columns.
- Many columns are deterministic rolling or technical functions of OHLCV, including returns, log returns, SMA/EMA ratios, MACD, RSI, stochastic oscillators, Williams %R, CCI, ROC, momentum, Bollinger bands, ATR/NATR, historical volatility, EMA crosses, trend slopes, OBV, volume ratios, VWAP, MFI, rolling mean/std/skew/kurtosis, realized variance, autocorrelations, volatility-regime flags, Hurst proxies, and z-score features.
- The generator must classify columns into primitive, deterministic-derived, and optional/contextual fields.

Required product behavior:

0. Project 3 synthetic augmentation mode
   - The first release must support a Project 3 mode but must not assume Project 3 is the only consumer.
   - Project 3 mode must accept an input CSV like:
     - `preprocessor/examples/data/project3/ethusdt_4h_tech_stat_full_model_ready.csv`
     - `experiments/stage_a_screening/inputs/<asset>/<timeframe>/<preset>/train.csv`
   - Project 3 mode must explicitly record:
     - `asset`
     - `timeframe`
     - `feature_preset`
     - `source_train_start`
     - `source_train_end`
     - `heldout_boundary`
     - `generator_train_start`
     - `generator_train_end`
     - `augmentation_ratio`
     - `generator_family`
   - If any input row is on or after the configured heldout boundary, generator training must fail unless an explicit `allow_non_research_mode=true` flag is set. That flag must never be used for Project 3.

1. Primitive-first generation
   - Generate transformed primitive variables only:
     - close-to-close log return
     - open-to-previous-close log gap
     - nonnegative high distance above max(open, close)
     - nonnegative low distance below min(open, close)
     - log1p volume or volume residual
   - Reconstruct OHLCV from generated transformed variables.
   - Recompute `typical_price` and all deterministic features after reconstruction.

2. Valid OHLCV reconstruction
   - Implement a reusable OHLCV reconstruction component that guarantees:
     - positive OPEN, HIGH, LOW, CLOSE
     - nonnegative VOLUME
     - HIGH >= max(OPEN, CLOSE)
     - LOW <= min(OPEN, CLOSE)
   - Use a mathematically safe parameterization such as exponentials or softplus-transformed range distances.

3. Plugin suite
   - Add or extend plugin types as needed while preserving the existing plugin loader pattern.
   - Required plugin concepts:
     - schema plugin or schema utility for primitive/derived/contextual column classification
     - transformer/preprocessor plugin for train-only fitting and transformed primitive-window creation
     - trainer plugins for baseline and ML generators
     - generator plugins for sampling and OHLCV reconstruction
     - evaluator plugins for financial validity and utility metrics
     - optional optimizer plugin support for hyperparameter optimization
   - Existing `sdg.trainer`, `sdg.generator`, `sdg.evaluator`, and `sdg.optimizer` groups must remain usable.
   - Suggested new entry-point groups, only if needed:
     - `sdg.transformer`
     - `sdg.reconstructor`
     - `sdg.feature_engine`
     - `sdg.pipeline`

4. Minimum generator implementations
   - Implement a CPU-safe stationary or moving-block bootstrap OHLCV generator as the mandatory baseline.
   - Implement a CPU-safe GARCH-like baseline if feasible without unstable dependencies; otherwise provide a clean optional adapter and skip gracefully when dependency is unavailable.
   - Implement a conditional TimeVAE/CVAE trainer/generator if TensorFlow is already available and the implementation can remain testable with small fixtures.
   - Add architecture hooks for future Sig-Wasserstein GAN, COT-GAN, and diffusion generators, but do not overbuild them in this first implementation.

5. Evaluation
   - Implement an algebraic evaluator for OHLCV and recomputed-feature consistency.
   - Implement a stylized-facts evaluator covering return distribution, skew/kurtosis, tail quantiles, volatility clustering, autocorrelation of returns, autocorrelation of absolute/squared returns, drawdown distribution, volume distribution, and volume-volatility relationships.
   - Implement distributional distance metrics such as KS distance, Wasserstein distance, MMD over windows, ACF distance, correlation-matrix distance when multivariate data is available, and drawdown-distribution distance.
   - Implement a memorization evaluator with nearest-neighbor distance, duplicate-window count, longest copied subsequence, and real-vs-synthetic classifier AUC using simple train/test splits.
   - Preserve the existing predictive-utility evaluation concept, but add a financial-utility interface that can later call external predictor or RL pipelines.
   - Add a downstream augmentation evaluator interface:
     - real_train_only
     - synthetic_train_only
     - real_plus_synthetic_0_25x
     - real_plus_synthetic_0_50x
     - real_plus_synthetic_1_00x
     - synthetic_pretrain_then_real_finetune
   - The evaluator must report whether synthetic augmentation improves real validation performance versus the matched real-only baseline. It must not treat synthetic evaluation data as promotion evidence.

6. Multi-timeframe support
   - Prefer generating base-resolution synthetic OHLCV, such as 5m, then aggregating into 15m, 1h, and 4h.
   - Provide a deterministic OHLCV aggregator utility:
     - OPEN = first open
     - HIGH = max high
     - LOW = min low
     - CLOSE = last close
     - VOLUME = sum volume
     - DATE_TIME alignment must be explicit and tested.

7. Feature recomputation
   - Add a feature-engine adapter interface that can either:
     - call an existing Project 3 feature pipeline if configured; or
     - recompute a minimal local set for tests and validation: typical_price, returns, log_returns, rolling mean/std, realized variance, ATR-like range, and simple volume ratios.
   - Do not attempt to reimplement the entire Project 3 feature library in this repo unless a configured external feature-engine path is provided.

8. CLI and config behavior
   - Existing CLI modes must remain valid.
   - Add config fields for financial generation without breaking existing `typical_price` configs.
   - Support config loading and saving.
   - Add a robust config merger if the repo does not already have one.
   - Preserve the pattern where plugins can define defaults through `plugin_params` and the final config is produced by merging plugin params, repository defaults, config file values, CLI args, and unknown CLI overrides.
   - Add `--list_plugins` or equivalent discovery output if feasible.

9. Outputs
   - Generated synthetic OHLCV file in CSV or Parquet.
   - Optional recomputed feature file.
   - JSON metrics report.
   - JSON metadata report.
   - Saved model or fitted state for generators that require training.
   - Saved effective config.

10. Acceptance criteria
   - Existing `typical_price` train/generate/evaluate tests still pass.
   - New financial baseline generator can train on a small OHLCV fixture and generate a valid synthetic OHLCV file.
   - Generated OHLCV passes algebraic validity tests with zero violations.
   - Deterministic features are recomputed, not independently generated.
   - Seed determinism is verified.
   - Config merging precedence is verified by tests.
   - Plugin loading and entry-point discovery are verified by tests.
   - Train-only preprocessing is verified by tests.
   - All new outputs include metadata and config hash.
   - The implementation does not require network access.
   - Project 3 mode rejects any training input crossing the configured heldout boundary.
   - A generated synthetic file includes an audit trail tying it to source input hash, generator config hash, generator seed, and train-window boundaries.
   - A synthetic-augmentation report compares real-only versus augmented training on the same real validation window, or explicitly reports that downstream utility was not run.
```

---

# 3. Technical Plan Prompt

```text
/speckit.plan

Use Python 3.10+ and preserve the repository's existing package style. The implementation must be backward-compatible with the current `sdg` CLI and entry-point architecture.

Technical architecture:

1. Keep existing app structure
   - Preserve `app/main.py`, `app/cli.py`, `app/config.py`, and `app/plugin_loader.py` behavior unless a backward-compatible refactor is needed.
   - If `app/config_merger.py` does not exist, add it.
   - If the current config merge is too simple, refactor it into a tested merge pipeline without breaking existing CLI behavior.

2. Add financial plugin modules under `sdg_plugins/`

Suggested structure:

- `sdg_plugins/schema/financial_ohlcv_schema.py`
- `sdg_plugins/transformer/ohlcv_transformer.py`
- `sdg_plugins/reconstructor/ohlcv_reconstructor.py`
- `sdg_plugins/aggregator/ohlcv_timeframe_aggregator.py`
- `sdg_plugins/trainer/stationary_bootstrap_ohlcv_trainer.py`
- `sdg_plugins/generator/stationary_bootstrap_ohlcv_generator.py`
- `sdg_plugins/trainer/garch_ohlcv_trainer.py` if feasible as optional dependency
- `sdg_plugins/generator/garch_ohlcv_generator.py` if feasible as optional dependency
- `sdg_plugins/trainer/conditional_timevae_ohlcv_trainer.py` if feasible with existing TensorFlow dependency
- `sdg_plugins/generator/conditional_timevae_ohlcv_generator.py` if feasible with existing TensorFlow dependency
- `sdg_plugins/feature_engine/minimal_financial_feature_engine.py`
- `sdg_plugins/evaluator/ohlcv_algebraic_evaluator.py`
- `sdg_plugins/evaluator/financial_stylized_facts_evaluator.py`
- `sdg_plugins/evaluator/financial_distribution_evaluator.py`
- `sdg_plugins/evaluator/memorization_evaluator.py`
- `sdg_plugins/evaluator/financial_utility_evaluator.py`
- `sdg_plugins/pipeline/financial_scenario_pipeline.py` if a pipeline plugin is needed.

3. Add entry points in `pyproject.toml`

Preserve existing entry points and add only the new ones required. Use names that are explicit and stable, such as:

- `stationary_bootstrap_ohlcv_trainer`
- `stationary_bootstrap_ohlcv_generator`
- `ohlcv_algebraic_evaluator`
- `financial_stylized_facts_evaluator`
- `financial_distribution_evaluator`
- `memorization_evaluator`
- `minimal_financial_feature_engine`
- `ohlcv_transformer`
- `ohlcv_reconstructor`
- `financial_scenario_pipeline`

4. Config model

Add financial config keys while preserving existing defaults:

- `data_format`: csv | parquet | auto
- `datetime_column`: DATE_TIME
- `primitive_columns`: [OPEN, HIGH, LOW, CLOSE, VOLUME]
- `derived_columns_policy`: recompute_only
- `generated_columns`: primitive_ohlcv_only
- `financial_mode`: false by default for backward compatibility
- `asset_id`
- `timeframe`
- `base_timeframe`
- `target_timeframes`
- `train_start`, `train_end`, `validation_start`, `validation_end`, `heldout_start`, `heldout_end`
- `fit_transforms_on`: train_only
- `transform_plugin`
- `reconstructor_plugin`
- `feature_engine_plugin`
- `pipeline_plugin`
- `volume_transform`: log1p_residual | log1p
- `seasonality_buckets`: hour_of_day, day_of_week, session, none
- `window_size`
- `block_length_mean`
- `seed`
- `deterministic_training`
- `metadata_file`
- `synthetic_metadata_file`
- `generated_feature_file`
- `metrics_file`
- `save_config`
- `project3_mode`: false by default
- `heldout_boundary`: optional, required when `project3_mode=true`
- `augmentation_ratios`: [0.25, 0.5, 1.0]
- `synthetic_use_case`: augmentation | pretraining | stress_test | diagnostics
- `generator_train_window_policy`: train_only
- `reject_if_input_crosses_heldout`: true
- `generator_family_id`
- `synthetic_ablation_id`
- `real_validation_report`
- `downstream_utility_report`

5. Transformation rules

Implement train-only fitting for:

- robust scaling of transformed primitive variables
- optional volume seasonality profile
- optional regime labels only if they are derived from train data

Use transformed primitive variables:

- `r_close_t = log(CLOSE_t / CLOSE_{t-1})`
- `r_open_t = log(OPEN_t / CLOSE_{t-1})`
- `d_high_t = log(HIGH_t / max(OPEN_t, CLOSE_t))`, constrained nonnegative
- `d_low_t = log(min(OPEN_t, CLOSE_t) / LOW_t)`, constrained nonnegative
- `v_t = log1p(VOLUME_t)` or seasonality-adjusted residual

6. Reconstruction rules

Reconstruct:

- `OPEN_t = previous_close * exp(r_open_t)`
- `CLOSE_t = previous_close * exp(r_close_t)`
- `HIGH_t = max(OPEN_t, CLOSE_t) * exp(nonnegative_high_distance)`
- `LOW_t = min(OPEN_t, CLOSE_t) * exp(-nonnegative_low_distance)`
- `VOLUME_t = expm1(nonnegative_log_volume)` or inverse residual transform

Validate all bars after reconstruction.

7. Baseline bootstrap implementation

Implement stationary or moving-block bootstrap over transformed primitive windows. It must:

- fit on train-transformed windows only
- sample variable or fixed-length blocks with deterministic RNG
- stitch transformed samples into a synthetic transformed path
- reconstruct OHLCV from an initial price
- emit metadata and fitted-state file

8. Optional GARCH implementation

Implement only if it can be done cleanly:

- Prefer optional dependency handling.
- If unavailable, plugin must fail gracefully with a clear message and tests must not require it.
- Student-t innovations are preferred over Gaussian innovations.

9. Optional TimeVAE/CVAE implementation

Implement only if it can be done with a small testable architecture:

- Use existing TensorFlow dependency if already present.
- Ensure GPU memory growth is configured before TensorFlow initializes.
- Provide tiny fixture tests with very few epochs or mocked training.
- Do not make full test suite depend on heavy training.

10. Evaluation architecture

Add evaluators that can run independently on real and synthetic files.

Algebraic evaluator:

- validates OHLC constraints
- validates positivity and nonnegative volume
- validates no NaN outside warm-up windows
- validates recomputed `typical_price`

Stylized-facts evaluator:

- return moments and quantiles
- volatility clustering
- ACF of returns and squared/absolute returns
- drawdown distribution
- volume distribution
- volume-volatility correlation

Distribution evaluator:

- KS distance
- Wasserstein distance
- MMD over windows if feasible
- ACF distance
- drawdown distance

Memorization evaluator:

- nearest-neighbor window distance
- duplicate-window count
- longest copied subsequence
- simple real-vs-synthetic classifier AUC

Utility evaluator:

- preserve existing predictive evaluator concept
- provide interface to downstream predictor or RL evaluation but do not require external repos in tests
- include a no-op/mock downstream runner for tests
- require any real downstream utility report to identify:
  - downstream repo or command
  - train data source
  - validation data source
  - augmentation ratio
  - seed
  - cost scenario, if applicable
  - matched real-only baseline id
  - whether the augmented model beats the real-only baseline

11. Testing plan

Add tests:

- `tests/unit/test_financial_schema.py`
- `tests/unit/test_ohlcv_transformer.py`
- `tests/unit/test_ohlcv_reconstructor.py`
- `tests/unit/test_config_merger_financial.py`
- `tests/unit/test_plugin_loader_financial.py`
- `tests/unit/test_stationary_bootstrap_ohlcv.py`
- `tests/unit/test_ohlcv_evaluators.py`
- `tests/unit/test_project3_heldout_boundary_guard.py`
- `tests/unit/test_synthetic_augmentation_report_schema.py`
- `tests/integration/test_financial_generate_cli.py`
- `tests/regression/test_typical_price_backward_compatibility.py`

Each test must use tiny local fixtures only.

12. Documentation

Add or update:

- README section for financial OHLCV generation
- example config under `examples/config/financial_ohlcv_bootstrap_config.json`
- small fixture under `examples/data/financial_ohlcv_sample.csv`
- documentation describing primitive vs derived columns
- documentation describing no-leakage rules
- documentation describing evaluation reports

13. Implementation phases

Phase A: repo inspection and tests for existing behavior.
Phase B: config merger and plugin discovery hardening.
Phase C: schema, transformer, reconstructor, aggregator.
Phase D: stationary bootstrap trainer/generator.
Phase E: algebraic and stylized-facts evaluators.
Phase F: CLI integration and example configs.
Phase G: Project 3 heldout-boundary guard and augmentation-report schema.
Phase H: optional GARCH and TimeVAE/CVAE hooks.
Phase I: documentation and final validation.

Do not implement optional neural generators before Phases A-G are passing.
```

---

# 4. Clarification Focus Prompt

```text
/speckit.clarify

Focus clarification on these risks:

1. Confirm the exact merge precedence and whether plugin defaults should be lower priority than repository defaults.
2. Confirm whether new plugin groups are acceptable or whether everything must remain inside `sdg.trainer`, `sdg.generator`, `sdg.evaluator`, and `sdg.optimizer`.
3. Confirm whether the first implementation should include only CPU-safe bootstrap/GARCH baselines or also a minimal TensorFlow CVAE.
4. Confirm whether generated output should be CSV only, Parquet only, or both.
5. Confirm whether the feature-engine adapter should call an external Project 3 feature-engine path or only produce a minimal local feature set for this repo.
6. Confirm whether 2025 or any downstream held-out period must be explicitly excluded by config validation.
7. Confirm whether the system should support multi-asset conditioning in the first release or single-asset generation only with future hooks.
8. Confirm whether GPU lockfile integration is available in this repository or should be implemented as an optional no-op-compatible utility.
9. Confirm whether Project 3 mode should be enabled in the first implementation or only documented with a config example.
10. Confirm the default augmentation ratios to test before using generated data in downstream RL/predictor training.
11. Confirm whether synthetic data should be appended to real training rows, used for pretraining only, or evaluated in both modes.
12. Confirm whether generator model selection must be based on real validation utility first, synthetic quality metrics second.
```

---

# 5. Implementation Guardrails Prompt

```text
Before implementation, inspect these files and summarize their current behavior:

- `pyproject.toml`
- `app/main.py`
- `app/cli.py`
- `app/config.py`
- `app/plugin_loader.py`
- all existing trainer/generator/evaluator/optimizer plugins
- existing tests

Then implement only the smallest backward-compatible changes required.

Critical guardrails:

- Do not remove or rename existing entry points.
- Do not break existing CLI commands.
- Do not train on validation or held-out data.
- Do not directly generate deterministic technical indicators.
- Do not add network dependencies.
- Do not make heavy TensorFlow training mandatory for tests.
- Do not silently clip invalid OHLCV bars; enforce validity by construction and report any validation failures.
- Do not swallow plugin-load errors without showing plugin group, plugin name, and available alternatives.
- Do not output secrets or credentials in config reports.
- Do not let synthetic-data quality metrics override downstream real-validation performance.
- Do not generate or evaluate synthetic data from rows on or after the configured heldout boundary in Project 3 mode.
- Do not add advanced GAN/diffusion implementations until the CPU bootstrap baseline, evaluators, and heldout guards are tested.
```

---

# 6. Expected Final Delivery Prompt

```text
When finished, provide a concise engineering report with:

1. Changed files and new files.
2. New plugin entry points.
3. Effective config merge order.
4. Exact CLI examples for:
   - training a financial OHLCV bootstrap generator
   - generating synthetic OHLCV
   - evaluating algebraic validity
   - evaluating stylized facts
5. Generated output schema.
6. Test results.
7. Known limitations.
8. Future extension hooks for GARCH, CVAE/TimeVAE, Sig-Wasserstein GAN, COT-GAN, and diffusion.
9. Confirmation that existing `typical_price` behavior remains backward-compatible.
10. Confirmation that deterministic technical indicators are recomputed, not independently generated.
11. Confirmation that Project 3 mode rejects heldout-boundary violations.
12. A recommendation on whether this implementation is ready for Project 3 Phase 4 experiments or only ready for standalone generator tests.

Do not paste unchanged source files in the final response. Summarize only what changed and where.
```
