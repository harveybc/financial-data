# Project3 OLAP Transversal Analysis Report

Date: 2026-06-29

Snapshot: `2026-06-29 17:46 UTC` / `2026-06-29 12:46 COT`

Database:

`financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite`

Companion query plan:

`financial-data/work_plan/PROJECT3_OLAP_TRANSVERSAL_ANALYSIS_PLAN_2026_06_29.md`

## Executive Read

The OLAP cube is useful and already exposes several actionable signals:

1. **No full-year candidate has positive annual RAP yet.** The best full-year RAP is still negative, so the current risk-adjusted objective is stricter than raw return and correctly penalizes drawdown exposure.
2. **Best full-year RAP and best full-year raw return disagree.** The best RAP candidate is lower-return but much safer; the best raw-return candidate gives more profit but loses badly on RAP.
3. **SOLUSDT 4h high-risk partials are the most interesting new signal.** They are not full-year proof yet, but their partial conservative scores are far above everything else.
4. **November 2023 is the main stress-regime cluster.** Multiple candidates fail around `2023-11-06` through `2023-12-04`; this is a high-value target for event/context/regime features.
5. **Risk geometry matters more than model churn right now.** The same SAC family changes materially with `rel_volume`, SL, and TP. Local risk-geometry search should be prioritized over blind feature/model Cartesian sweeps.
6. **Legacy BTCUSDT anomaly rows exist and must stay excluded from winner selection.** They are from older unnamed phases and show extreme weekly losses; useful as audit cases, not as current candidates.

## Data Coverage

|object|rows|
|---|---:|
|`weekly_result_olap`|9647|
|`weekly_result_test_week_olap`|9540|
|`weekly_result_test_year_olap`|653|
|`weekly_result_full_year_protocol_olap`|92|
|`result_artifacts`|55652|

Current subjob state at snapshot:

|status|rows|
|---|---:|
|done|9647|
|deferred|6461|
|superseded|2688|
|pending|261|
|failed|4|
|running|3|

Interpretation: the cube has enough depth for transversal analysis, but only a small subset has near-full-year test coverage. Final decisions must continue using `unique_test_weeks >= 48`.

## Best Full-Year Candidates

### Ranked by Annual RAP

|rank|candidate summary|weeks|annual return|annual RAP|mean weekly return|mean weekly RAP|mean weekly drawdown|worst weekly RAP|
|---:|---|---:|---:|---:|---:|---:|---:|---:|
|1|ETHUSDT 4h, SAC, scratch 4y, `fixed_rv0p05_sl2_tp4`, phase8|52|+2.0800%|-2.5767%|+0.0400%|-0.0496%|0.1791%|-0.7956%|
|2|ETHUSDT 4h, SAC, fine-tune m3, fixed ATR, full-year phase|52|+0.7890%|-4.9932%|+0.0152%|-0.0960%|0.1112%|-1.2702%|
|3|ETHUSDT 4h, SAC, scratch 4y, `rv0.05`, phase7|51|-0.2954%|-5.3735%|-0.0058%|-0.1054%|0.3983%|-1.0041%|
|4|ETHUSDT 4h, SAC, scratch 4y, `aware_rv0p10_base`, phase8|52|+2.5605%|-7.1924%|+0.0492%|-0.1383%|0.3751%|-1.5307%|
|5|ETHUSDT 4h, SAC, scratch 4y, `rv0.075`, phase7|51|-0.7054%|-7.9087%|-0.0138%|-0.1551%|0.5650%|-1.8607%|

Conclusion: the safest current full-year candidate is `fixed_rv0p05_sl2_tp4`, but its annual raw return is only +2.08% and annual RAP is still negative. This is a stable baseline, not a business-level solution.

### Ranked by Annual Raw Return

|rank|candidate summary|weeks|annual return|annual RAP|mean weekly drawdown|comment|
|---:|---|---:|---:|---:|---:|---|
|1|ETHUSDT 4h, scratch 4y, `fixed_rv0p10_sl2_tp3`, phase8|51|+5.9383%|-12.7392%|0.7324%|Best full-year raw return, but risk too high.|
|2|ETHUSDT 4h, scratch 4y, `fixed_rv0p50_sl1p25_tp1p25`, phase8|52|+5.3628%|-43.2804%|1.8709%|Too much drawdown for current RAP.|
|3|ETHUSDT 4h, scratch 4y, fixed ATR, full-year phase|51|+2.5963%|-15.5657%|0.3561%|Raw return acceptable but RAP weak.|
|4|ETHUSDT 4h, scratch 4y, `aware_rv0p10_base`, phase8|52|+2.5605%|-7.1924%|0.3751%|More balanced than rank 1, but still negative RAP.|
|5|ETHUSDT 4h, scratch 4y, `fixed_rv0p05_sl2_tp4`, phase8|52|+2.0800%|-2.5767%|0.1791%|Best risk-adjusted full-year candidate.|

