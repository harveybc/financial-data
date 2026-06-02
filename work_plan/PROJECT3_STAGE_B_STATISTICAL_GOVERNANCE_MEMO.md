# Project 3 Stage B Statistical Governance: DSR, PBO/CSCV, Reality Check, SPA, and RL Seed Uncertainty

**Role assumed:** skeptical senior quantitative-finance researcher, empirical deep-RL evaluation reviewer, and statistical backtesting-governance auditor.  
**Target system:** Project 3 financial-data / RL trading experiment.  
**Primary candidate motivating this memo:** `ETHUSDT 4h + SAC + tech_stat`.  
**Hard firewall:** no data, labels, prompts, generator fitting, tuning, model selection, threshold selection, report drafting, or validation logic may use observations at or after `2025-01-01`, except the final locked Stage C evaluation.  
**Scope constraint:** do not change PPO/SAC/DQN algorithms. Statistical governance evaluates whether data, feature, source, synthetic, and training-protocol variants genuinely improve fixed RL configurations.

---

## 0. Assumptions and project-specific interpretation

1. **Project 3 is data/feature-centric.** PPO, SAC, and DQN are held fixed. The experiment varies trading asset, simulation timeframe, feature input set, and feature-engineering technique.
2. **Stage A is broad screening.** It can use approximate but conservative governance to kill weak candidates early.
3. **Stage B is decision-grade validation.** It must use per-step/per-bar returns, paired seeds, multiple-testing accounting, DSR, PBO/CSCV where feasible, and family-level Reality Check / SPA tests before a candidate can approach Stage C.
4. **Stage C is not a validation set.** It is a single locked real held-out rollout starting `2025-01-01`.
5. **Synthetic data is training-only.** Synthetic-only performance is diagnostic and cannot become evidence of tradability.
6. **Returns are not IID.** Assume autocorrelation, volatility clustering, skewness, kurtosis, and non-normal tails.
7. **Trials are not independent.** Assets, timeframes, feature families, seeds, cost scenarios, and synthetic protocols are correlated, but correlation does not eliminate the need to count them.
8. **Stage B promotion must be fail-closed.** Missing return streams, missing ledger entries, unpaired seeds, missing cost runs, missing trial counts, or any possible Stage C contamination should block promotion.

Internal Project 3 references used in this memo:

- `30_PHASE_3_OVERVIEW.md`: fixed PPO/SAC/DQN, strict held-out discipline, pre-registration, staged Stage A/B/C evaluation, and DSR requirement.
- `40_PHASE_4_SYNTHETIC_DATA_AUGMENTATION.md`: synthetic data may augment training, but real validation remains the judge; synthetic-only metrics are diagnostic.
- `STAGE_2.1_DELIVERABLE.md`: cross-source alignment uses point-in-time backward/as-of merge and no interpolation.
- `STAGE_2.2_DELIVERABLE.md`, `STAGE_2.3_DELIVERABLE.md`, `STAGE_2.4_DELIVERABLE.md`: large technical/statistical, decomposition, and learned feature families are available, creating a large multiple-testing surface.

---

## 1. Executive summary

### 1.1 What must be implemented before trusting Stage B

1. **Per-run return stream storage.** Every Stage B run must emit per-step/per-bar net returns after costs, gross returns, equity curve, position, action, turnover, cost, slippage, timestamp, run ID, seed, asset, timeframe, algorithm, feature preset, and cost scenario.
2. **A complete multiple-testing ledger.** Every attempted variant must be registered: assets, timeframes, algorithms, seeds, feature presets, feature families, source families, cost scenarios, reward/action variants, synthetic generator families, augmentation ratios, and pretraining schedules.
3. **Deflated Sharpe Ratio from return streams.** Stage B cannot rely on a headline annualized Sharpe from summary logs. DSR must use per-period returns, skewness, kurtosis, sample length/effective sample length, and a declared trial count.
4. **Paired seed-level uncertainty.** At least 5 paired seeds are required for Stage B; 10 paired seeds are preferred for promotion discussion. A single lucky seed must not promote a candidate.
5. **PBO/CSCV or PBO-lite.** For each candidate family, estimate whether in-sample selection rank degrades out-of-sample across contiguous/purged validation folds. Random k-fold is not acceptable.
6. **Family-level White Reality Check or Hansen SPA.** For each feature/source/synthetic/training-protocol family, test whether any alternative beats a matched baseline after data snooping adjustment.
7. **Cost/slippage stress gates.** A candidate must remain viable under base and pessimistic cost scenarios. Zero-cost wins are diagnostic only.
8. **Matched baselines.** Every alternative must be compared to a matched baseline with the same asset, timeframe, algorithm, seed set, train/validation split, reward/action configuration, and cost scenario.
9. **Fail-closed evaluator architecture.** If required inputs are missing, the governance evaluator must output `promotion_allowed = false`.
10. **Immutable report artifacts.** Stage B must produce `statistical_governance_report.json`, `statistical_governance_report.md`, `per_candidate_metrics.csv`, and `family_test_results.csv` with config hashes and code commit IDs.

### 1.2 What can remain approximate in Stage A

Stage A may use approximate governance if it is explicitly labeled as screening:

- Approximate annualized Sharpe / Sortino / Calmar.
- Coarse DSR proxy using raw trial count and sample skew/kurtosis.
- Three seeds if compute-constrained, provided no candidate is promoted to Stage C from Stage A.
- Simplified cost proxies, provided Stage B reruns full cost/slippage scenarios.
- PBO not required for every Stage A candidate, but the design must preserve enough return-stream metadata to support Stage B.

Stage A must not use approximation as promotion evidence. Its job is to reduce the search space.

### 1.3 What must be forbidden

The following must be hard failures:

1. Using `2025-01-01+` Stage C data for training, tuning, synthetic generation, feature selection, threshold selection, prompt context, statistical calibration, or report drafting.
2. Promoting a candidate from a leaderboard without paired seed uncertainty.
3. Selecting the best seed and ignoring weak seeds.
4. Reporting DSR without declaring the number of trials and how killed/failed variants were counted.
5. Running PBO/CSCV with random k-fold splits that break temporal dependence and leak future information.
6. Treating synthetic-only performance as evidence of tradability.
7. Tuning augmentation ratio, pretraining length, OOD threshold, cost model, or feature mask on validation and reporting only the winner.
8. Running White Reality Check / SPA after removing failed alternatives from the tested family.
9. Changing PPO/SAC/DQN hyperparameters inside Stage B while claiming the experiment isolates data/features.
10. Re-running Stage C after seeing Stage C results.

---

## 2. Deflated Sharpe Ratio implementation

### 2.1 Why DSR is required

The Deflated Sharpe Ratio is designed to correct Sharpe-ratio claims for two problems that Project 3 definitely has:

1. **Selection bias under multiple testing.** Project 3 tries many assets, timeframes, algorithms, seeds, feature presets, feature families, source families, synthetic generators, and training protocols.
2. **Non-normal returns.** Trading returns are usually skewed, fat-tailed, autocorrelated, and volatility-clustered.

DSR is not a magic proof of edge. It is a necessary but insufficient screen against false discoveries.

Primary references:

- Bailey and López de Prado, *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Bailey and López de Prado, *The Sharpe Ratio Efficient Frontier* / Probabilistic Sharpe Ratio — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643
- Lo, *The Statistics of Sharpe Ratios* — https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios

### 2.2 Exact inputs needed

Each Stage B run must emit a per-step returns file:

```text
per_run_returns.parquet

Required columns:
  timestamp
  run_id
  candidate_id
  asset
  timeframe
  algorithm
  feature_preset
  feature_family
  source_family
  seed
  cost_scenario
  step_index
  bar_return_gross
  bar_return_net
  equity_before
  equity_after
  position_before
  position_after
  action
  trade_notional
  turnover
  fee_cost
  slippage_cost
  funding_or_financing_cost
  synthetic_origin_present
  stage
  split_id
  git_commit
  config_hash
```

DSR should be computed from `bar_return_net`, not from cumulative return summaries. If the environment uses episodic returns, store both per-step returns and episode boundaries; DSR uses the full ordered per-step return series unless the Stage B evaluator explicitly aggregates by episode for a separate diagnostic.

### 2.3 Computing Sharpe from per-bar or per-step returns

For a single run:

```text
r_t = net strategy return at bar/step t after fees, slippage, funding/financing, and borrow/cash effects if modeled
rf_t = per-bar risk-free/cash return, often set to 0 for short-horizon crypto experiments unless cash yield is explicitly modeled
x_t = r_t - rf_t
SR_period = mean(x_t) / std(x_t)
SR_annual = SR_period * sqrt(bars_per_year)
```

Important implementation notes:

- Use sample standard deviation with `ddof=1`.
- Compute Sharpe on arithmetic per-period returns unless the evaluator explicitly defines log-return Sharpe. Do not mix arithmetic return PnL and log-return denominators.
- If volatility is zero or near zero, Sharpe is undefined. Fail closed rather than emitting infinity.
- For DSR / PSR formulas, use the **per-period Sharpe** and sample size. Annualized Sharpe is for reporting.
- Because returns are autocorrelated, report both naive annualized Sharpe and autocorrelation-adjusted/HAC or block-bootstrap confidence intervals.

### 2.4 Annualization constants

Use observed calendar-aware bar counts whenever possible. The constants below are acceptable defaults for complete data.

| Market / timeframe | Default bars per day | Default bars per year | Notes |
|---|---:|---:|---|
| Crypto 4h | 6 | 2,190 | 24/7 × 365. |
| Crypto 1h | 24 | 8,760 | 24/7 × 365. |
| Crypto 15m | 96 | 35,040 | 24/7 × 365. |
| FX 4h | ~6 for active weekdays | ~1,560 | Approx. 5 trading days × 24 hours × 52 weeks / 4. Prefer empirical calendar count. |
| FX 1h | ~24 for active weekdays | ~6,240 | Approx. 5 × 24 × 52. Prefer empirical calendar count. |
| FX 15m | ~96 for active weekdays | ~24,960 | Approx. 5 × 96 × 52. Prefer empirical calendar count. |

For FX, do **not** assume 24/7. Use the actual timestamp index or a trading-calendar/session mask:

```text
bars_per_year = median(number_of_valid_bars_per_calendar_year_in_training_data)
```

If missing bars are material, report `bars_per_year_observed` and `missing_bar_rate`.

### 2.5 Handling skewness, kurtosis, and serial dependence

DSR/PSR incorporate skewness and kurtosis through the estimated standard error of the Sharpe ratio. For return stream `x`:

```text
skew = E[((x - mean) / std)^3]
kurtosis = E[((x - mean) / std)^4]
```

Use non-excess kurtosis in the Bailey/López de Prado PSR/DSR denominator.

The common PSR form is:

```text
PSR(SR_hat, SR_benchmark) = Φ(
    (SR_hat - SR_benchmark) * sqrt(T - 1)
    / sqrt(1 - skew * SR_hat + ((kurtosis - 1) / 4) * SR_hat^2)
)
```

DSR replaces `SR_benchmark` with the expected maximum Sharpe threshold expected from `N` trials. A common threshold approximation is:

```text
SR_star = std(SR_trials) * [
    (1 - gamma_euler) * Φ^-1(1 - 1 / N)
    + gamma_euler * Φ^-1(1 - 1 / (N * e))
]
```

where `gamma_euler ≈ 0.5772`, `e` is Euler's number, and `SR_trials` are per-period Sharpe estimates across tested strategy variants.

Because Project 3 returns are serially dependent, the evaluator should also compute an effective sample size:

```text
T_eff = T / (1 + 2 * sum_{k=1..K} rho_k)
```

where `rho_k` are autocorrelations of net returns up to a predeclared lag `K`. Use `T_eff = min(T, max(30, T_eff))` as a conservative guard. Report both:

```text
DSR_naive_T
DSR_effective_T
```

Gate on the more conservative result unless the evaluator has a validated HAC/block-bootstrap Sharpe standard-error implementation.

### 2.6 How to set or estimate the number of trials

#### Conservative trial count

Use the raw number of strategy specifications that could have influenced candidate selection:

```text
N_raw = count_unique(
  asset,
  timeframe,
  algorithm,
  feature_preset,
  feature_family,
  source_family,
  reward_variant,
  action_space_variant,
  cost_model_variant,
  synthetic_generator_family,
  synthetic_ablation_id,
  training_protocol_id,
  augmentation_ratio,
  pretraining_schedule_id
)
```

Seed handling:

- If seeds are fixed and always aggregated, seeds are repeated measurements of one specification.
- If the best seed is selected or used in decision-making, each seed must count as a separate trial.
- If seed failures are hidden, the entire candidate should fail governance.

Killed, failed, blocked, and diagnostic runs:

- **Killed after metric inspection:** include in trial count.
- **Failed due infrastructure before producing metrics:** log but do not necessarily include in DSR; disclose separately.
- **Blocked before execution:** log but do not include in DSR.
- **Diagnostic runs that influenced later design:** include or disclose as exploratory researcher degrees of freedom.
- **Synthetic generator variants that produce training data:** include as training-protocol trials.
- **Synthetic-only quality diagnostics:** do not count as trading performance trials, but do count in the synthetic generator ledger.

#### Practical effective trial count

Because trials are correlated, report an effective trial count as a diagnostic, not as a way to hide search.

Recommended practical method:

1. Build a matrix of validation return streams or validation metric vectors for all candidate specifications.
2. Compute the correlation matrix `C` across strategy specifications.
3. Compute eigenvalues `λ_i` of `C`.
4. Estimate participation-ratio effective tests:

```text
N_eff_eigen = (sum(λ_i)^2) / sum(λ_i^2)
```

5. Clamp:

```text
N_eff = max(number_of_top_level_families, ceil(N_eff_eigen))
N_eff <= N_raw
```

Report both `DSR_N_raw` and `DSR_N_eff`. Promotion should prefer candidates that pass `N_raw`. A candidate passing only `N_eff` may continue to more seeds but should not be considered statistically clean.

### 2.7 How DSR should be interpreted for RL policies

For Project 3, DSR should be interpreted as:

```text
A probability-like measure that the observed validation Sharpe exceeds the Sharpe expected from multiple tested, non-normal-return strategy variants.
```

It is **not**:

- proof of live tradability;
- proof of causality;
- protection against market regime shift;
- protection against execution frictions not modeled;
- permission to touch Stage C repeatedly;
- a replacement for seed uncertainty, PBO/CSCV, cost stress, or baseline comparisons.

For RL specifically, the return stream is produced by a trained policy and a stochastic optimization process. Therefore DSR must be reported at both levels:

```text
run-level DSR: one seed / one policy instance
candidate-level DSR: aggregated across paired seeds, preferably using median or IQM return streams/metrics
family-level DSR: with trial count across all related candidates
```

### 2.8 Python-like pseudocode

