# Project 3 Data Context And Paid Source Gap Spec

Generated: 2026-05-13

Status: implementation-ready follow-up. This is not a Stage C launch packet.

## Finding

The current Stage B execution path enforces a Friday/session close rule, but
the inspected model-ready `tech_stat` input did not expose explicit
time-to-Friday or bars-to-force-close features to the policy.

That is a real data-presentation gap. The strategy can force flat positions on
Friday, but a policy without calendar/session context cannot learn to reduce
exposure before the forced close except indirectly through price patterns.

The current environment observation does include state context such as
`position`, `equity_norm`, `unrealized_pnl_norm`, and `steps_remaining_norm`.
It does not expose `bars_to_force_close` or `hours_to_force_close` as an
environment state field.

The paid-data concern is also valid. CryptoQuant artifacts and a paid shadow
plan exist in the repo, but the current Stage B pragmatic diagnostic variants
are still mostly own-asset technical/statistical variants. They do not yet test
a matched `best_free` versus `best_free_plus_cryptoquant` lane.

However, CryptoQuant is not immediately runnable for Stage B: the acquired API
payload currently covers only a recent 2026 window. See
`work_plan/PROJECT3_CRYPTOQUANT_SUBSCRIPTION_DECISION_2026_05_13.md`.
Do not launch CryptoQuant historical ablations unless historical export/API
coverage is confirmed.

## Implemented Immediately

The Stage B feature materializer now emits three session/calendar variants:

- `baseline_12_plus_session_calendar`
- `tech_stat_full_plus_session_calendar`
- `tech_stat_reduced_corr_v1_plus_session_calendar`

Each adds deterministic, causal timestamp features:

- `calendar_weekday`
- `calendar_hour`
- `calendar_hour_of_week`
- `calendar_weekday_sin`
- `calendar_weekday_cos`
- `calendar_hour_of_day_sin`
- `calendar_hour_of_day_cos`
- `calendar_hour_of_week_sin`
- `calendar_hour_of_week_cos`
- `calendar_is_trading_session`
- `calendar_is_force_close_zone`
- `calendar_is_friday_close_day`
- `calendar_is_friday_force_close_bar`
- `calendar_is_monday_entry_window`
- `calendar_hours_to_friday_close`
- `calendar_bars_to_friday_close`
- `calendar_hours_to_next_friday_close`
- `calendar_bars_to_next_friday_close`
- `calendar_hours_to_next_entry_window`

Generated outputs:

- `experiments/stage_b_validation/diagnostic_inputs/ethusdt/4h/baseline_12_plus_session_calendar/train.csv`
- `experiments/stage_b_validation/diagnostic_inputs/ethusdt/4h/tech_stat_full_plus_session_calendar/train.csv`
- `experiments/stage_b_validation/diagnostic_inputs/ethusdt/4h/tech_stat_reduced_corr_v1_plus_session_calendar/train.csv`
- `experiments/stage_b_validation/diagnostic_inputs/ethusdt/4h/feature_variant_materialization_summary.md`

Audit outputs:

- `experiments/stage_b_validation/hardening/data_context_gap_audit.md`
- `experiments/stage_b_validation/hardening/data_context_gap_audit.json`

## Agent-Multi Trade Trace Verdict

Copilot's agent-multi review found no trace-infrastructure defect causing the
trade-behavior failures.

Verified contract:

- `info["trades"]` is a cumulative, non-decreasing counter within each episode.
- `stage_b_return_trace_v1.trades` is a passthrough of that cumulative value.
- `financial-data` `infer_trade_count()` consumes the last value per
  split/episode segment and only falls back to row-summing for legacy
  per-step-style traces.

Implication:

- no rerun is needed to repair a trade-count writer bug;
- no-trade and excessive-trade flags should be treated as real economic or
  policy-behavior outcomes under the current observation/action setup;
- the next rerun, if any, should be a targeted diagnostic of improved data
  context, not a blind repeat.

## P0 Next Work

