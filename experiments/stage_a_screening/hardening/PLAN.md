# Promotion Hardening Evaluator — PLAN

Generated: 2026-05-03T06:19:08.537688+00:00

## Data Flow

```
artifacts/run_ledger.jsonl          →  build_ledger_index()
experiments/stage_a_screening/      →  load_stage_a_index()
  index.csv
         │
         ├── verify_ledger_membership()      per run
         ├── validate_required_metadata()    per run
         ├── compute_cost_proxy()            per run × 3 scenarios
         ├── find_matched_baselines()        per run
         ├── compute_paired_uplift()         per run
         ├── classify_candidate()            per run → status + blockers
         │
         ├── compute_group_statistics()      by preset, asset, algo
         ├── compute_seed_dispersion()       by (asset, tf, algo, preset)
         ├── compute_bootstrap_ci()          by preset
         ├── compute_dsr_placeholder_or_approximation()  per surviving run
         └── compute_pbo_placeholder()       global placeholder
                   │
                   ▼
hardening/
  SPEC.md
  PLAN.md
  TASKS.md
  promotion_candidates.csv
  promotion_hardening_report.md
  promotion_hardening_report.json
```

## Validation Checks (in order)

### KILL Checks (immediate disqualifiers)

| Order | Check | Status assigned |
| --- | --- | --- |
| 1 | Run not in immutable ledger | KILL_LEDGER_MISSING |
| 2 | asset/tf/algo/preset/seed/machine invalid | KILL_INVALID_METRICS |
| 3 | total_return / sharpe / drawdown missing or non-finite | KILL_INVALID_METRICS |
| 4 | trades_total == 0 | KILL_NO_TRADES |
| 5 | total_return ≤ 0 | KILL_NON_POSITIVE_RETURN |
| 6 | sharpe_ratio < 0 | KILL_NEGATIVE_SHARPE |
| 7 | base-cost proxy net ≤ 0 | KILL_NON_POSITIVE_RETURN |

### Governance Blockers (after all KILLs pass)

| Blocker id | Check | Source |
| --- | --- | --- |
| B1 | Leakage audit not completed | leakage_audit.md |
| B2 | Availability contract not verified (cross-source presets) | Rule P3.6 |
| B3 | DSR not rigorous (no annualized return series) | multiple_testing_correction.md |
| B4 | PBO/CSCV not feasible at Stage A | multiple_testing_correction.md |
| B5 | No matched baseline_12 OR uplift ≤ 0 | stage_b_promotion_gate.yaml |
| B6 | Fewer than 2 seeds | stage_b_promotion_gate.yaml §uncertainty |
| B7 | Pessimistic cost: catastrophic or negative | cost_model.md |
| B8 | Simple baselines not compared | §1.3 Stage A deliverable |
| B9 | Feature-family ablation not reported | feature_family_ablation_plan.md |
| B10 | Heldout firewall not audited | leakage_audit.md §heldout_timestamp_exclusion |

### Secondary Watch Flags (additive)

| Flag | Trigger |
| --- | --- |
| WATCH_NEEDS_BASELINE | has_baseline = False |
| WATCH_NEEDS_SEEDS | n_seeds < 2 |
| WATCH_COST_FRAGILE | pessimistic_net < 0 |

## Scoring Logic

No numeric promotion score is computed. Classification is deterministic:
1. Apply KILL checks in order. First KILL terminates evaluation.
2. If no KILL: accumulate all governance blockers.
3. Assign PROMOTE_BLOCKED_HARDENING if any blocker exists.
4. Assign secondary watch flags independently.

## Output Schema

### promotion_candidates.csv

| Column | Description |
| --- | --- |
| run_slug | Unique run identifier |
| asset, timeframe, algo, preset, seed, machine | Experiment metadata |
| total_return | Gross return from summary.json |
| sharpe_ratio | Episode Sharpe from backtesting engine |
| max_drawdown_pct | Maximum drawdown |
| trades_total | Number of trades executed |
| ledger_ok | bool: found in immutable ledger |
| metadata_ok | bool: all required metadata present |
| cost_optimistic | Net return under optimistic cost proxy |
| cost_base | Net return under base cost proxy |
| cost_pessimistic | Net return under pessimistic cost proxy |
| asset_class | crypto_spot or fx |
| has_baseline | bool: matched baseline_12 found |
| baseline_slug | Matching baseline_12 run slug |
| baseline_return | baseline_12 total_return |
| baseline_sharpe | baseline_12 sharpe_ratio |
| uplift_total_return | Δ total_return vs baseline |
| uplift_sharpe_ratio | Δ sharpe vs baseline |
| n_seeds | Seeds run for this (asset,tf,algo,preset) |
| dsr_approx | Approximate DSR value |
| dsr_status | Status string for DSR |
| classification | Primary status |
| watch_flags | Semicolon-separated secondary flags |
| n_blockers | Count of governance blockers |
| blockers | Pipe-separated blocker list |