```python
# Import numerical tools required for vectorized statistics.
import numpy as np  # numerical arrays and linear algebra
from scipy.stats import norm, skew, kurtosis  # distribution and moments

# Define a stable Sharpe calculation for one return stream.
def period_sharpe(net_returns: np.ndarray) -> float:  # compute per-period Sharpe from net returns
    x = np.asarray(net_returns, dtype=float)  # convert input to a numeric vector
    x = x[np.isfinite(x)]  # remove non-finite values before statistics
    if x.size < 30:  # require a minimum track record length
        return np.nan  # fail later if sample is too short
    sigma = np.std(x, ddof=1)  # compute sample volatility
    if sigma <= 1e-12:  # guard against zero-volatility artifacts
        return np.nan  # avoid infinite Sharpe ratios
    return float(np.mean(x) / sigma)  # return per-period Sharpe

# Estimate effective sample size using autocorrelation truncation.
def effective_sample_size(net_returns: np.ndarray, max_lag: int = 50) -> float:  # compute autocorrelation-adjusted T
    x = np.asarray(net_returns, dtype=float)  # convert to numeric vector
    x = x[np.isfinite(x)]  # keep finite returns only
    x = x - np.mean(x)  # center returns for autocorrelation
    t = x.size  # count observations
    if t < 30:  # enforce minimum sample length
        return float(t)  # return raw length for short diagnostics
    denom = float(np.dot(x, x))  # compute zero-lag covariance denominator
    if denom <= 1e-12:  # guard against degenerate returns
        return float(t)  # avoid division instability
    acf_sum = 0.0  # initialize autocorrelation sum
    for lag in range(1, min(max_lag, t - 1) + 1):  # iterate through allowed lags
        rho = float(np.dot(x[:-lag], x[lag:]) / denom)  # estimate autocorrelation at lag
        if rho < 0 and lag > 5:  # optional truncation after first meaningful negative region
            break  # stop adding noisy long-lag terms
        acf_sum += rho  # accumulate autocorrelation
    t_eff = t / max(1e-12, 1.0 + 2.0 * acf_sum)  # compute effective sample size
    return float(np.clip(t_eff, 30.0, float(t)))  # clamp to reasonable range

# Compute a DSR-like probability for one selected strategy.
def deflated_sharpe_ratio(  # compute DSR for a selected strategy
    selected_returns: np.ndarray,  # net returns for the selected run or aggregated candidate
    trial_sharpes: np.ndarray,  # per-period Sharpe ratios for all tested strategy specs
    n_trials: int,  # raw or effective number of trials
    use_effective_t: bool = True,  # select raw or effective sample size
) -> dict:  # return scalar metrics and diagnostics
    sr_hat = period_sharpe(selected_returns)  # compute selected per-period Sharpe
    x = np.asarray(selected_returns, dtype=float)  # convert selected returns to vector
    x = x[np.isfinite(x)]  # remove non-finite values
    t_raw = x.size  # store raw sample length
    t_used = effective_sample_size(x) if use_effective_t else float(t_raw)  # choose sample length
    g3 = float(skew(x, bias=False))  # estimate sample skewness
    g4 = float(kurtosis(x, fisher=False, bias=False))  # estimate non-excess kurtosis
    trial_srs = np.asarray(trial_sharpes, dtype=float)  # convert trial Sharpes to vector
    trial_srs = trial_srs[np.isfinite(trial_srs)]  # keep valid trial Sharpes only
    sr_std = float(np.std(trial_srs, ddof=1)) if trial_srs.size > 1 else 0.0  # estimate trial dispersion
    n = max(int(n_trials), 1)  # guard against invalid trial count
    euler_gamma = 0.5772156649015329  # Euler-Mascheroni constant
    if n <= 1 or sr_std <= 1e-12:  # handle no-search or degenerate dispersion
        sr_star = 0.0  # set benchmark threshold to zero
    else:  # compute expected maximum Sharpe threshold
        sr_star = sr_std * ((1.0 - euler_gamma) * norm.ppf(1.0 - 1.0 / n) + euler_gamma * norm.ppf(1.0 - 1.0 / (n * np.e)))  # DSR threshold
    denom = np.sqrt(max(1e-12, 1.0 - g3 * sr_hat + ((g4 - 1.0) / 4.0) * sr_hat * sr_hat))  # non-normal SR standard-error denominator
    z = (sr_hat - sr_star) * np.sqrt(max(1.0, t_used - 1.0)) / denom  # compute test statistic
    dsr = float(norm.cdf(z))  # map test statistic to probability scale
    return {  # return all required diagnostics
        "sr_period": float(sr_hat),  # per-period Sharpe
        "t_raw": int(t_raw),  # raw sample length
        "t_used": float(t_used),  # sample length used in DSR
        "skew": g3,  # skewness estimate
        "kurtosis_non_excess": g4,  # kurtosis estimate
        "n_trials": int(n),  # trial count used
        "sr_star": float(sr_star),  # deflated benchmark Sharpe
        "dsr": dsr,  # final DSR value
    }  # end diagnostics dictionary
```

### 2.9 Stage B acceptance criteria for DSR

Required:

```text
[ ] per-bar/per-step net returns exist for every seed and cost scenario
[ ] annualization constant is documented and calendar-aware
[ ] skewness and kurtosis are reported
[ ] raw trial count is reported
[ ] effective trial count is reported only as secondary diagnostic
[ ] DSR_N_raw and DSR_N_eff are both reported
[ ] candidate-level aggregation is seed-paired, not best-seed selected
```

Suggested gates:

```text
Strong promotion evidence:
  DSR_N_raw >= 0.95
  and net validation return > matched baseline
  and median seed beats matched baseline
  and cost stress survives

Conditional continuation:
  0.80 <= DSR_N_raw < 0.95
  or DSR_N_eff >= 0.95 but DSR_N_raw < 0.95
  -> require more seeds, more validation folds, or stricter baselines

Block promotion:
  DSR_N_raw < 0.80
  or DSR missing
  or trial count incomplete
  or selected run is a best-seed cherry-pick
```

---

## 3. PBO/CSCV implementation for time-series RL

### 3.1 Why naive random k-fold is not acceptable

Random k-fold is invalid for this setting because:

1. Adjacent bars share information through rolling indicators, volatility clustering, and market microstructure.
2. RL policies learn from temporally ordered episodes; randomizing bars destroys path structure.
3. Rolling features can leak future information if fold boundaries are not purged.
4. Ranking candidates on random folds overstates generalization under regime shift.

Use contiguous folds, purge windows, and embargo periods.

Primary reference:

- Bailey, Borwein, López de Prado, and Zhu, *The Probability of Backtest Overfitting* — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253

### 3.2 Recommended design: contiguous CSCV / PBO-lite

Full CSCV trains and tests over combinatorial splits. For Project 3 RL, full retraining per split may be expensive. Use a two-tier design:

#### Tier 1: Stage B PBO-lite from validation return streams

Use this for all Stage B candidates:

1. Take each candidate’s real-validation return stream.
2. Split validation into `S` contiguous folds.
3. Purge/embargo around fold boundaries based on max feature lookback and reward horizon.
4. For every combination of `S/2` folds, treat one side as selection/in-sample and the complement as out-of-sample.
5. Rank candidate specifications by in-sample metric.
6. Select the top in-sample candidate.
7. Measure its out-of-sample rank.
8. Compute PBO as the fraction of splits where the selected candidate’s OOS rank falls below the median.

This is not as strong as retraining policies in every split, but it directly measures whether validation ranking is unstable across time regimes.

#### Tier 2: Full walk-forward / purged CSCV for finalists

Use only for finalists if compute allows:

1. Define contiguous train/test fold combinations before Stage C.
2. Retrain candidate policies from scratch on fold-specific train data.
3. Evaluate on fold-specific test data.
4. Compute PBO using rank degradation.

Full fold-retraining is expensive but more faithful to the original PBO concept.

### 3.3 Fold counts for Project 3

Use time-blocks, not random bars.

