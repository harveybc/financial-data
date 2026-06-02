# Project 3 Stage 3X Claude Review Prompt

Use this prompt in Claude only if you want a parallel review/hardening pass.
Codex already implemented the target-relation worker, so Claude should review
and harden rather than duplicate it.

```text
You are Claude acting as a senior quantitative engineering reviewer inside the
financial-data repo. You have repository access. Do not guess paths.

Repository:
- cd /home/harveybc/Documents/GitHub/financial-data

Python:
- Use /home/harveybc/anaconda3/envs/tensorflow/bin/python
- Do not assume "python" is on PATH.

Current state to verify, not assume:
- Stage C access is DENIED.
- No training should be launched.
- stage3x_target_relation_screen_worker.py exists and produced:
  54 genomes screened, 13 PASS_CPU_SCREEN, 12 selected contracts.
- Broad GPU launch is still blocked; small SAC smoke planning is allowed.

Read these files first:
1. work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md
2. work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md
3. _scripts/workers/stage3x_target_relation_screen_worker.py
4. _scripts/tests/test_stage3x_target_relation_screen_worker.py
5. experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.json
6. experiments/stage3x_target_relation_screen/stage3x_target_relation_screen.md
7. experiments/stage3x_target_relation_screen/selected_feature_contracts.json
8. experiments/stage3x_absurdity_guard/stage3x_absurdity_guard_report.json

Mission:
Review and harden the Stage 3X target-relation screen. Do not duplicate the
worker unless a defect requires edits.

Review:
1. Stage C firewall:
   - DATE_TIME >= 2025-01-01 must fail closed.
2. Feature ranking:
   - known signal should rank above noise;
   - constant / near-constant / missing-heavy features must be penalized;
   - selected features must not include forward-return target columns.
3. Cost-aware sanity:
   - contracts with negative proxy return must not PASS_CPU_SCREEN;
   - high IC alone must not be enough.
4. Output contracts:
   - selected_feature_contracts.json must contain enough fields for agent-multi
     SAC smoke planning;
   - all outputs keep stage_c_access DENIED and training_launched false.
5. Performance:
   - worker must cache per-dataset diagnostics and avoid recomputing expensive
     MI for every selection method.

Allowed edits:
- _scripts/workers/stage3x_target_relation_screen_worker.py
- _scripts/tests/test_stage3x_target_relation_screen_worker.py
- generated experiments/stage3x_target_relation_screen artifacts
- work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md only if the spec
  needs a correction

Commands:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest _scripts/tests/test_stage3x_target_relation_screen_worker.py -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_target_relation_screen_worker.py
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python _scripts/workers/stage3x_absurdity_guard_worker.py

Final report:
- defects found or "no defects found";
- files changed;
- tests run;
- selected contract count;
- exact remaining blockers;
- confirmation no training launched and Stage C not touched.
```
