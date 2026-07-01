# Project3 OLAP Transversal Analysis Plan

Date: 2026-06-29

Purpose: mine the live weekly walk-forward OLAP cube for pragmatic signals that can accelerate current experiments, expose hidden promising regions, detect broken assumptions, and identify anomalies before they waste GPU time.

Primary database:

`financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite`

Primary views:

- `weekly_result_test_year_olap`: candidate-level test-year aggregates.
- `weekly_result_test_week_olap`: weekly test rows for stability and stress analysis.
- `weekly_result_validation_year_olap`: validation-year aggregates.
- `weekly_result_full_year_protocol_olap`: normalized validation/test blocks.
- `weekly_result_olap`: raw completed subjob rows.

Operational rule: full-year decisions must prioritize `has_near_full_year_coverage = 1` or `unique_test_weeks >= 48`. Partial candidates can be used only as promotion signals, never as final winners.

## 1. Full-Year Profit/Risk/RAP Frontier

Question: Which completed candidates form the current Pareto frontier between annual return, annual RAP, and drawdown?

Use: identify the serious best performers and avoid chasing partial spikes.

```sql
SELECT
  asset,
  timeframe,
  experiment_phase,
  olap_profile_key,
  training_policy,
  train_years,
  input_data_file,
  feature_count,
  rel_volume,
  k_sl,
  k_tp,
  reward_risk_ratio,
  unique_test_weeks,
  ROUND(mean_weekly_test_return, 6) AS mean_weekly_return,
  ROUND(annual_test_return, 6) AS annual_return,
  ROUND(mean_weekly_test_drawdown, 6) AS mean_weekly_drawdown,
  ROUND(mean_weekly_test_rap, 6) AS mean_weekly_rap,
  ROUND(annual_test_rap, 6) AS annual_rap,
  ROUND(worst_weekly_test_rap, 6) AS worst_weekly_rap,
  candidate_id
FROM weekly_result_test_year_olap
WHERE unique_test_weeks >= 48
ORDER BY annual_test_rap DESC, annual_test_return DESC
LIMIT 50;
```

Decision: promote neighborhoods around candidates with strong annual RAP, not only annual return. If high-return candidates have strongly negative annual RAP, they belong in a risk-geometry sweep rather than direct exploitation.

## 2. Partial Candidate Early Promotion Score

Question: Which partial candidates are good enough to deserve more weeks before the full queue spends time on weaker regions?

Use: accelerate scheduling while avoiding single-week noise.

```sql
WITH weekly AS (
  SELECT
    candidate_id,
    asset,
    timeframe,
    experiment_phase,
    olap_profile_key,
    training_policy,
    rel_volume,
    k_sl,
    k_tp,
    test_week_start,
    mean_test_return,
    mean_test_rap,
    mean_test_drawdown
  FROM weekly_result_test_week_olap
  WHERE mean_test_rap IS NOT NULL
),
agg AS (
  SELECT
    candidate_id,
    asset,
    timeframe,
    experiment_phase,
    olap_profile_key,
    training_policy,
    rel_volume,
    k_sl,
    k_tp,
    COUNT(*) AS weeks,
    AVG(mean_test_return) AS mean_weekly_return,
    AVG(mean_test_rap) AS mean_weekly_rap,
    AVG(mean_test_drawdown) AS mean_weekly_drawdown,
    MIN(mean_test_rap) AS worst_weekly_rap,
    AVG(mean_test_rap * mean_test_rap) - AVG(mean_test_rap) * AVG(mean_test_rap) AS var_weekly_rap
  FROM weekly
  GROUP BY candidate_id
)
SELECT
  *,
  mean_weekly_rap - 0.50 * SQRT(CASE WHEN var_weekly_rap > 0 THEN var_weekly_rap ELSE 0 END) AS conservative_rap_score,
  52.0 * mean_weekly_return AS annualized_return,
  52.0 * mean_weekly_rap AS annualized_rap
FROM agg
WHERE weeks BETWEEN 5 AND 47
ORDER BY conservative_rap_score DESC, mean_weekly_return DESC
LIMIT 80;
```

Decision: feed scheduler promotion with conservative RAP, not raw partial return. Candidates with high mean but bad worst-week RAP require more risk control before expansion.

## 3. Train/Validation/Test Generalization Gap

