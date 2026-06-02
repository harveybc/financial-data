# Project 3 Market-State Representation Agent Specs

Date: 2026-05-23 local / 2026-05-24 UTC

Purpose: copy-paste-ready specs for the next implementation/review wave after
the final market-state representation plan.

Primary plan:

```text
work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md
```

Global rules for every agent:

- Stage C remains locked.
- Do not use rows at or after `2025-01-01`.
- Do not launch broad GPU work.
- Do not modify PPO/SAC/DQN algorithm implementations.
- Do not hide warnings or overwrite evidence to manufacture a pass.
- Use `/home/harveybc/anaconda3/envs/tensorflow/bin/python`.

## Current Runtime Status

G18 micro-NSGA is active in agent-multi. At the time this spec was written:

- done: `6`
- running: `4`
- pending: `26`
- failed: `0`
- active hosts: `dragon=2`, `omega=1`, `gamma=1`
- Stage C: `DENIED`

Do CPU-only work while G18 runs. Do not launch a new GPU generation until G18 is
synthesized or Codex explicitly accepts capacity.

## Claude Spec A - financial-data CPU State Profiles

Status: implemented by Codex on 2026-05-23 local / 2026-05-24 UTC. Use this
spec for Claude review/hardening or further implementation, not duplicate
from-scratch work.

```text
You are Claude acting as a senior quantitative engineer inside the
financial-data repo. You have repository access. Do not guess paths.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- Use /home/harveybc/anaconda3/envs/tensorflow/bin/python
- Do not assume python is on PATH.

Read first:
1. work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md
2. work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md
3. work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md
4. experiments/stage3x_market_state_causal_contract/stage3x_market_state_causal_contract.json
5. _scripts/workers/stage3x_market_state_causal_contract_worker.py
6. _scripts/workers/stage3x_weekly_walk_forward_contract_worker.py
7. _scripts/workers/stage3x_target_relation_screen_worker.py
8. _scripts/workers/stage3x_micro_nsga_nextgen_worker.py

Mission:
Review and harden the CPU-only market-state profile generation and screen
layer. Defect fixes are allowed; do not rewrite without evidence.

Implemented files:
1. _scripts/workers/stage3x_market_state_profile_worker.py
2. _scripts/workers/stage3x_market_state_profile_screen_worker.py
3. _scripts/tests/test_stage3x_market_state_profile_worker.py
4. _scripts/tests/test_stage3x_market_state_profile_screen_worker.py

Generated artifacts:
1. experiments/stage3x_market_state_profile/stage3x_market_state_profiles.json
2. experiments/stage3x_market_state_profile/stage3x_market_state_profile_screen.json
3. experiments/stage3x_market_state_profile/selected_market_state_profiles.json

Profile worker requirements:
- consume the weekly/causal contract;
- emit profile contracts for engineered summary, engineered+PCA, and
  engineered+regime profiles first;
- include stubs/contract fields for autoencoder, TS2Vec, and Patch profiles
  without requiring heavy dependencies yet;
- support 1h and 4h profile metadata;
- record source hash, selected columns, encoder config hash, output hash,
  train-only fit window, validation/test transform windows;
- emit stage_c_access="DENIED" and training_launched=false.

Profile screen requirements:
- rank profiles using validation-safe next-week diagnostics;
- include negative controls: shuffled outcome, future-leak sentinel, irrelevant
  feature family;
- report redundancy between profiles;
- output a shortlist that avoids redundant profile/timeframe pairs;
- negative returns are scores, not mechanical blockers.

Tests:
- Stage C rows are rejected;
- post-cutoff rows are rejected;
- PCA/regime fit metadata is train-only;
- output hashes are deterministic;
- negative controls fail as expected;
- selected shortlist is nonredundant;
- no training launched.

Commands:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stage3x_market_state_profile_worker.py _scripts/tests/test_stage3x_market_state_profile_screen_worker.py -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_market_state_profile_worker.py
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_market_state_profile_screen_worker.py
4. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stage3x*.py -q

Final report:
- files changed;
- tests run;
- profile counts by timeframe and family;
- selected nonredundant profiles;
- exact remaining blockers;
- confirmation no training launched and Stage C not touched.
```

## Copilot Spec B - agent-multi/gym-fx State Profile Plumbing

Use after Claude/Codex emits the financial-data profile contract.

```text
You are Copilot acting as a senior RL infrastructure engineer inside
agent-multi and gym-fx. You have repository access. Do not guess paths.

Repositories:
- cd /home/harveybc/Documents/GitHub/agent-multi
- cd /home/harveybc/Documents/GitHub/gym-fx

Read first:
1. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md
2. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md
3. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_market_state_profile/selected_market_state_profiles.json
4. agent-multi/tools/project3_stage3x_sac_smoke_plan.py
5. agent-multi/pipeline_plugins/_return_trace.py
6. gym-fx/app/env.py

Mission:
Add config-gated market-state profile plumbing so locked SAC smoke configs can
consume selected state profiles and prove the columns reach the observation
state.

Implement/verify:
- generated configs preserve market_state_profile_id and
  market_state_profile_hash;
- feature_list / feature_columns include market-state columns;
- observation evidence includes state-profile fields/hash;
- missing profile fields fail closed for Stage 3X locked configs;
- no-training fixtures prove 1h and 4h state-profile columns reach the env;
- no PPO/SAC/DQN algorithm source edits.

Tests:
- generated config denies Stage C;
- missing profile hash fails closed;
- state profile columns appear in observation fields;
- return trace/evidence records state profile id/hash;
- 2-profile fixture does not alter algorithm code.

Commands:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stage3x_sac_smoke_plan.py --help
3. dry-run validate against selected_market_state_profiles.json if available.

Final report:
- files changed;
- tests run;
- fields preserved;
- confirmation no training launched, Stage C not touched, PPO/SAC/DQN unchanged.
```

## ChatGPT 5.5 Pro Web Spec C - Research Review

Use only if we want an external research critique before implementing learned
embeddings.

```text
You are ChatGPT 5.5 Pro Web acting as an external research reviewer for
Project 3. You do not mutate code.

Context:
- Project 3 is a weekly-retrained portfolio/RL trading system.
- The immediate problem is selecting the best market-state representation for
  1h and 4h weekly decision windows.
- Stage C is locked and must remain locked.
- We need practical profit/risk guidance, not academic blockers.

Files attached:
1. PROJECT3_MARKET_STATE_REPRESENTATION_OPTIMIZATION_PLAN_2026_05_23.md
2. PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md
3. PHASE_3X_UNSUPERVISED_CAUSAL_AUDIT.md
4. latest stage3x_market_state_causal_contract.md
5. latest stage3x_micro_nsga synthesis summary if available

Research task:
1. Critique the proposed state profiles:
   - engineered summary;
   - PCA/robust PCA;
   - autoencoder;
   - TS2Vec/contrastive embedding;
   - PatchTST/masked patch embedding;
   - regime probabilities;
   - hybrid full.
2. Recommend the minimum implementation order for 1h and 4h.
3. Identify redundant or low-value experiments to avoid.
4. Recommend lightweight libraries/dependencies if any.
5. List failure modes and negative controls.
6. Keep Stage C locked and do not suggest broad GPU work.

Output:
- Markdown memo;
- ranked recommendation table;
- implementation risks;
- exact criteria for sending a profile to GPU smoke.
```

## Codex Immediate Tasks

Codex should do the first local integration pass before external dispatch:

1. keep G18 monitored and synthesize when complete;
2. implement small CPU profile worker if it is faster than waiting for agents;
3. update this spec if implementation changes names/paths;
4. launch no new GPU generation until current G18 status is clear.