| Data scale | Suggested folds | Notes |
|---|---:|---|
| ETHUSDT 4h, multi-year pre-2025 | `S = 8` or `S = 10` | Enough bars for contiguous folds; avoid too many small folds. |
| 1h crypto | `S = 10` to `S = 12` | More bars allow more folds, but regimes still matter. |
| 15m crypto/perp | `S = 12` to `S = 16` | Use day/week/month block structure, not tiny random folds. |
| FX 4h | `S = 6` to `S = 8` | Session gaps and weekends reduce effective samples. |
| FX 15m/1h | `S = 10` to `S = 12` | Use session-aware folds and avoid weekend artifacts. |

Purging rule:

```text
purge_bars = max(max_feature_lookback_bars, reward_horizon_bars, execution_settlement_lag_bars)
embargo_bars = max(purge_bars, ceil(0.01 * fold_length_bars))
```

For `tech_stat`, if features include 200/252-bar rolling windows, purge at least that lookback at fold boundaries.

### 3.4 Computing PBO from rank degradation

For each CSCV split:

```text
1. Compute in-sample metric for each candidate.
2. Select candidate with best in-sample metric.
3. Compute out-of-sample rank of that selected candidate.
4. Convert rank to relative rank ω in (0, 1).
5. Compute logit λ = log(ω / (1 - ω)).
6. Count overfit if λ < 0.
```

PBO is:

```text
PBO = mean(λ < 0)
```

Interpretation:

```text
PBO ≈ probability that the selected best-in-sample strategy degrades below median out-of-sample.
```

### 3.5 Handling multiple seeds and algorithms

Use a hierarchy:

```text
candidate_spec = (asset, timeframe, algorithm, feature_preset, source_family, training_protocol)
seed = repeated stochastic measurement of candidate_spec
```

Rules:

1. Do not rank individual seeds unless the project intends to deploy a single trained seed selected after validation.
2. Aggregate paired seeds per fold using median or IQM before candidate ranking.
3. Keep algorithm as part of the candidate specification; PPO/SAC/DQN are fixed algorithms but still alternatives in the tested family.
4. Report seed-level PBO only as diagnostic.

### 3.6 Python-like pseudocode

```python
# Import combinatorics and numeric tools.
from itertools import combinations  # generate CSCV fold combinations
import numpy as np  # numerical arrays

# Compute a robust metric on a return slice.
def fold_metric(returns: np.ndarray) -> float:  # evaluate one fold return stream
    x = np.asarray(returns, dtype=float)  # convert returns to numeric vector
    x = x[np.isfinite(x)]  # drop non-finite values
    if x.size < 30:  # require enough observations
        return np.nan  # return missing metric for too-short fold
    vol = np.std(x, ddof=1)  # compute sample volatility
    if vol <= 1e-12:  # guard against zero volatility
        return np.nan  # avoid undefined Sharpe
    return float(np.mean(x) / vol)  # use per-period Sharpe or replace with net utility

# Build contiguous fold indices with optional purge and embargo.
def make_contiguous_folds(timestamps, n_folds: int) -> list:  # define ordered folds
    indices = np.arange(len(timestamps))  # create integer index vector
    return np.array_split(indices, n_folds)  # split into contiguous blocks

# Aggregate seed returns for one candidate and fold.
def aggregate_seed_metric(candidate_returns_by_seed: dict, fold_indices: np.ndarray) -> float:  # aggregate seeds
    metrics = []  # store per-seed fold metrics
    for seed, returns in candidate_returns_by_seed.items():  # iterate over paired seeds
        metrics.append(fold_metric(np.asarray(returns)[fold_indices]))  # compute metric for seed
    metrics = np.asarray(metrics, dtype=float)  # convert to vector
    metrics = metrics[np.isfinite(metrics)]  # keep valid seed metrics
    if metrics.size == 0:  # fail if no seed metric exists
        return np.nan  # return missing aggregate
    return float(np.median(metrics))  # use median; IQM is also acceptable

# Estimate PBO from contiguous CSCV splits.
def estimate_pbo(candidates: dict, timestamps, n_folds: int = 8) -> dict:  # compute PBO over candidates
    folds = make_contiguous_folds(timestamps, n_folds)  # create contiguous folds
    if n_folds % 2 != 0:  # CSCV needs even number of folds
        raise ValueError("n_folds must be even for CSCV")  # fail closed
    lambdas = []  # store logit relative ranks
    split_records = []  # store audit details per split
    candidate_ids = list(candidates.keys())  # collect candidate IDs
    for train_fold_ids in combinations(range(n_folds), n_folds // 2):  # enumerate symmetric splits
        train_fold_ids = set(train_fold_ids)  # store train fold IDs as set
        test_fold_ids = set(range(n_folds)) - train_fold_ids  # define complement test folds
        train_idx = np.concatenate([folds[i] for i in sorted(train_fold_ids)])  # build train-like indices
        test_idx = np.concatenate([folds[i] for i in sorted(test_fold_ids)])  # build test-like indices
        is_scores = []  # collect in-sample scores
        oos_scores = []  # collect out-of-sample scores
        for cid in candidate_ids:  # iterate over candidates
            is_scores.append(aggregate_seed_metric(candidates[cid], train_idx))  # candidate IS score
            oos_scores.append(aggregate_seed_metric(candidates[cid], test_idx))  # candidate OOS score
        is_scores = np.asarray(is_scores, dtype=float)  # convert IS scores to vector
        oos_scores = np.asarray(oos_scores, dtype=float)  # convert OOS scores to vector
        if np.any(~np.isfinite(is_scores)) or np.any(~np.isfinite(oos_scores)):  # check data completeness
            continue  # skip incomplete split or fail closed in strict mode
        winner_pos = int(np.argmax(is_scores))  # select best in-sample candidate
        winner_oos_score = oos_scores[winner_pos]  # read winner OOS score
        rank_low_to_high = int(np.sum(oos_scores <= winner_oos_score))  # compute OOS rank position
        omega = rank_low_to_high / (len(candidate_ids) + 1.0)  # map rank to open interval proxy
        omega = float(np.clip(omega, 1e-6, 1.0 - 1e-6))  # prevent infinite logits
        lam = float(np.log(omega / (1.0 - omega)))  # compute logit rank statistic
        lambdas.append(lam)  # append split logit
        split_records.append({"winner": candidate_ids[winner_pos], "lambda": lam, "omega": omega})  # audit split
    lambdas = np.asarray(lambdas, dtype=float)  # convert lambdas to vector
    pbo = float(np.mean(lambdas < 0.0)) if lambdas.size else np.nan  # compute PBO fraction
    return {"pbo": pbo, "n_splits": int(lambdas.size), "lambdas": lambdas.tolist(), "splits": split_records}  # return report
```

### 3.7 Acceptance criteria and failure interpretations

Suggested Stage B PBO gates:

```text
Strong:
  PBO <= 0.10

Caution:
  0.10 < PBO <= 0.20
  -> allow only with strong DSR, seed stability, cost robustness, and family-test support

Fail:
  PBO > 0.20
  -> candidate likely selected from unstable validation ranking; require redesign or more evidence
```

Failure interpretations:

- **High PBO with high Sharpe:** likely selected from a noisy family.
- **Low PBO but low net return:** stable mediocrity; do not promote.
- **PBO inconclusive due few candidates:** report as diagnostic and rely more heavily on paired seeds, DSR, and SPA.
- **PBO improves only after deleting failed variants:** invalid; restore full tested family.

---

## 4. White Reality Check and Hansen SPA-style family tests

### 4.1 When to use them

Use White Reality Check or Hansen SPA when Project 3 asks:

```text
After trying many related alternatives, does any member of this family truly beat its matched baseline on real validation data?
```

Use them at family level, not for isolated one-off runs.

