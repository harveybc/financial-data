# Stage 3X Absurdity Guard

Generated UTC: `2026-05-19T10:37:22.512686+00:00`

- Stage C access: `DENIED`
- Training launched by this worker: `False`
- Broad GPU launch allowed: `False`
- Small SAC smoke allowed: `True`
- Selected feature contracts: `564`
- Smoke contracts summarized: `4`
- Smoke contracts missing broker profile: `0`
- Smoke contracts over trade-frequency hard max: `0`
- Smoke contracts with OANDA FX calendar violation: `0`
- Small CPU/dry-run work allowed: `True`
- Issues: `1`

## Issues

| severity | code | required action |
| --- | --- | --- |
| `block_broad_gpu` | `NO_STAGE_B_PROMOTION` | Run data/preprocessing target-relation screening before any new broad GPU batch. |
