# Project 3 OANDA Trade-Policy Agent Specs — 2026-05-15

## Current Verified State

- Stage C remains locked. Do not inspect, train, tune, or evaluate rows at or after `2025-01-01`.
- Stage 3X SAC smoke dispatch is complete:
  - total tasks: 12
  - done: 11
  - failed: 1
  - running: 0
  - pending: 0
- The failed cell is not an infrastructure crash:
  - contract: `audusd__1h__fx_full__corr_stability_topk__p00__selected`
  - seed: `0`
  - host: `gamma`
  - reason: `aborted_no_trade_at_40.0%: zero train/validation trades after smoke threshold`
- Result synthesis says no contract is eligible for targeted follow-up or Stage 3X micro-NSGA.
- The FINRA/OANDA memo is now available at:
  - `financial-data/work_plan/PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md`

## Orchestration Decision

Do not launch another GPU batch yet.

The next required work is broker-aware execution policy hardening:

1. `agent-multi` must emit OANDA/New-York-aware calendar and broker state fields, not fixed UTC approximations.
2. `financial-data` must compute broker-profile-aware trade-frequency metrics from trace evidence and hard-fail candidates that violate the policy.
3. Only after those checks are implemented should we create another small smoke run.

---

## Copilot Agent Prompt — agent-multi / gym-fx

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi and gym-fx repos. Do not guess paths.

Repositories:
- cd /home/harveybc/Documents/GitHub/agent-multi
- gym-fx is available at /home/harveybc/Documents/GitHub/gym-fx or as the local
  dependency used by agent-multi.

Python:
- Prefer /home/harveybc/anaconda3/envs/tensorflow/bin/python when running tests.

Read first:
1. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md
2. /home/harveybc/Documents/GitHub/agent-multi/docs/STAGE_B_EVIDENCE_CONTRACT.md
3. /home/harveybc/Documents/GitHub/agent-multi/pipeline_plugins/_return_trace.py
4. /home/harveybc/Documents/GitHub/agent-multi/pipeline_plugins/rl_pipeline.py
5. /home/harveybc/Documents/GitHub/agent-multi/pipeline_plugins/rl_pipeline_with_validation.py
6. /home/harveybc/Documents/GitHub/gym-fx/app/env.py
7. /home/harveybc/Documents/GitHub/agent-multi/tests/unit/test_return_trace.py
8. /home/harveybc/Documents/GitHub/gym-fx/tests/

Mission:
Implement OANDA-aware calendar and broker observation support for Stage 3X
without launching training and without touching PPO/SAC/DQN algorithm code.

Important current defect:
Earlier force-close observation support used a fixed UTC approximation. The
FINRA/OANDA memo requires America/New_York calendar logic. Do not hard-code a
fixed UTC Friday close, because daylight-saving time changes.

Implement:
1. A small OANDA FX calendar helper using IANA timezone `America/New_York`.
   Required policy times:
   - FX weekly open: Sunday 17:05 New York.
   - FX weekly close: Friday 16:59 New York.
   - Daily FX break: 16:59-17:05 New York.
   - Project no-trade window: 16:50-17:10 New York.
   - Friday no-new-position cutoff: Friday 14:00 New York.
   - Friday risk-reduction window begins: Friday 15:00 New York.
   - Friday force-flat deadline: Friday 15:45 New York.
   - Last-exit safety cutoff: Friday 15:55 New York.
2. Config-gated observation/info fields for Stage 3X:
   - `hours_to_fx_daily_break`
   - `bars_to_fx_daily_break`
   - `hours_to_friday_close`
   - `bars_to_friday_close`
   - `is_friday_risk_reduction_window`
   - `is_no_new_position_window`
   - `is_force_flat_window`
   - `is_broker_daily_break_near`
   - `broker_market_open`
   - `margin_closeout_percent` if available, else deterministic placeholder/null-safe value
   - `margin_available_norm` if available, else deterministic placeholder/null-safe value
3. Keep existing `stage_b_force_close_obs` / Stage 3X force-close config
   backward-compatible, but make OANDA FX profile use New York timezone.
4. Add evidence metadata fields when resolvable:
   - `broker_profile`
   - `market_type`
   - `trade_rate_band_id`
   - `calendar_policy_id`
5. Add tests proving:
   - New York DST is handled via timezone conversion, not fixed UTC.
   - Friday force-flat / no-new-position windows are correct in New York time.
   - Daily FX break fields activate around 16:59-17:05 New York.
   - Stage C dual-flag guard remains unchanged.
   - Existing configs without OANDA fields remain backward-compatible.

Hard rules:
- Do not launch training.
- Do not touch PPO/SAC/DQN algorithm source.
- Do not weaken Stage C guards.
- Do not unlock broad GPU launch.

Commands to run:
- /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit/test_return_trace.py -q
- /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q
- cd /home/harveybc/Documents/GitHub/gym-fx && /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests -q