Conclusion: raw return improves as exposure increases, but RAP collapses. This supports the current decision to tune risk geometry instead of simply increasing `rel_volume`.

## Pareto Frontier

Full-year non-dominated candidates across annual return, annual RAP, and mean weekly drawdown:

|candidate summary|annual return|annual RAP|mean weekly drawdown|interpretation|
|---|---:|---:|---:|---|
|ETHUSDT 4h `fixed_rv0p05_sl2_tp4` scratch 4y|+2.0800%|-2.5767%|0.1791%|Best current full-year risk-adjusted baseline.|
|ETHUSDT 4h fine-tune m3 fixed ATR|+0.7890%|-4.9932%|0.1112%|Lower return, lower drawdown, useful low-risk reference.|
|ETHUSDT 4h `aware_rv0p10_base` scratch 4y|+2.5605%|-7.1924%|0.3751%|Potential middle-risk local-search seed.|
|ETHUSDT 4h `fixed_rv0p10_sl2_tp3` scratch 4y|+5.9383%|-12.7392%|0.7324%|Best full-year raw return; useful high-return risk-geometry seed.|
|ETHUSDT 4h fixed ATR scratch 4y|+2.5963%|-15.5657%|0.3561%|Dominated for RAP by better phase8 variants in practice.|

Correlations among full-year candidates:

|pair|correlation|n|
|---|---:|---:|
|drawdown vs annual return|+0.5072|17|
|drawdown vs annual RAP|-0.7729|17|
|annual return vs annual RAP|-0.2334|17|

Interpretation: in the currently completed full-year set, higher drawdown tends to produce somewhat higher raw return, but strongly worse RAP. That means the RAP metric is doing its job, and the next search should look for candidates that bend this curve rather than moving along it.

## Strong Partial Candidates

Partial candidates are not final winners. They are useful for queue prioritization only.

|rank|candidate summary|weeks|annualized return|annualized RAP|mean weekly drawdown|worst weekly RAP|conservative weekly RAP|
|---:|---|---:|---:|---:|---:|---:|---:|
|1|SOLUSDT 4h, fine-tune m6 base3y, `aware_rv0p50_base`, seed12 extension|7|+284.91%|+188.59%|3.7047%|-2.8172%|+0.5800%|
|2|SOLUSDT 4h, fine-tune m6 base3y, `aware_rv0p50_base`, seed6 extension|10|+336.37%|+232.96%|3.9774%|-10.7717%|+0.4586%|
|3|ETHUSDT 4h, scratch 4y, phase7 `rap_l1p0_rv0p1`|5|+31.14%|+21.17%|0.1919%|-0.2918%|+0.1895%|
|4|ETHUSDT 4h, scratch 4y, `fixed_rv0p10_sl1p5_tp2`|5|+14.42%|+8.84%|0.2147%|-0.1659%|+0.0363%|

Interpretation:

- The SOLUSDT signal is too large to ignore, but it is partial and high-risk.
- Its worst-week RAP is already meaningfully negative, so completion is mandatory before promotion to business confidence.
- This is exactly the kind of candidate that should receive weeks first, not a huge blind sweep.

Recommended queue action:

1. Complete SOLUSDT 4h `aware_rv0p50_base` seed6/seed12 to at least 24 weeks.
2. If still positive, complete to 48-52 weeks.
3. Run local lower-risk siblings: `rv0.25`, `rv0.35`, `rv0.40`, `rv0.50` with the same architecture and training policy.

## Risk Geometry Findings

Best full-year risk geometry groups:

|phase/profile|rel_volume|SL|TP|full-year candidates|best annual return|best annual RAP|avg weekly drawdown|
|---|---:|---:|---:|---:|---:|---:|---:|
|phase8 `fixed_rv0p05_sl2_tp4`|0.05|2.0|4.0|2|+2.0800%|-2.5767%|0.2856% avg group|
|full-year fixed ATR|0.05|2.0|3.0|8|+2.5963%|-4.9932%|0.2906% avg group|
|phase8 `aware_rv0p10_base`|0.10|2.0|3.0|1|+2.5605%|-7.1924%|0.3751%|
|phase8 `fixed_rv0p10_sl2_tp3`|0.10|2.0|3.0|1|+5.9383%|-12.7392%|0.7324%|
|phase8 `fixed_rv0p50_sl1p25_tp1p25`|0.50|1.25|1.25|1|+5.3628%|-43.2804%|1.8709%|

Interpretation:

- `rv0.05 + SL2/TP4` is the current best risk-adjusted full-year anchor.
- `rv0.10 + SL2/TP3` is the current best raw-return full-year anchor, but risk is too high.
- `rv0.50 + symmetric SL/TP` can generate return but is too drawdown-heavy full-year on ETH. It may still be viable for SOL if its partial result survives completion.

Recommended local search:

- Around ETH full-year safe anchor:
  - `rel_volume`: 0.04, 0.05, 0.06, 0.075
  - `k_sl/k_tp`: 1.75/3.5, 2/4, 2.25/4.5
- Around ETH high-return anchor:
  - `rel_volume`: 0.075, 0.10, 0.125
  - `k_sl/k_tp`: 1.5/2, 1.75/2.5, 2/3, 2/4
- Around SOL partial:
  - `rel_volume`: 0.25, 0.35, 0.40, 0.50
  - preserve the same profile first, then vary SL/TP only after completion.

## Feature/Profile Attribution

Current high-signal observations:

|profile/data|full-year result|partial signal|interpretation|
|---|---|---|---|
|ETHUSDT 4h kitchen-sink guarded, 180 features, `fixed_rv0p05_sl2_tp4`|best full-year RAP, +2.08% return / -2.58% RAP|small positive partials|Keep as baseline and local-search seed.|
|ETHUSDT 4h kitchen-sink guarded, fixed ATR|moderate full-year baseline|one phase7 partial at +21% annualized RAP|Still useful, but phase8 risk geometry is superior.|
|SOLUSDT 4h kitchen-sink guarded, 121 features, `aware_rv0p50_base`|no full-year yet|very strong partials|Highest priority for completion.|
|SOLUSDT 4h margin-aware `rv0p50_cap2p5`|no full-year yet|strong partial +141% annualized RAP|Secondary SOL risk-control branch.|
|event-token / transformer profiles|no full-year yet|not enough completed evidence in top lists|Do not judge yet; they need controlled comparisons against the same anchors.|

Interpretation: feature innovations should be tested as overlays on strong anchors, not as broad stand-alone sweeps. The strongest immediate evidence is asset/risk geometry, not a new feature family.

## Training Policy Findings

|policy/phase|full-year candidates|best annual return|best annual RAP|average annual RAP|average weekly drawdown|
|---|---:|---:|---:|---:|---:|
|scratch 4y, phase8 SL/TP geometry|6|+5.9383%|-2.5767%|-14.3529%|0.6558%|
|fine-tune 4y, full-year phase|6|+1.1934%|-4.9932%|-15.3618%|0.2932%|
|scratch 4y, phase7 RAP|3|+0.1143%|-5.3735%|-7.6823%|0.5794%|
|scratch 4y, old full-year phase|2|+2.5963%|-10.1774%|-12.8715%|0.2827%|

Interpretation:

- Scratch 4y plus explicit SL/TP geometry is the most productive full-year lane so far.
- Fine-tune is safer in some cases but has not beaten phase8 on full-year RAP.
- Do not discard fine-tune: SOL partials are fine-tune based and may change the conclusion if they complete well.

## Generalization Gap

Largest overfit-style gaps:

|candidate summary|train+val RAP mean|test RAP mean|gap|annual return|annual RAP|
|---|---:|---:|---:|---:|---:|
|ETH `rv0.50 sl1.25 tp1.25` scratch 4y|+0.8235%|-0.8323%|+1.6558%|+5.3628%|-43.2804%|
|ETH phase7 `rv0.10` scratch 4y|+0.7235%|-0.1915%|+0.9150%|+0.1143%|-9.7647%|
|ETH `rv0.10 sl2 tp3` scratch 4y|+0.5486%|-0.2498%|+0.7984%|+5.9383%|-12.7392%|