Question: Are we overfitting to train-tail plus validation, or are some profiles genuinely stable into test?

Use: detect profile families that look good before test but collapse in the test year.

```sql
SELECT
  asset,
  timeframe,
  experiment_phase,
  olap_profile_key,
  training_policy,
  rel_volume,
  k_sl,
  k_tp,
  unique_test_weeks,
  ROUND(0.5 * mean_weekly_train_tail_rap + 0.5 * mean_weekly_validation_rap, 6) AS mean_train_val_rap,
  ROUND(mean_weekly_test_rap, 6) AS mean_test_rap,
  ROUND((0.5 * mean_weekly_train_tail_rap + 0.5 * mean_weekly_validation_rap) - mean_weekly_test_rap, 6) AS rap_gap,
  ROUND(annual_test_return, 6) AS annual_return,
  ROUND(annual_test_rap, 6) AS annual_rap,
  candidate_id
FROM weekly_result_test_year_olap
WHERE unique_test_weeks >= 48
ORDER BY rap_gap DESC
LIMIT 50;
```

Decision: high `rap_gap` groups become de-prioritized or require stronger regularization/early stopping. Low-gap groups deserve local exploration.

## 4. SL/TP and rel_volume Response Surface

Question: Which risk geometry actually works, and does rel_volume need a coupled SL/TP formula?

Use: find the best neighborhoods for the risk-adjusted phase and avoid blind sweeps.

```sql
SELECT
  experiment_phase,
  sltp_risk_mode,
  rel_volume,
  k_sl,
  k_tp,
  reward_risk_ratio,
  COUNT(*) AS candidates,
  SUM(CASE WHEN unique_test_weeks >= 48 THEN 1 ELSE 0 END) AS full_year_candidates,
  ROUND(AVG(CASE WHEN unique_test_weeks >= 48 THEN annual_test_return END), 6) AS avg_annual_return_full,
  ROUND(MAX(CASE WHEN unique_test_weeks >= 48 THEN annual_test_return END), 6) AS best_annual_return_full,
  ROUND(AVG(CASE WHEN unique_test_weeks >= 48 THEN annual_test_rap END), 6) AS avg_annual_rap_full,
  ROUND(MAX(CASE WHEN unique_test_weeks >= 48 THEN annual_test_rap END), 6) AS best_annual_rap_full,
  ROUND(AVG(CASE WHEN unique_test_weeks >= 48 THEN mean_weekly_test_drawdown END), 6) AS avg_weekly_drawdown_full
FROM weekly_result_test_year_olap
GROUP BY experiment_phase, sltp_risk_mode, rel_volume, k_sl, k_tp, reward_risk_ratio
HAVING candidates >= 2
ORDER BY best_annual_rap_full DESC, best_annual_return_full DESC;
```

Decision: if best RAP clusters around specific `rel_volume/k_sl/k_tp`, enqueue local search around that geometry. If high rel_volume is only good with narrow SL/TP, codify a rel_volume-aware SL/TP policy.

## 5. Feature/Profile Family Attribution

Question: Are kitchen-sink/event/context profiles actually helping, or are simpler profiles carrying the useful signal?

Use: avoid wasting experiments on feature families with poor risk-adjusted value.

```sql
SELECT
  olap_profile_key,
  input_data_file,
  feature_count,
  model_family,
  COUNT(*) AS candidates,
  SUM(CASE WHEN unique_test_weeks >= 48 THEN 1 ELSE 0 END) AS full_year_candidates,
  ROUND(MAX(CASE WHEN unique_test_weeks >= 48 THEN annual_test_return END), 6) AS best_full_annual_return,
  ROUND(MAX(CASE WHEN unique_test_weeks >= 48 THEN annual_test_rap END), 6) AS best_full_annual_rap,
  ROUND(AVG(CASE WHEN unique_test_weeks >= 48 THEN annual_test_rap END), 6) AS avg_full_annual_rap,
  ROUND(MAX(CASE WHEN unique_test_weeks BETWEEN 5 AND 47 THEN 52.0 * mean_weekly_test_rap END), 6) AS best_partial_annualized_rap
FROM weekly_result_test_year_olap
GROUP BY olap_profile_key, input_data_file, feature_count, model_family
ORDER BY best_full_annual_rap DESC, best_partial_annualized_rap DESC
LIMIT 80;
```

