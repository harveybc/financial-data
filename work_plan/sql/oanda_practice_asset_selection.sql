-- OANDA Practice selection evidence.
-- Selection uses validation only. Test rows remain reporting-only.

-- Current E4 asset-policy evidence by asset/timeframe.
SELECT
    json_extract(config_json, '$.asset') AS asset,
    json_extract(config_json, '$.timeframe') AS timeframe,
    json_extract(config_json, '$.portfolio_role') AS portfolio_role,
    COUNT(*) AS seed_count,
    AVG(validation_evaluation_weeks) AS mean_validation_weeks,
    100.0 * AVG(validation_annualized_return) AS mean_annual_return_pct,
    100.0 * AVG(validation_annual_rap) AS mean_annual_rap_pct,
    100.0 * MIN(validation_annual_rap) AS worst_seed_annual_rap_pct,
    100.0 * AVG(validation_max_drawdown) AS mean_max_drawdown_pct
FROM evidence_result_olap
WHERE stage = 'E4_ASSET_POLICY_TRAINING'
  AND status = 'completed'
GROUP BY 1, 2, 3
ORDER BY AVG(validation_annual_rap) DESC;

-- Comparable historical activity proxy. Run against project3_weekly_pool.sqlite.
WITH ranked AS (
    SELECT
        asset,
        timeframe,
        candidate_id,
        model_family,
        annual_validation_return,
        annual_validation_rap,
        worst_weekly_validation_rap,
        mean_weekly_validation_trades,
        unique_validation_weeks,
        ROW_NUMBER() OVER (
            PARTITION BY asset, timeframe
            ORDER BY annual_validation_rap DESC, candidate_id
        ) AS rank_in_pair
    FROM weekly_result_validation_year_olap
    WHERE experiment_phase = 'annual_diversity_survey_fast40k_v2'
      AND has_near_full_year_coverage = 1
)
SELECT *
FROM ranked
WHERE rank_in_pair = 1
ORDER BY asset, timeframe;