Examples:

- `tech_stat` vs `baseline_12` across assets/timeframes/seeds.
- `tech_stat_decomp` vs `tech_stat`.
- `learned_lstm` vs `tech_stat`.
- `crypto_full` vs `tech_stat` for crypto assets.
- `synthetic_pretrain_then_real_finetune` vs `real_only_compute_matched`.
- `regime_residual_bootstrap_v1` vs `stationary_bootstrap_v1` vs `real_only` for downstream validation, if synthetic variants are permitted.

Primary references:

- White, *A Reality Check for Data Snooping*, Econometrica 2000 — https://www.ssc.wisc.edu/~bhansen/718/White2000.pdf
- Hansen, *A Test for Superior Predictive Ability*, Journal of Business & Economic Statistics 2005 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569
- Politis and Romano, *The Stationary Bootstrap*, JASA 1994 — https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf

### 4.2 Null hypotheses in Project 3 language

White Reality Check null:

```text
Within the tested family, no alternative data/feature/source/synthetic/training-protocol variant has better expected real-validation performance than its matched baseline, after accounting for data snooping.
```

Hansen SPA null:

```text
No alternative in the tested family has superior predictive/trading ability relative to its matched baseline; the test is studentized and less sensitive to irrelevant or poor alternatives than White RC.
```

Recommended usage:

- Use White RC as conservative family-level screen.
- Use Hansen SPA as the preferred decision-support test when many weak/irrelevant alternatives are included.
- Report both if implementation cost is manageable.

### 4.3 Block bootstrap choice for dependent returns

Use paired performance differentials:

```text
d_{t,m} = utility_or_return_{t, alternative_m} - utility_or_return_{t, matched_baseline_m}
```

Then bootstrap the time index using stationary bootstrap or moving-block bootstrap. Stationary bootstrap is attractive because it resamples variable-length blocks and preserves weak dependence.

Recommended block-length policy:

```text
P0 implementation:
  expected_block_length = max(5, ceil(1.5 * T^(1/3)))

P1 implementation:
  automatic block-length selection or calibration from ACF decay

Always report:
  block_length
  bootstrap_reps
  random_seed
```

Use at least:

```text
bootstrap_reps = 2,000 for Stage B
bootstrap_reps = 5,000 for finalist reports if compute permits
```

### 4.4 How to group alternatives

Use explicit family IDs:

```text
feature_family_test:
  alternatives: tech_stat, tech_stat_decomp, learned_lstm, learned_cnn
  baseline: baseline_12 or tech_stat depending on question

source_family_test:
  alternatives: crypto_full, fx_full, sota_low_cost, kitchen_sink_guarded
  baseline: tech_stat

synthetic_generator_family_test:
  alternatives: regime_residual_bootstrap_v1, garch_hmm_v1, timevae_v1
  baseline: real_only_compute_matched

training_protocol_family_test:
  alternatives: real_plus_synth_0_25x, real_plus_synth_0_50x, synthetic_pretrain_then_real_finetune
  baseline: real_train_only_compute_matched
```

Every alternative must have a matched baseline with the same:

```text
asset
timeframe
algorithm
seed
train/validation split
cost scenario
reward/action configuration
```

### 4.5 Python-like pseudocode

```python
# Import numerical tools.
import numpy as np  # arrays and vectorized math

# Draw stationary-bootstrap indices for dependent time series.
def stationary_bootstrap_indices(t: int, expected_block_len: int, rng) -> np.ndarray:  # sample dependent indices
    p = 1.0 / float(expected_block_len)  # restart probability for geometric block lengths
    out = np.empty(t, dtype=int)  # allocate output indices
    out[0] = rng.integers(0, t)  # choose initial source index
    for i in range(1, t):  # fill remaining bootstrap positions
        if rng.random() < p:  # decide whether to start a new block
            out[i] = rng.integers(0, t)  # choose new source index
        else:  # continue previous block
            out[i] = (out[i - 1] + 1) % t  # advance source index circularly
    return out  # return resampled index vector

# Compute White Reality Check p-value from paired differentials.
def white_reality_check(diffs: np.ndarray, block_len: int, n_boot: int, seed: int) -> dict:  # run White RC
    rng = np.random.default_rng(seed)  # create reproducible RNG
    d = np.asarray(diffs, dtype=float)  # ensure numeric matrix T x M
    d = d[np.all(np.isfinite(d), axis=1)]  # remove rows with missing values
    t, m = d.shape  # read time length and number of alternatives
    mean_d = np.mean(d, axis=0)  # compute mean differential by alternative
    obs = float(np.sqrt(t) * np.max(mean_d))  # compute observed max statistic
    centered = d - mean_d  # center under null of no superior performance
    boot_stats = []  # initialize bootstrap statistic list
    for _ in range(n_boot):  # iterate bootstrap repetitions
        idx = stationary_bootstrap_indices(t, block_len, rng)  # sample dependent indices
        boot_mean = np.mean(centered[idx, :], axis=0)  # bootstrap mean differential
        boot_stats.append(float(np.sqrt(t) * np.max(boot_mean)))  # store max statistic
    boot_stats = np.asarray(boot_stats)  # convert list to vector
    p_value = float(np.mean(boot_stats >= obs))  # compute upper-tail p-value
    return {"stat": obs, "p_value": p_value, "n_alt": int(m), "n_obs": int(t)}  # return results

# Compute simplified Hansen SPA-style p-value.
def spa_test_simplified(diffs: np.ndarray, block_len: int, n_boot: int, seed: int) -> dict:  # run approximate SPA
    rng = np.random.default_rng(seed)  # create reproducible RNG
    d = np.asarray(diffs, dtype=float)  # ensure numeric matrix T x M
    d = d[np.all(np.isfinite(d), axis=1)]  # remove invalid rows
    t, m = d.shape  # read dimensions
    mean_d = np.mean(d, axis=0)  # compute mean differential
    std_d = np.std(d, axis=0, ddof=1)  # compute differential volatility
    std_d = np.maximum(std_d, 1e-12)  # avoid zero division
    t_stats = np.sqrt(t) * mean_d / std_d  # studentize observed means
    obs = float(np.max(t_stats))  # maximum studentized statistic
    # Truncate poor alternatives as an SPA-like power improvement.
    centered = d - np.minimum(mean_d, 0.0)  # center poor alternatives less aggressively
    boot_stats = []  # initialize bootstrap statistic list
    for _ in range(n_boot):  # iterate bootstrap repetitions
        idx = stationary_bootstrap_indices(t, block_len, rng)  # sample dependent time indices
        boot_mean = np.mean(centered[idx, :] - np.mean(centered, axis=0), axis=0)  # bootstrap centered means
        boot_t = np.sqrt(t) * boot_mean / std_d  # studentize bootstrap means
        boot_stats.append(float(np.max(boot_t)))  # store max studentized statistic
    boot_stats = np.asarray(boot_stats)  # convert statistics to vector
    p_value = float(np.mean(boot_stats >= obs))  # compute p-value
    return {"stat": obs, "p_value": p_value, "n_alt": int(m), "n_obs": int(t)}  # return results
```

The SPA pseudocode above is deliberately marked simplified. A production implementation should follow Hansen’s exact recentering variants and report which SPA variant was used.

### 4.6 How to report p-values without overclaiming

Required reporting language:

```text
The family-level test rejects / does not reject the null that no alternative in this tested family outperforms the matched baseline on real validation data.
```

Forbidden reporting language:

```text
The feature family is proven profitable.
The strategy is causal.
The strategy will work live.
The p-value proves the RL model is superior.
```

Suggested interpretation:

```text
p <= 0.05:
  useful evidence after family-level data-snooping adjustment, subject to DSR, PBO, costs, and seed stability

0.05 < p <= 0.10:
  weak evidence; continue only if other gates are strong

p > 0.10:
  family-level superiority not established; do not promote based on this family test
```

---

## 5. RL seed uncertainty

### 5.1 Why seed uncertainty is non-negotiable

Deep RL results can vary substantially across random seeds, environment stochasticity, initialization, replay sampling, and nondeterministic GPU kernels. Henderson et al. emphasize that nondeterminism and variance can make reported RL improvements hard to interpret without proper significance metrics and standardized reporting. Agarwal et al. further argue that few-run deep RL evaluation should report uncertainty intervals, performance profiles, IQM, and probability of improvement rather than relying on point estimates.

Primary references:

- Henderson et al., *Deep Reinforcement Learning That Matters*, AAAI 2018 — https://ojs.aaai.org/index.php/AAAI/article/view/11694
- Agarwal et al., *Deep Reinforcement Learning at the Edge of the Statistical Precipice*, NeurIPS 2021 — https://proceedings.neurips.cc/paper/2021/hash/f514cec81cb148559cf475e7426eed5e-Abstract.html
- `rliable` library — https://github.com/google-research/rliable

### 5.2 Minimum and preferred seed counts

| Stage | Minimum | Preferred | Interpretation |
|---|---:|---:|---|
| Stage A screening | 3 | 5 | Approximate; no direct Stage C promotion. |
| Stage B validation | 5 | 10 | Decision-grade comparison starts here. |
| Finalist before Stage C | 10 | 20 if feasible | Needed if results are close, tails are unstable, or candidate is high-impact. |
| Synthetic Phase 4 ablation | 5 | 10 | Must be paired against real-only and compute-matched real-only baselines. |

### 5.3 Paired seed tests

Use identical seed lists for all matched comparisons:

```text
baseline seeds: [0, 1, 2, 3, 4]
variant seeds:  [0, 1, 2, 3, 4]
```

For each seed:

```text
delta_seed_i = metric(variant_seed_i) - metric(baseline_seed_i)
```

Report:

- median paired delta;
- IQM paired delta;
- paired bootstrap confidence interval;
- probability of improvement `P(delta > 0)`;
- number of winning seeds;
- worst-seed delta;
- top-seed-minus-median concentration;
- performance profiles across candidates/families.

### 5.4 Recommended aggregate metrics

Required:

```text
mean
median
standard deviation
min / max
number of winning seeds
paired deltas
```

Recommended:

```text
IQM: interquartile mean, robust to extreme lucky/unlucky seeds
bootstrap CI: confidence interval over paired seeds
probability of improvement: fraction/bootstrap probability variant beats baseline
performance profile: distribution of normalized performance over seeds/assets/timeframes
```

Optional:

```text
stratified bootstrap across seed × asset/timeframe cells
Bayesian hierarchical model for candidate effects
```

### 5.5 Handling “seed 0 is strong, seeds 1 and 2 are weak”

This is **not promotion evidence**. The correct action is:

```text
1. Mark candidate as seed-fragile.
2. Do not promote on seed 0.
3. Run additional paired seeds if the median/IQM is still plausible.
4. Inspect failure cases and cost sensitivity.
5. If added seeds remain weak, kill or downgrade the candidate.
```

Suggested hard rule:

```text
No Stage B promotion unless median seed beats the matched baseline after costs.
```

For synthetic augmentation, preserve the Phase 4 rule:

```text
Top-seed-minus-median improvement must not exceed 50% of total improvement.
```

### 5.6 Report-table templates

#### Candidate seed table

| candidate_id | asset | tf | algo | feature_preset | cost_scenario | seed | net_return | sharpe | sortino | max_dd | turnover | DSR | beats_baseline |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `eth4h_sac_techstat` | ETHUSDT | 4h | SAC | tech_stat | base | 0 | ... | ... | ... | ... | ... | ... | true/false |

#### Paired comparison table

| comparison_id | baseline | variant | n_seeds | win_rate | median_delta_sharpe | iqm_delta_sharpe | ci_low | ci_high | prob_improvement | top_seed_concentration | decision |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `tech_stat_vs_baseline12` | baseline_12 | tech_stat | 10 | ... | ... | ... | ... | ... | ... | ... | promote/hold/kill |

#### Asset/timeframe family table

| family_id | asset | tf | algo | n_candidates | RC_p | SPA_p | PBO | best_candidate | best_DSR_raw | median_seed_win_rate | decision |
|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---|

---

## 6. Multiple-testing ledger

### 6.1 What counts as a trial

A trial is any executed or researcher-observed specification that could influence model, feature, data, or promotion decisions.

At minimum, the trial key includes:

```text
asset
timeframe
algorithm
feature_preset
feature_family
source_family
cross_source_set
reward_variant
action_space_variant
cost_model_variant
slippage_model_variant
seed_set_id
synthetic_generator_family
synthetic_ablation_id
augmentation_ratio
pretraining_schedule_id
training_protocol_id
run_budget_id
selection_stage
```

Seed treatment:

```text
If the seed list is fixed and aggregated, seed is a repeated measurement.
If the seed is selected, seed becomes part of the trial key.
```

### 6.2 Killed, failed, blocked, and diagnostic runs

| Run status | Include in trial count? | Ledger requirement | Notes |
|---|---:|---|---|
| Completed and inspected | Yes | Full metrics | Always included. |
| Killed after partial metrics | Yes | Partial metrics + kill reason | Avoid survival bias. |
| Killed before metrics by predeclared rule | Usually yes | Kill reason | Include if it influenced search narrowing. |
| Infrastructure failure before metrics | No for DSR, yes in ledger | Error metadata | Disclose failure rate. |
| Blocked before execution | No for DSR, yes in ledger | Block reason | Useful for reproducibility. |
| Diagnostic-only synthetic quality run | No as trading trial | Synthetic ledger | Not performance evidence. |
| Diagnostic run that influenced later design | Yes or disclosed | Notes | Conservative inclusion preferred. |

### 6.3 Conservative trial-count method

```text
N_raw = number of unique trial keys with status in:
  completed
  killed_after_metrics
  killed_after_partial_metrics
  diagnostic_influenced_design
```

Use `N_raw` for primary DSR.

### 6.4 Practical effective-trial-count method

Use both an eigenvalue method and a group-minimum guard:

```text
N_eff_eigen = (sum eigenvalues(C)^2) / sum eigenvalues(C)^2
N_eff_group_guard = number_of_top_level_families_tested
N_eff = max(ceil(N_eff_eigen), N_eff_group_guard)
```

Where `C` is the correlation matrix of candidate validation return streams or standardized metric vectors. If `C` cannot be computed because too many candidates lack aligned returns, do not estimate `N_eff`; use `N_raw` only.

Report:

```text
N_raw
N_eff
DSR_N_raw
DSR_N_eff
reason_for_difference
```

### 6.5 Ledger schema

```text
experiments/ledger/RUN_LEDGER.csv

Required columns:
  run_id
  candidate_id
  parent_candidate_id
  stage
  status
  asset
  timeframe
  algorithm
  feature_preset
  feature_family
  source_family
  cross_source_set_id
  seed
  seed_set_id
  reward_variant
  action_space_variant
  cost_scenario
  slippage_model_id
  synthetic_generator_family
  synthetic_ablation_id
  augmentation_ratio
  pretraining_schedule_id
  training_protocol_id
  train_start
  train_end
  validation_start
  validation_end
  heldout_start
  uses_heldout
  config_hash
  git_commit
  metrics_file
  returns_file
  trades_file
  kill_reason
  included_in_trial_count
  included_in_dsr
  included_in_family_test
  notes
```

Fail-closed rules:

```text
uses_heldout == true before Stage C -> fail
returns_file missing for Stage B completed run -> fail
included_in_trial_count missing -> fail
status missing -> fail
config_hash missing -> fail
```

---

## 7. Stage B evaluator architecture

### 7.1 Proposed Python module layout

```text
financial_data/
  statistical_governance/
    __init__.py
    cli.py
    schemas.py
    io.py
    calendar.py
    returns.py
    sharpe.py
    dsr.py
    pbo_cscv.py
    block_bootstrap.py
    reality_check.py
    spa.py
    seed_uncertainty.py
    multiple_testing.py
    family_grouping.py
    cost_scenarios.py
    validation_gates.py
    report_json.py
    report_markdown.py
    exceptions.py
    tests/
      test_dsr_known_values.py
      test_pbo_rank_degradation.py
      test_block_bootstrap_indices.py
      test_seed_pairing.py
      test_fail_closed_missing_returns.py
      test_no_heldout_access.py
```

### 7.2 CLI commands

```bash
fd-governance validate-inputs \
  --ledger experiments/ledger/RUN_LEDGER.csv \
  --stage stage_b

fd-governance compute-candidate-metrics \
  --ledger experiments/ledger/RUN_LEDGER.csv \
  --out experiments/stage_b_validation/governance/per_candidate_metrics.csv

fd-governance compute-dsr \
  --ledger experiments/ledger/RUN_LEDGER.csv \
  --trial-count-mode raw-and-effective

fd-governance compute-pbo \
  --family-manifest experiments/design/family_tests.yaml \
  --folds 8 \
  --purge-bars 252

fd-governance compute-family-tests \
  --family-manifest experiments/design/family_tests.yaml \
  --method white-rc,spa \
  --bootstrap stationary \
  --bootstrap-reps 2000

fd-governance make-report \
  --ledger experiments/ledger/RUN_LEDGER.csv \
  --out-dir experiments/stage_b_validation/governance/
```

### 7.3 Required input schemas

#### Run ledger

See Section 6.5.

#### Per-run returns

```text
returns_file.parquet

Required columns:
  timestamp: datetime64[ns, UTC] or timezone-aware equivalent
  run_id: string
  split: train|validation|heldout
  stage: stage_a|stage_b|stage_c|phase4
  step_index: int
  bar_return_gross: float
  bar_return_net: float
  equity_before: float
  equity_after: float
  position: float
  action: string or int
  turnover: float
  fee_cost: float
  slippage_cost: float
  financing_cost: float
  cost_scenario: string
```

#### Per-run trades

```text
trades_file.parquet

Required columns:
  timestamp
  run_id
  asset
  side
  quantity
  notional
  price
  fee
  slippage
  position_after
  trade_reason
```

#### Cost scenario outputs

```text
cost_scenario_metrics.csv

Required columns:
  run_id
  cost_scenario
  net_return
  sharpe
  sortino
  calmar
  max_drawdown
  turnover
  total_cost
  total_slippage
```

#### Candidate metadata

```text
candidate_metadata.json

Required fields:
  candidate_id
  asset
  timeframe
  algorithm
  feature_preset
  feature_family
  source_family
  train_window
  validation_window
  heldout_start
  config_hash
  git_commit
  stage_a_parent_run_ids
  stage_b_run_ids
  baselines
  family_test_groups
```

### 7.4 Required outputs

#### `statistical_governance_report.json`

```json
{
  "generated_at_utc": "...",
  "git_commit": "...",
  "stage": "stage_b",
  "heldout_start": "2025-01-01",
  "heldout_access_detected": false,
  "promotion_allowed": false,
  "candidates": [],
  "family_tests": [],
  "trial_count": {
    "N_raw": 0,
    "N_eff": null
  },
  "fail_closed_reasons": [],
  "warnings": []
}
```

#### `per_candidate_metrics.csv`

Required fields:

```text
candidate_id, asset, timeframe, algorithm, feature_preset, cost_scenario,
n_seeds, median_sharpe, iqm_sharpe, mean_sharpe, sharpe_ci_low, sharpe_ci_high,
median_net_return, median_max_drawdown, median_turnover,
DSR_N_raw, DSR_N_eff, PBO, paired_win_rate_vs_baseline,
promotion_gate_status, blocking_reasons
```

#### `family_test_results.csv`

Required fields:

```text
family_test_id, family_type, baseline_id, n_alternatives,
method, bootstrap_method, block_length, bootstrap_reps,
statistic, p_value, decision, notes
```

### 7.5 Fail-closed rules

The evaluator must set `promotion_allowed = false` if any of the following occur:

```text
1. Any pre-Stage-C artifact uses data >= 2025-01-01.
2. Completed Stage B run lacks per-step returns.
3. Candidate lacks matched baseline.
4. Candidate lacks paired seed set.
5. Candidate lacks base cost scenario.
6. Candidate lacks at least one pessimistic cost scenario.
7. Trial count cannot be reconstructed.
8. DSR cannot be computed.
9. Return timestamps are unordered or duplicated.
10. Any family-test manifest excludes known inspected failures without explanation.
```

---

## 8. Concrete Project 3 go/no-go rules

### 8.1 Minimum rule set for Stage B promotion

A candidate may be promoted from Stage B toward Stage C consideration only if all are true:

```text
[ ] Stage C data remains untouched.
[ ] Candidate has real-validation returns for all required seeds.
[ ] Candidate has matched baseline returns for the same seeds.
[ ] Candidate uses fixed PPO/SAC/DQN configuration.
[ ] Candidate beats matched baseline on median seed after costs.
[ ] Candidate has at least 5 paired seeds; 10 preferred.
[ ] Candidate is not dominated by one lucky seed.
[ ] Candidate survives base and pessimistic cost scenarios.
[ ] DSR_N_raw >= 0.95, or DSR_N_raw >= 0.80 with explicit additional-seed requirement.
[ ] PBO <= 0.10, or PBO <= 0.20 with explicit caution and supporting evidence.
[ ] White RC or SPA family test is significant or at least non-contradictory for the tested family.
[ ] Multiple-testing ledger includes completed, killed, failed, blocked, and diagnostic variants as required.
[ ] Leakage/heldout audit passes.
[ ] Feature/source-family ablation supports the claimed source of improvement.
```

### 8.2 What blocks promotion

Hard blockers:

```text
[ ] Any Stage C access before locked final evaluation.
[ ] Missing per-step return stream.
[ ] Missing matched baseline.
[ ] Best-seed-only improvement.
[ ] Validation-only threshold tuning.
[ ] DSR missing or DSR_N_raw < 0.80.
[ ] PBO > 0.20 unless explicitly demoted to exploratory.
[ ] Candidate wins only under zero-cost or base-only cost.
[ ] Median seed fails to beat baseline.
[ ] Synthetic-only metrics used as evidence.
[ ] Trial count excludes inspected failures.
[ ] Family test run after deleting poor alternatives.
```

### 8.3 Warnings acceptable only with disclosure

Warnings that do not automatically block but must be disclosed:

```text
[ ] DSR_N_eff passes but DSR_N_raw does not.
[ ] SPA passes but White RC does not.
[ ] PBO between 0.10 and 0.20.
[ ] One asset/timeframe dominates family-level improvement.
[ ] Seed win rate is 60% to 70% but median delta is positive.
[ ] Cost-stress performance is positive but much weaker than base.
[ ] High turnover but still net-positive under costs.
[ ] FX annualization depends on empirical calendar due session gaps.
```

### 8.4 What requires more seeds or more data

Require more seeds or additional validation folds when:

```text
[ ] confidence intervals overlap zero materially;
[ ] seed 0 is strong but other seeds are weak;
[ ] DSR is borderline;
[ ] PBO is borderline;
[ ] feature-family effect is present only in one regime;
[ ] the candidate uses synthetic pretraining or complex feature selection;
[ ] turnover/cost sensitivity is near the promotion threshold;
[ ] the candidate would materially change subscription or deployment decisions.
```

---

## 9. Recommended Stage B implementation plan

### P0 — must implement before trusting Stage B

| Task | Rationale | Estimated effort | Acceptance criteria |
|---|---|---:|---|
| Per-step return/trade schema | All statistics require return streams, not summary metrics. | 1–2 days | Every completed Stage B run emits returns/trades parquet. |
| Multiple-testing ledger | DSR and family tests need complete trial accounting. | 1–2 days | Ledger reconstructs raw trial count and statuses. |
| DSR module | Corrects Sharpe for non-normality and multiple testing. | 1–2 days | Known-value tests pass; reports raw/effective trial modes. |
| Paired seed uncertainty module | Prevents lucky-seed promotion. | 1–2 days | Median/IQM/CI/probability-of-improvement reports generated. |
| Fail-closed validator | Prevents incomplete governance. | 0.5–1 day | Missing inputs block promotion. |
| Cost-scenario integration | Prevents zero-cost false discoveries. | 1 day | Base and pessimistic costs required. |

### P1 — should implement during Stage B hardening

| Task | Rationale | Estimated effort | Acceptance criteria |
|---|---|---:|---|
| PBO/CSCV-lite | Measures selection-rank degradation across time folds. | 2–4 days | Contiguous fold PBO report generated per family. |
| White RC | Conservative family-level data-snooping correction. | 2–3 days | Stationary-bootstrap p-value per family. |
| Hansen SPA | More powerful family test when many poor alternatives exist. | 3–5 days | Studentized p-values and variant notes reported. |
| Trial-correlation effective N | Gives practical DSR diagnostic. | 1 day | Eigenvalue effective count reported beside raw count. |
| Markdown/JSON reports | Makes governance auditable by orchestrator. | 1–2 days | Required outputs generated with config hashes. |

### P2 — optional or finalist-only

| Task | Rationale | Estimated effort | Acceptance criteria |
|---|---|---:|---|
| Full purged fold retraining | Stronger PBO for finalists. | 1–3 weeks | Retrained fold-specific policies and PBO reported. |
| Hierarchical uncertainty model | Better asset/timeframe/seed inference. | 1 week | Posterior candidate effects reported as diagnostic. |
| Automatic block-length selection | Better bootstrap calibration. | 2–4 days | Block length selected and logged reproducibly. |
| rliable integration | Standard RL uncertainty tooling. | 1–2 days | IQM/performance profiles produced from Stage B tables. |

---

## 10. Concrete instructions for engineering agent

Paste this checklist into the orchestrator issue:

```text
Title:
  Implement Project 3 Stage B Statistical Governance Evaluator

Scope:
  Implement DSR, PBO/CSCV-lite, White Reality Check, Hansen SPA-style family tests, paired seed uncertainty, and multiple-testing ledger checks for Stage B. Do not alter PPO/SAC/DQN algorithms.

Hard constraints:
  - No file or row with timestamp >= 2025-01-01 may be used before Stage C.
  - Synthetic data is training-only; synthetic-only performance is diagnostic.
  - All Stage B completed runs must emit per-step returns.
  - Missing required data must fail closed.

P0 tasks:
  1. Add per_run_returns.parquet and per_run_trades.parquet schema validation.
  2. Extend RUN_LEDGER.csv with trial-accounting fields.
  3. Implement financial_data/statistical_governance/dsr.py.
  4. Implement financial_data/statistical_governance/seed_uncertainty.py.
  5. Implement fail-closed input validator.
  6. Generate per_candidate_metrics.csv and statistical_governance_report.json/md.

P1 tasks:
  1. Implement pbo_cscv.py using contiguous folds and purge bars.
  2. Implement stationary bootstrap in block_bootstrap.py.
  3. Implement White Reality Check in reality_check.py.
  4. Implement simplified Hansen SPA in spa.py, clearly marked with method version.
  5. Add family_test_results.csv output.

Acceptance:
  - Unit tests pass for known values and failure modes.
  - ETHUSDT 4h SAC tech_stat can be evaluated against matched baseline.
  - Report includes DSR_N_raw, DSR_N_eff, PBO, seed CI, family-test p-values, cost-stress outcomes, and promotion decision.
  - Any missing returns, missing baselines, unpaired seeds, or heldout contamination sets promotion_allowed=false.
```

---

## 11. References

1. Bailey, D. H., and López de Prado, M. *The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality*. SSRN. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
2. Bailey, D. H., and López de Prado, M. *The Sharpe Ratio Efficient Frontier*. SSRN. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1821643
3. Lo, A. W. *The Statistics of Sharpe Ratios*. Financial Analysts Journal, 2002. https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/the-statistics-of-sharpe-ratios
4. Bailey, D. H., Borwein, J. M., López de Prado, M., and Zhu, Q. J. *The Probability of Backtest Overfitting*. SSRN. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
5. White, H. *A Reality Check for Data Snooping*. Econometrica, 2000. https://www.ssc.wisc.edu/~bhansen/718/White2000.pdf
6. Hansen, P. R. *A Test for Superior Predictive Ability*. Journal of Business & Economic Statistics, 2005. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569
7. Politis, D. N., and Romano, J. P. *The Stationary Bootstrap*. Journal of the American Statistical Association, 1994. https://www.ssc.wisc.edu/~bhansen/718/Politis%20Romano.pdf
8. Politis, D. N., and White, H. *Automatic Block-Length Selection for the Dependent Bootstrap*. Econometric Reviews, 2004. https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf
9. Henderson, P., Islam, R., Bachman, P., Pineau, J., Precup, D., and Meger, D. *Deep Reinforcement Learning That Matters*. AAAI, 2018. https://ojs.aaai.org/index.php/AAAI/article/view/11694
10. Agarwal, R., Schwarzer, M., Castro, P. S., Courville, A., and Bellemare, M. G. *Deep Reinforcement Learning at the Edge of the Statistical Precipice*. NeurIPS, 2021. https://proceedings.neurips.cc/paper/2021/hash/f514cec81cb148559cf475e7426eed5e-Abstract.html
11. Google Research. `rliable`: reliable evaluation for RL and ML benchmarks. https://github.com/google-research/rliable

---

## 12. Final checklist for GitHub issue

```text
[ ] Implement per-step return schema for all Stage B runs.
[ ] Implement RUN_LEDGER trial-accounting fields.
[ ] Implement DSR from per-period net returns.
[ ] Report DSR_N_raw and DSR_N_eff.
[ ] Implement calendar-aware annualization for crypto and FX.
[ ] Implement seed-paired uncertainty: median, IQM, CI, probability of improvement.
[ ] Require at least 5 paired seeds for Stage B; prefer 10.
[ ] Implement contiguous PBO/CSCV-lite with purge/embargo.
[ ] Implement White Reality Check by family.
[ ] Implement Hansen SPA-style family test by family.
[ ] Include killed and failed inspected variants in trial accounting.
[ ] Require matched baselines for every candidate.
[ ] Require base and pessimistic cost scenarios.
[ ] Fail closed on missing returns, missing baselines, unpaired seeds, missing trial counts, or heldout access.
[ ] Do not touch Stage C before final locked evaluation.
[ ] Do not treat synthetic-only metrics as evidence.
[ ] Do not promote best-seed-only winners.
[ ] Generate statistical_governance_report.json.
[ ] Generate statistical_governance_report.md.
[ ] Generate per_candidate_metrics.csv.
[ ] Generate family_test_results.csv.
```