Decision: expand families that produce robust full-year RAP or strong partial conservative scores. Retire feature families whose best result is only a raw-return spike with poor RAP.

## 6. Training Policy Comparison

Question: Is scratch 4y, weekly fine-tune, or shorter recent fine-tune winning under RAP?

Use: decide whether to spend GPUs on from-scratch retraining, continuation, or hybrid.

```sql
SELECT
  training_policy,
  train_years,
  experiment_phase,
  COUNT(*) AS candidates,
  SUM(CASE WHEN unique_test_weeks >= 48 THEN 1 ELSE 0 END) AS full_year_candidates,
  ROUND(MAX(CASE WHEN unique_test_weeks >= 48 THEN annual_test_return END), 6) AS best_annual_return,
  ROUND(MAX(CASE WHEN unique_test_weeks >= 48 THEN annual_test_rap END), 6) AS best_annual_rap,
  ROUND(AVG(CASE WHEN unique_test_weeks >= 48 THEN annual_test_rap END), 6) AS avg_annual_rap,
  ROUND(AVG(CASE WHEN unique_test_weeks >= 48 THEN mean_weekly_test_drawdown END), 6) AS avg_weekly_drawdown
FROM weekly_result_test_year_olap
GROUP BY training_policy, train_years, experiment_phase
ORDER BY best_annual_rap DESC, avg_annual_rap DESC;
```

Decision: favor the policy with best full-year RAP and acceptable drawdown. If fine-tune has high partial but little full-year coverage, prioritize completion rather than starting new scratch variants.

## 7. Hard Weeks and Regime Stress

Question: Are failures concentrated in specific weeks/regimes, suggesting missing event/calendar/context features?

Use: identify where event-token/market-context representations should help.

```sql
SELECT
  test_week_start,
  COUNT(*) AS candidate_rows,
  ROUND(AVG(mean_test_return), 6) AS avg_return,
  ROUND(AVG(mean_test_rap), 6) AS avg_rap,
  ROUND(AVG(mean_test_drawdown), 6) AS avg_drawdown,
  ROUND(MIN(mean_test_rap), 6) AS worst_rap,
  ROUND(MAX(mean_test_rap), 6) AS best_rap,
  SUM(CASE WHEN mean_test_return > 0 THEN 1 ELSE 0 END) AS positive_return_rows,
  SUM(CASE WHEN mean_test_rap > 0 THEN 1 ELSE 0 END) AS positive_rap_rows
FROM weekly_result_test_week_olap
WHERE test_week_start IS NOT NULL
GROUP BY test_week_start
HAVING COUNT(*) >= 10
ORDER BY avg_rap ASC
LIMIT 60;
```

Decision: hard weeks with broad model failure become priority cases for event/calendar/context embeddings. Weeks where only some feature families survive are useful for attribution.

## 8. Profit vs Risk Plot Feed for Metabase

Question: What is the current tradeoff surface across all completed and partial candidates?

Use: Metabase scatter plot. X = risk, Y = profit, color = RAP.

```sql
SELECT
  candidate_id,
  asset,
  timeframe,
  experiment_phase,
  olap_profile_key,
  training_policy,
  input_data_file,
  rel_volume,
  k_sl,
  k_tp,
  unique_test_weeks,
  has_near_full_year_coverage,
  mean_weekly_test_drawdown AS x_weekly_drawdown,
  annual_test_return AS y_annual_return,
  annual_test_rap AS color_annual_rap,
  mean_weekly_test_return,
  mean_weekly_test_rap,
  worst_weekly_test_rap
FROM weekly_result_test_year_olap
WHERE unique_test_weeks >= 5
  AND mean_weekly_test_drawdown IS NOT NULL
ORDER BY has_near_full_year_coverage DESC, annual_test_rap DESC;
```

Decision: manually inspect frontiers and outliers in Metabase. The useful region is high annual return with drawdown not growing faster than return.

## 9. Anomaly and Integrity Audit

Question: Are any reported winners caused by metric bugs, missing weeks, invalid drawdown/RAP, or no-trade artifacts?

Use: catch measurement/system problems before scheduling more work around bad data.