Most stable positive-return candidates by low RAP gap:

|candidate summary|abs gap|annual return|annual RAP|
|---|---:|---:|---:|
|ETH fine-tune m6 fixed ATR|0.0640%|+1.1934%|-20.1491%|
|ETH fine-tune m12 fixed ATR|0.1329%|+1.1424%|-8.9486%|
|ETH `fixed_rv0p05_sl2_tp4` scratch 4y|0.1453%|+2.0800%|-2.5767%|

Interpretation: high-exposure candidates can look good in train/validation but degrade sharply in test. The best current full-year RAP candidate also has one of the better positive-return generalization gaps.

## Hard-Week / Regime Stress Analysis

Worst broad-stress test weeks:

|week|rows|avg return|avg RAP|avg drawdown|positive return rows|positive RAP rows|
|---|---:|---:|---:|---:|---:|---:|
|2023-11-27|391|-1.8233%|-4.2953%|2.6873%|234|212|
|2022-11-07|12|-1.5138%|-2.6255%|2.1679%|4|0|
|2023-11-13|421|-0.5720%|-2.6053%|2.4554%|265|31|
|2022-09-12|13|-1.3499%|-2.2412%|1.7596%|2|2|
|2023-11-06|411|-0.1901%|-2.1653%|2.3374%|279|242|
|2023-11-20|445|-0.5326%|-2.0535%|1.7127%|250|171|
|2023-12-04|396|-0.2298%|-1.8884%|1.7631%|249|198|

Interpretation:

- The stress cluster around November 2023 is not isolated to one candidate.
- This is exactly where event context, market-regime embeddings, and calendar-aware features should be tested.
- A candidate that survives this cluster with positive RAP deserves strong promotion.

Recommended diagnostic:

Build a small stress-regime dashboard panel for weeks:

- `2023-11-06`
- `2023-11-13`
- `2023-11-20`
- `2023-11-27`
- `2023-12-04`

Compare candidate families on these weeks only. This can reveal whether event/context features are adding value where they matter most.

## Integrity and Anomaly Audit

Detected anomaly rows:

|phase|anomaly rows|extreme return rows|RAP math rows|no-trade return rows|
|---|---:|---:|---:|---:|
|empty/legacy phase|15|15|0|0|

Examples include old `btcusdt_perp` rows with weekly returns from about `-57%` to `-99%` and RAP near `-128%` to `-198%`.

Interpretation:

- These rows are legacy/extreme-loss artifacts, not evidence for current phase behavior.
- There is no current RAP math anomaly in this audit; the relation `RAP <= return` under positive drawdown holds.
- Keep these rows in OLAP for historical traceability, but exclude unnamed legacy phases from candidate promotion and dashboard defaults.

Recommended rule:

Default Metabase dashboards should filter:

```sql
experiment_phase IS NOT NULL
AND experiment_phase <> ''
```

unless the view is explicitly for legacy audit.

## Main Insights

### Insight 1: Current Full-Year Results Are Risk-Limited, Not Model-Limited

The completed full-year set shows that raw return rises with drawdown, while annual RAP falls. This means the present bottleneck is not simply "find a stronger SAC run"; it is finding a risk geometry or representation that allows return without proportional adverse excursion.

Action: prioritize local risk geometry around proven anchors.

### Insight 2: SOLUSDT 4h May Be a New High-Value Branch

SOLUSDT partials are too strong to ignore. They could be:

- a genuine asset/regime opportunity,
- a high-risk artifact that will collapse over full-year coverage,
- or an example that `rv0.50` is viable only on some assets/timeframes.

Action: complete the SOLUSDT high-risk branch before starting a large new sweep.

Portfolio implication: this is also the first concrete "asset bloom" case for
the future portfolio allocator. The important question is not only whether this
specific SOLUSDT branch survives full-year completion. The broader question is
whether the system can detect, before the weekly rebalance, that an asset/model
stream is entering a temporary opportunity regime and deserves more portfolio
weight for that week.

This implication has been added to the main weekly-retrained portfolio protocol
as the **Opportunity/Bloom Portfolio Allocator** lane.

The allocator must eventually learn or estimate:

- which asset/model streams are eligible for activation;
- whether their current pre-week context resembles past opportunity regimes;
- how much capital weight they deserve under max-weight, drawdown, worst-week,
  and correlation caps;
