# Stage 3X SAC Smoke Request

Generated UTC: `2026-05-19T10:36:43.709175+00:00`

- Stage C access: `DENIED`
- Training launched by this worker: `False`
- Request mode: `small_sac_smoke`
- Request allowed: `True`
- Selected contracts available: `564`
- Top contracts requested: `4`
- Seeds: `[0, 1, 2]`
- Cost scenarios: `['base']`
- Expected configs: `12`
- Expected manifest: `/home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_sac_smoke_plan/stage3x_sac_smoke_plan_manifest.json`
- Smoke shortlist: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_sac_smoke_request/selected_feature_contracts_smoke_shortlist.json`

## Selected Contracts

- `btcusdt_perp__4h__crypto_full__regime_conditioned_topk__p00__selected`
- `btcusdt__1h__learned_cnn__rank_ic_topk__p00__selected`
- `btcusdt__4h__learned_cnn__rank_ic_topk__p00__selected`
- `btcusdt__1h__learned_lstm__regime_conditioned_topk__p00__selected`

## Commands

Validate only:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python /home/harveybc/Documents/GitHub/agent-multi/tools/project3_stage3x_sac_smoke_plan.py --selected-contracts /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_sac_smoke_request/selected_feature_contracts_smoke_shortlist.json --output-dir /home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_sac_smoke_plan --top-n 4 --seeds 0,1,2 --cost-scenario base --validate-only
```

Write locked plan files, still no training:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python /home/harveybc/Documents/GitHub/agent-multi/tools/project3_stage3x_sac_smoke_plan.py --selected-contracts /home/harveybc/Documents/GitHub/financial-data/experiments/stage3x_sac_smoke_request/selected_feature_contracts_smoke_shortlist.json --output-dir /home/harveybc/Documents/GitHub/agent-multi/experiments/stage3x_sac_smoke_plan --top-n 4 --seeds 0,1,2 --cost-scenario base
```