```sql
SELECT
  subjob_id,
  job_id,
  candidate_id,
  experiment_phase,
  test_week_start,
  test_return,
  test_drawdown,
  test_rap,
  risk_penalty_lambda,
  test_trades,
  run_dir
FROM weekly_result_olap
WHERE status = 'done'
  AND (
    ABS(COALESCE(test_return, 0)) > 0.50
    OR COALESCE(test_drawdown, 0) < -0.000001
    OR (COALESCE(risk_penalty_lambda, 0) > 0 AND COALESCE(test_drawdown, 0) > 0 AND test_rap > test_return + 0.000001)
    OR (COALESCE(test_trades, 0) = 0 AND ABS(COALESCE(test_return, 0)) > 0.000001)
  )
ORDER BY completed_at DESC
LIMIT 200;
```

Decision: any row returned here is not a candidate to celebrate. It needs audit first.

## 10. Candidate Neighborhood Expansion Targets

Question: Which completed or partial candidates should seed the next exploration queue?

Use: produce a practical shortlist for automatic job generation.

```sql
WITH scored AS (
  SELECT
    *,
    CASE
      WHEN unique_test_weeks >= 48 THEN annual_test_rap
      ELSE 52.0 * mean_weekly_test_rap
    END AS comparable_annual_rap,
    CASE
      WHEN unique_test_weeks >= 48 THEN annual_test_return
      ELSE 52.0 * mean_weekly_test_return
    END AS comparable_annual_return
  FROM weekly_result_test_year_olap
  WHERE unique_test_weeks >= 5
)
SELECT
  asset,
  timeframe,
  experiment_phase,
  olap_profile_key,
  training_policy,
  input_data_file,
  rel_volume,
  k_sl,
  k_tp,
  unique_test_weeks,
  ROUND(comparable_annual_return, 6) AS comparable_annual_return,
  ROUND(comparable_annual_rap, 6) AS comparable_annual_rap,
  ROUND(mean_weekly_test_drawdown, 6) AS mean_weekly_drawdown,
  ROUND(worst_weekly_test_rap, 6) AS worst_weekly_rap,
  candidate_id
FROM scored
WHERE comparable_annual_return > 0
ORDER BY comparable_annual_rap DESC, unique_test_weeks DESC, comparable_annual_return DESC
LIMIT 100;
```

Decision: use these rows as seeds for focused local variants: neighboring `rel_volume`, coupled `k_sl/k_tp`, event-token encoding, and portfolio allocation tests. Do not spawn large Cartesian sweeps unless this shortlist shows a real region worth expanding.

## 11. Portfolio-Readiness Export

Question: Which asset/timeframe/candidate streams are worth testing in the portfolio layer?

Use: find candidates with positive standalone RAP and non-identical weekly behavior.

```sql
SELECT
  candidate_id,
  asset,
  timeframe,
  test_week_start,
  mean_test_return,
  mean_test_rap,
  mean_test_drawdown,
  rel_volume,
  k_sl,
  k_tp,
  olap_profile_key,
  training_policy
FROM weekly_result_test_week_olap
WHERE candidate_id IN (
  SELECT candidate_id
  FROM weekly_result_test_year_olap
  WHERE unique_test_weeks >= 48
    AND annual_test_return > 0
  ORDER BY annual_test_rap DESC
  LIMIT 50
)
ORDER BY candidate_id, test_week_start;
```

Decision: export this to compute correlations/covariance outside SQLite if needed. Portfolio layer should start with candidates that are not merely individually good, but complementary across bad weeks.

## 12. Immediate Analysis Order

Run in this order:

1. Integrity audit: query 9.
2. Full-year frontier: query 1.
3. Risk geometry surface: query 4.
4. Partial promotion: query 2.
5. Generalization gap: query 3.
6. Feature/profile attribution: query 5.
7. Training policy comparison: query 6.
8. Hard-week stress: query 7.
9. Metabase scatter feed: query 8.
10. Neighborhood expansion targets: query 10.
11. Portfolio-readiness export: query 11.

Output expected from the analysis:

- A short list of candidates to protect/complete.
- A short list of experiment families to de-prioritize.
- A local search region around rel_volume, SL, and TP.
- Any metric/integrity anomalies requiring code fixes.
- A small set of hard weeks for event-context investigation.
- A portfolio-readiness shortlist for later multi-asset allocation tests.
