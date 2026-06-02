# Project 3 Stage 3X Copilot Active Prompt

Use this prompt in Copilot. This is the required next coding handoff.

```text
You are Copilot acting as a senior RL infrastructure engineer inside the
agent-multi and gym-fx repos. You have repository access. Do not guess paths.

Repositories:
- cd /home/harveybc/Documents/GitHub/agent-multi
- cd /home/harveybc/Documents/GitHub/gym-fx
- Read-only context from /home/harveybc/Documents/GitHub/financial-data

Python:
- Prefer /home/harveybc/anaconda3/envs/tensorflow/bin/python when available.

Current state to verify, not assume:
- Stage C is locked and must remain locked.
- Broad GPU launch is blocked.
- Small SAC smoke planning is allowed.
- selected_feature_contracts.json exists:
  /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_target_relation_screen/selected_feature_contracts.json
- Current CPU screen summary:
  54 genomes screened, 13 PASS_CPU_SCREEN, 12 selected contracts.

Read these files first:
1. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md
2. /home/harveybc/Documents/GitHub/financial-data/work_plan/PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md
3. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_target_relation_screen/selected_feature_contracts.json
4. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_parametric_data_space/project3_data_preprocessing_search_space.schema.json
5. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_absurdity_guard/stage3x_absurdity_guard_report.json
6. /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_input_preprocessing_optimization/stage3x_input_preprocessing_matrix.csv
7. agent-multi/docs/STAGE_B_EVIDENCE_CONTRACT.md
8. agent-multi/pipeline_plugins/_return_trace.py
9. agent-multi/tools/project3_stageb_run_plan.py
10. gym-fx/app/env.py

Mission:
Prepare agent-multi/gym-fx to consume selected Stage 3X feature contracts and
emit locked SAC smoke-run configs. Do not launch training.

Implement:
1. A dry-run tool:
   tools/project3_stage3x_sac_smoke_plan.py
2. Inputs:
   - --selected-contracts pointing to selected_feature_contracts.json
   - --output-dir for generated locked configs/manifests
   - --top-n default 3
   - --seeds default 0,1,2
   - --cost-scenario default base
3. The tool must emit locked SAC configs only:
   - top N selected data contracts;
   - 3 seeds by default;
   - base cost only for smoke;
   - Stage C access DENIED;
   - final_stage_c_evaluation false;
   - stage_c_acknowledged false;
   - return_trace/evidence enabled;
   - feature_list / feature_columns populated from selected features;
   - progress file path present;
   - expected evidence path present;
   - _NOT_TO_RUN_UNTIL_STAGE_B_APPROVED true;
   - _project3_stage3x_sac_smoke true.
4. Preserve selected preprocessing fields where possible:
   - scaling_mode;
   - feature_scaling_window;
   - feature_clip;
   - window_size;
   - stage_b_force_close_obs / force-close fields if selected.
5. Add tests:
   - generated config denies Stage C;
   - missing feature list fails closed;
   - selected preprocessing fields are preserved;
   - smoke plan does not launch training;
   - evidence path contract is present;
   - generated configs use SAC only.

Hard rules:
- Do not launch training.
- Do not touch Stage C.
- Do not change PPO/SAC/DQN algorithm source.
- Do not weaken evidence guards.
- Do not unlock broad GPU launch.

Commands:
1. /home/harveybc/anaconda3/envs/tensorflow/bin/python -m pytest tests/unit -q
2. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stage3x_sac_smoke_plan.py --help
3. /home/harveybc/anaconda3/envs/tensorflow/bin/python tools/project3_stage3x_sac_smoke_plan.py --dry-run --validate-only

Final report:
- files changed;
- tests run;
- config count;
- example locked config path;
- exact financial-data input contract expected;
- confirmation no training launched and Stage C not touched.
```