Final report must include:
- files changed
- tests run
- exact calendar policy implemented
- example observation/info row for a Friday 15:30 New York timestamp
- confirmation no training launched and Stage C not touched
```

---

## Claude Agent Prompt — financial-data

```text
You are Claude acting as a senior quantitative engineering reviewer inside the
financial-data repo. Do not guess paths.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- Use /home/harveybc/anaconda3/envs/tensorflow/bin/python

Read first:
1. work_plan/PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md
2. work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md
3. work_plan/PROJECT3_STAGE3X_CHATGPT55_PRO_RESEARCH_REVIEW.md
4. experiments/stage3x_sac_smoke_results/stage3x_sac_smoke_result_synthesis.md
5. experiments/stage3x_sac_smoke_results/stage3x_sac_smoke_result_synthesis.json
6. experiments/stage3x_target_relation_screen/selected_feature_contracts.json
7. _scripts/workers/stage3x_sac_smoke_result_synthesis_worker.py
8. _scripts/workers/stage3x_absurdity_guard_worker.py
9. _scripts/tests/test_stage3x_sac_smoke_result_synthesis_worker.py
10. _scripts/tests/test_stage3x_sac_smoke_request_worker.py

Mission:
Wire the FINRA/OANDA policy memo into Stage 3X reporting and gating. This is
not trading advice and not Stage C. It is a broker-aware trade-behavior policy
layer for research candidates.

Implement:
1. Broker profile inference/registry:
   - `oanda_us_fx` for FX pairs such as AUDUSD/EURUSD/GBPUSD/USDJPY.
   - `oanda_us_spot_crypto` or `crypto_exchange_spot` for spot crypto; if
     venue is missing, emit `BROKER_PROFILE_UNCONFIRMED` and fail closed for
     OANDA-specific promotion.
   - `crypto_exchange_perp` for `_perp` instruments.
2. Trade-frequency policy table from the memo:
   - FX 4h: target 3/week, warning >6/week, hard max 12/week.
   - FX 1h: target 6/week, warning >12/week, hard max 24/week.
   - OANDA crypto 4h: target 1-3/week, warning >3/week, hard max 12/week.
   - OANDA crypto 1h: target 3-6/week, warning >12/week, hard max 24/week.
   - Non-OANDA crypto/perp 4h: target 3-6/week, warning >12/week, hard max 24/week.
   - Non-OANDA crypto/perp 1h: target 6-12/week, warning >24/week, hard max 36/week.
3. Evidence-derived metrics:
   - Use return trace/evidence split timestamps to compute validation/test
     duration in weeks.
   - Compute trades/week from split trade count divided by duration.
   - Report median validation trades/week and median test trades/week per contract.
   - Do not use training split for candidate gates.
4. Hard blockers:
   - `TRADE_FREQUENCY_HARD_MAX_EXCEEDED`
   - `BROKER_PROFILE_MISSING_OR_UNCONFIRMED`
   - `OANDA_FX_FRIDAY_FORCE_FLAT_VIOLATION` if evidence supports detection
   - `OANDA_FX_DAILY_BREAK_TRADE_ATTEMPT` if evidence supports detection
   - Keep existing no-trade / negative validation / negative test blockers.
5. Warning fields:
   - `TRADE_FREQUENCY_WARNING_BAND_EXCEEDED`
   - `OANDA_POLICY_FIELDS_MISSING`
   - `COST_TO_GROSS_EDGE_UNAVAILABLE`
6. Reporting:
   - Update the Stage 3X synthesis Markdown/JSON with broker_profile,
     trade-rate policy band, median validation/test trades/week, warnings, and
     hard blockers.
   - Add or update an absurdity-guard field that blocks broad GPU launch when
     broker profile or policy fields are missing.

Hard rules:
- Do not unlock Stage C.
- Do not launch training.
- Do not weaken existing hard gates.
- Do not mark any current smoke contract eligible unless the existing economic
  gates and the new trade-frequency gates pass.

Commands to run:
- /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stage3x_sac_smoke_result_synthesis_worker.py _scripts/tests/test_stage3x_sac_smoke_request_worker.py -q
- /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_sac_smoke_result_synthesis_worker.py
- /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_absurdity_guard_worker.py

Final report must include:
- files changed
- tests run
- current done/failed/running/pending smoke counts
- contract-level trade-frequency status
- whether any contract became eligible for follow-up or micro-NSGA
- confirmation no training launched and Stage C not touched
```

---

## Codex Local Owner Tasks

Codex owns integration review after both agents finish:

1. Verify Copilot's `agent-multi` evidence fields match Claude's
   `financial-data` parser.
2. Re-run Stage 3X synthesis and absurdity guard.
3. If and only if the OANDA policy fields are present and no existing hard
   blocker remains, prepare a tiny smoke rerun. Do not launch broad GPU.
4. If policy fields are missing, keep GPU idle and finish CPU-side contract
   repair first.

## ChatGPT 5.5 Pro Web

No new research task is needed right now. The FINRA/OANDA memo is sufficient
for implementation. Use ChatGPT 5.5 Pro again only if:

- OANDA official documentation is ambiguous about a specific limit;
- FINRA/SEC migration dates change;
- a broker other than OANDA becomes the intended live execution path.
