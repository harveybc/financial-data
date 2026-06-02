# Stage 3X Micro-NSGA Plan

- Generated: `2026-05-19T10:32:28.438867+00:00`
- Stage C access: `DENIED`
- Training launched by this worker: `False`
- Micro-NSGA plan allowed: `True`
- Next action: `write_locked_stage3x_micro_nsga_configs`
- Parent contracts: `3`
- Micro individuals: `12`
- Expected locked configs: `36`

## Eligible Parent Contracts

- `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected`
- `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p04__selected`
- `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p05__selected`

## Commands

Validate only:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python /home/harveybc/Documents/GitHub/agent-multi/tools/project3_stage3x_sac_smoke_plan.py --selected-contracts /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_micro_nsga_plan/selected_feature_contracts_micro_nsga_seed_population.json --output-dir /home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_micro_nsga_plan --top-n 12 --seeds 0,1,2 --cost-scenario base --validate-only
```

Write locked plan files, still no training:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python /home/harveybc/Documents/GitHub/agent-multi/tools/project3_stage3x_sac_smoke_plan.py --selected-contracts /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_micro_nsga_plan/selected_feature_contracts_micro_nsga_seed_population.json --output-dir /home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_micro_nsga_plan --top-n 12 --seeds 0,1,2 --cost-scenario base
```
