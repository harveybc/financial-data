# Project 3 Weekly Pool Seed Plan

- Schema: `project3_weekly_pool_seed_plan_v2`
- Stage C access: `DENIED`
- Training launched: `false`
- Input: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/inputs/solusdt/1h/kitchen_sink_guarded/train.csv`
- Rows: `29332` from `2020-08-26 00:00:00` to `2023-12-31 23:00:00`
- Early-stop train-tail days: `7`
- Validation days: `7`
- Test days: `7`
- Execution profile: ``
- Jobs: `2`
- Subjobs: `26`
- Skipped windows: `0`

## Enqueued Jobs

| job | policy | train years | recent months | subjobs | features |
|---|---|---:|---:|---:|---:|
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_3y` | `scratch_n_years` | 3 |  | 13 | 121 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_start_chain_3y` | `warm_start_chain_n_years` | 3 |  | 13 | 121 |

## Subjobs

| subjob | depends on | train | validation | test | rows |
|---|---|---|---|---|---|
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231218` | `` | `2020-12-18 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | `2023-12-25 00:00:00 -> 2024-01-01 00:00:00` | 26261/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231211` | `` | `2020-12-11 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | 26261/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231204` | `` | `2020-12-04 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | 26261/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231127` | `` | `2020-11-27 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231120` | `` | `2020-11-20 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231113` | `` | `2020-11-13 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231106` | `` | `2020-11-06 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231030` | `` | `2020-10-30 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231023` | `` | `2020-10-23 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231016` | `` | `2020-10-16 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231009` | `` | `2020-10-09 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20231002` | `` | `2020-10-02 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_scratch_ty3_20230925` | `` | `2020-09-25 00:00:00 -> 2023-09-25 00:00:00` | `2023-09-25 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20230925` | `` | `2020-09-25 00:00:00 -> 2023-09-25 00:00:00` | `2023-09-25 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231002` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20230925` | `2020-10-02 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231009` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231002` | `2020-10-09 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231016` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231009` | `2020-10-16 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231023` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231016` | `2020-10-23 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231030` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231023` | `2020-10-30 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231106` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231030` | `2020-11-06 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231113` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231106` | `2020-11-13 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231120` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231113` | `2020-11-20 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231127` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231120` | `2020-11-27 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | 26260/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231204` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231127` | `2020-12-04 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | 26261/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231211` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231204` | `2020-12-11 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | 26261/168/168 |
| `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231218` | `solusdt_1h_kitchen_sink_guarded_all_available_1h_sac_warm_ty3_20231211` | `2020-12-18 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | `2023-12-25 00:00:00 -> 2024-01-01 00:00:00` | 26261/168/168 |