1. Build a locked Stage B diagnostic run packet for the three
   `plus_session_calendar` variants. Done:
   - `experiments/stage_b_validation/session_calendar_run_plan/stageb_session_calendar_run_plan_summary.md`
   - `experiments/stage_b_validation/session_calendar_run_plan/run_plan/stage_b_session_calendar_locked_run_plan.md`
   - `270` locked configs: 3 variants x 5 seeds x 3 costs x candidate+5 baselines.
   - Machine split: dragon `108`, gamma `108`, omega `54`.
   - Executor dry-run: `270/270` ready, `0` blocked.
   - Execution complete: `270/270` done, `0` failed, `0` pending.
   - Dragon/gamma/omega artifacts synced into the local
     `session_calendar_run_plan` tree.
   - Evaluator discovery now includes
     `experiments/stage_b_validation/session_calendar_run_plan/plans`.
   - Final evidence universe after sync: `1220` evidence files,
     `1220` traces found, `0` evidence failures.
   - Result: `0/100` candidate statistical gates passed,
     `0` DSR passes under `N_raw`, `promotion_allowed=false`,
     `stage_c_allowed=false`.
2. Add an agent-multi/gym-fx observation-state audit for
   `bars_to_force_close` and `hours_to_force_close`.
3. If CSV calendar columns are not enough, add those force-close context fields
   to the observation dictionary without changing PPO/SAC/DQN algorithms.
4. Materialize a paid-source diagnostic lane:
   `best_free` versus `best_free_plus_cryptoquant`, matched on
   asset/timeframe/algorithm/seed/cost.
   This is blocked until CryptoQuant historical access/export is confirmed.
5. Keep every new run counted in the ledger and in DSR/PBO trial accounting.

## P1 Research Lane

The proposed specialized open/close behavior is sensible, but it is a new
strategy-family question, not a silent fix to the current fixed-policy
comparison.

Allowed research lane:

- flat-state opening policy;
- in-position holding/closing policy;
- Friday-risk closing policy;
- mixture or hierarchy over those contexts.

Rules:

- count it as a new strategy family;
- do not compare it to old PPO/SAC/DQN results as if only data changed;
- do not use Stage C for selection;
- require matched real validation and matched baselines.

## Post-Session-Calendar Decision

The session/calendar diagnostic answered the immediate data-presentation
question: adding explicit weekday/hour/hour-to-Friday features to the CSV input
did not produce a Stage B-ready candidate.

This is useful negative evidence. It means the next step should not be a blind
larger rerun of the same SAC/ETHUSDT/4h feature space. The blocker has moved
from "maybe the model lacked Friday context" to "the current feature/action/
reward/source setup still does not produce statistically robust, cost-robust,
trade-behavior-clean policies."

Next orchestration decision:

1. Keep Stage C locked.
2. Close the session-calendar diagnostic as `NO_STAGE_B_PROMOTION`.
3. Do not pay for CryptoQuant historical/API access unless a small offline
   feasibility packet proves that the already exported/free-source feature
   families are insufficient and that CryptoQuant provides historical,
   point-in-time aligned signals over the Stage B period.
4. Move coding work to the remaining P0 gap: environment/observation-state
   force-close context. CSV calendar features were tested; the still-untested
   part is whether `bars_to_force_close` / `hours_to_force_close` must be
   present in the environment state alongside `position`, `equity_norm`,
   `unrealized_pnl_norm`, and `steps_remaining_norm`.
5. Move research/design work to feature/source redesign:
   - split noisy `tech_stat` into smaller interpretable families;
   - test regime-conditioned features and source-family ablations;
   - use free/owned data first;
   - count every new diagnostic as a new trial in DSR/PBO accounting.

## Feature/Action Audit Result

Generated audit:

- `experiments/stage_b_validation/hardening/stage_b_feature_action_audit.md`
- `experiments/stage_b_validation/hardening/stage_b_feature_action_audit.json`
- `experiments/stage_b_validation/hardening/stage_b_feature_action_audit.csv`

Key finding:

- Top audited candidates: `12`
- Distinct data hashes: `12`
- Missing feature-list hash candidates: `12`
- Largest identical performance/action-signature group: `11`

Interpretation:

The top `tech_stat` variants are not accidentally pointing to the same data
file; their data hashes differ. However, their action/trade/performance
signatures are effectively identical:

- mean OOS trades: `368.13`
- mean exposure: `0.5122`
- mean action standard deviation: `0.095240`
- same hard blockers: `DSR_RIGOROUS_FAIL`,
  `FAMILY_REALITY_CHECK_FAIL`, `PBO_DEFERRED_OR_FAIL`

This strongly suggests that the current policy/environment/reward/action setup
is insensitive to the tested feature-family changes. The next branch should
therefore audit and repair observation-state/evidence plumbing before launching
another broad GPU matrix.

Immediate implementation tasks:

1. Agent-multi must persist a non-null `feature_list_hash` in every
   `project3_return_trace_evidence_v1` file.
2. Agent-multi/gym-fx must expose and test force-close context in the live
   observation state, not only as CSV columns.