- when to reduce weight or no-trade the stream after the bloom decays.

The evaluation must remain strictly walk-forward: for each week, the portfolio
allocator sees only information available before that week's rebalance, chooses
weights, then the next-week test outcome is recorded.

### Insight 3: Event/Context Features Should Be Tested Against Stress Weeks

The reason to use event-token/transformer/context features should not be generic sophistication. The concrete target is the hard-week cluster, especially November 2023.

Action: compare event/context profiles on the stress-week subset and require improvement specifically there.

### Insight 4: `fixed_rv0p05_sl2_tp4` Is the Current Control Arm

This candidate is not strong enough financially, but it is the best risk-adjusted full-year control. Future innovations should beat it on:

- annual return,
- annual RAP,
- mean weekly drawdown,
- and worst weekly RAP.

Action: all new phases should show delta versus this control.

### Insight 5: The Cube Is Working, But Dashboards Need Sensible Defaults

Because legacy and partial rows coexist with current full-year rows, dashboard defaults must prevent misleading conclusions.

Action: default dashboard filters:

- `experiment_phase IS NOT NULL`
- `unique_test_weeks >= 48` for final leaderboards
- `unique_test_weeks >= 5 AND unique_test_weeks < 48` for promotion board
- separate "legacy anomaly audit" page

## Recommended Queue Changes

### Immediate Completion Priority

1. Complete SOLUSDT 4h `aware_rv0p50_base` seed6 and seed12 to 24 weeks.
2. If annualized RAP remains positive after 24 weeks, complete to 48-52 weeks.
3. Complete ETHUSDT 4h `rap_l1p0_rv0p1` to at least 24 weeks; it has a reasonable partial conservative RAP with much lower drawdown than SOL.

### Local Search Priority

Use focused neighborhoods:

1. ETH safe control:
   - `rv`: 0.04, 0.05, 0.06, 0.075
   - `SL/TP`: 1.75/3.5, 2/4, 2.25/4.5
2. ETH raw-return anchor:
   - `rv`: 0.075, 0.10, 0.125
   - `SL/TP`: 1.5/2, 1.75/2.5, 2/3, 2/4
3. SOL partial branch:
   - `rv`: 0.25, 0.35, 0.40, 0.50
   - start with current `aware_rv0p50_base` logic before adding feature changes.

### Defer or Downweight

1. Do not expand `rv0.50` ETH broadly unless a margin-aware or drawdown-aware variant proves better.
2. Do not launch broad event-token/transformer sweeps without tying them to the hard-week diagnostic.
3. Do not promote unnamed legacy BTCUSDT candidates from old phases.

## Suggested New Analysis Views

These are not required immediately, but they would make Metabase more useful:

1. `weekly_result_promotion_board_olap`
   - candidates with `5 <= unique_test_weeks < 48`
   - includes conservative RAP score
2. `weekly_result_stress_week_olap`
   - rows filtered to the hard-week cluster
   - useful for event/context evaluation
3. `weekly_result_control_delta_olap`
   - candidate metrics minus ETH `fixed_rv0p05_sl2_tp4` baseline
   - makes progress visible without manually comparing tables
4. `weekly_asset_opportunity_panel_olap`
   - one row per candidate/asset/week with causal pre-week features and
     next-week return/RAP outcome
   - intended for future opportunity/bloom detection and portfolio allocation
5. `weekly_portfolio_bloom_backtest_olap`
   - portfolio-level weekly weights, active streams, no-trade decisions,
     realized return, realized RAP, drawdown, turnover, and CDT excess return

## Final Recommendation

The next pragmatic move is not "more of everything." It is:

1. Protect the ETH 4h `rv0.05 SL2 TP4` full-year control.
2. Complete the SOLUSDT 4h high-risk partials enough to know whether they are real.
3. Use the November 2023 stress cluster as the proving ground for event/context/transformer ideas.
4. Run local SL/TP/rel_volume searches around proven anchors instead of broad Cartesian sweeps.
5. Prepare the future portfolio opportunity/bloom allocator around causal
   weekly asset-stream scoring, but do not let it consume current-week test
   outcomes.
6. Keep RAP, annual return, mean weekly return, drawdown, and worst-week RAP together in every status/report so we do not mistake leverage for intelligence.