3. Financial-data must treat identical action/performance signatures across
   distinct feature hashes as a warning before expensive reruns.

## Stage C Rule

Stage C remains locked. These changes only prepare better Stage B/diagnostic
inputs. No rows at or after `2025-01-01` are used here.

## Force-Close Observation Repair Result

The first force-close observation diagnostic completed, but the trained SAC
candidate evidence did not prove that the policy saw the new observation-state
fields. Baseline evidence carried the observation fields, while candidate
evidence had missing `observation_state_fields`.

Repair performed:

1. `agent-multi` return-trace evidence resolution was fixed to walk through
   observation wrappers until it finds the base `Dict` observation space.
2. The 15 trained `tech_stat_full_plus_force_close_obs` candidate cells were
   rerun with the repaired evidence contract; the 75 deterministic baselines
   were not rerun.
3. All repaired force-close evidence now carries:
   - non-null `feature_list_hash`: `90/90`
   - non-null `observation_state_hash`: `90/90`
   - force-close observation fields present: `90/90`
   - trained candidate force-close observation fields present: `15/15`

Post-repair Stage B evaluator result:

- evidence files discovered: `1310`
- evidence failures: `0`
- candidate statistical gates passing: `0/106`
- DSR gates passing: `0/675`
- Stage C allowed: `false`

The repaired feature/action audit now includes the lower-ranked
`ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate` instead of only
the top 12 diagnostic candidates.

Key comparison:

- `force_close_obs` contract OK: `true`
- behavior changed versus both matched old policies: `2/2`
- Friday-late exposure improved versus both matched old policies: `2/2`
- mean OOS trades changed from `368.13` to `308.07`
- mean exposure changed from `0.5122` to `0.4089`
- mean action standard deviation changed from `0.095240` to `0.077138`
- mean Friday-late exposure changed from `0.8247` to `0.6731`

Interpretation:

The environment-level force-close observation fields are now reaching the
policy/evidence contract and they do change behavior in the intended direction.
However, the change is not yet economically or statistically sufficient:
Stage B still has no promotion-ready candidate. The next unblocker is not
another broad rerun of the same matrix; it is a focused design branch using this
working observation contract:

1. test whether force-close context needs a reward/action penalty for late
   Friday exposure or excessive churn;
2. test smaller, regime-conditioned feature families instead of the current
   feature-insensitive `tech_stat` bundle;
3. keep all new trials counted in DSR/PBO accounting;
4. keep Stage C locked until a candidate clears all Stage B hard gates.

## Force-Close Reward-Penalty Diagnostic Started

The force-close observation repair showed that the policy now sees the
environment state and reacts to it, but late-Friday exposure remained too high
for a promotable Stage B candidate. The next focused diagnostic has therefore
been started.

Implementation completed:

1. `gym-fx/app/env.py` now has a config-gated Stage B reward-shaping hook:
   - `stage_b_force_close_reward_penalty`
   - `force_close_exposure_penalty_coef`
   - `force_close_exposure_penalty_window_hours`
2. The penalty is disabled by default and only applies when
   `stage_b_force_close_obs=true`, the penalty flag is enabled, and the policy
   holds non-zero exposure within the configured Friday force-close lookahead
   window.
3. PPO/SAC/DQN algorithm code was not modified.
4. New regression tests in `gym-fx/tests/test_force_close_reward_penalty.py`
   pin the pre-close-window, force-close-zone, flat-position, and config-gated
   behavior.
5. `financial-data/_scripts/workers/stage_b_force_close_penalty_run_plan_worker.py`
   generated and activated a locked diagnostic plan:
   - variants: `2`
   - penalty coefficients: `[0.0001, 0.0003]`
   - total locked configs: `180`
   - machine split: dragon `72`, gamma `72`, omega `36`
   - Stage C access: `DENIED`
6. `stageb_dsr_pbo_evaluator.py` evidence discovery now includes
   `experiments/stage_b_validation/force_close_penalty_run_plan/plans`.

Execution status at launch:

- dragon: running trained candidate cell;
- gamma: running trained candidate cell;
- omega: running baseline cell;
- Stage C: still locked;
- training launched only for this counted Stage B diagnostic branch.

Interpretation:

This is not an attempt to weaken the gate or force a pass. It tests whether the
already repaired force-close observation state also needs a reward incentive to
make Friday exposure behavior economically sane. The result must still pass the
same DSR, PBO, family, seed, cost, and trade-behavior gates before Stage C can
be considered.
