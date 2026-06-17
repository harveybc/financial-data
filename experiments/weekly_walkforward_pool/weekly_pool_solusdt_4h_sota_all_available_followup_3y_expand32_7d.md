# Project 3 Weekly Pool Seed Plan

- Schema: `project3_weekly_pool_seed_plan_v2`
- Stage C access: `DENIED`
- Training launched: `false`
- Input: `/home/harveybc/Documents/GitHub/financial-data/experiments/stage_a_screening/inputs/solusdt/4h/sota_low_cost/train.csv`
- Rows: `7175` from `2020-09-22 04:00:00` to `2023-12-31 20:00:00`
- Early-stop train-tail days: `7`
- Validation days: `7`
- Test days: `7`
- Execution profile: ``
- Jobs: `2`
- Subjobs: `26`
- Skipped windows: `38`

## Enqueued Jobs

| job | policy | train years | recent months | subjobs | features |
|---|---|---:|---:|---:|---:|
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_3y` | `scratch_n_years` | 3 |  | 13 | 83 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_start_chain_3y` | `warm_start_chain_n_years` | 3 |  | 13 | 83 |

## Subjobs

| subjob | depends on | train | validation | test | rows |
|---|---|---|---|---|---|
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231218` | `` | `2020-12-18 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | `2023-12-25 00:00:00 -> 2024-01-01 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231211` | `` | `2020-12-11 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231204` | `` | `2020-12-04 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231127` | `` | `2020-11-27 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231120` | `` | `2020-11-20 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231113` | `` | `2020-11-13 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231106` | `` | `2020-11-06 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231030` | `` | `2020-10-30 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231023` | `` | `2020-10-23 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231016` | `` | `2020-10-16 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231009` | `` | `2020-10-09 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20231002` | `` | `2020-10-02 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_scratch_ty3_20230925` | `` | `2020-09-25 00:00:00 -> 2023-09-25 00:00:00` | `2023-09-25 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20230925` | `` | `2020-09-25 00:00:00 -> 2023-09-25 00:00:00` | `2023-09-25 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231002` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20230925` | `2020-10-02 00:00:00 -> 2023-10-02 00:00:00` | `2023-10-02 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231009` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231002` | `2020-10-09 00:00:00 -> 2023-10-09 00:00:00` | `2023-10-09 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231016` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231009` | `2020-10-16 00:00:00 -> 2023-10-16 00:00:00` | `2023-10-16 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231023` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231016` | `2020-10-23 00:00:00 -> 2023-10-23 00:00:00` | `2023-10-23 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231030` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231023` | `2020-10-30 00:00:00 -> 2023-10-30 00:00:00` | `2023-10-30 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231106` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231030` | `2020-11-06 00:00:00 -> 2023-11-06 00:00:00` | `2023-11-06 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231113` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231106` | `2020-11-13 00:00:00 -> 2023-11-13 00:00:00` | `2023-11-13 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231120` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231113` | `2020-11-20 00:00:00 -> 2023-11-20 00:00:00` | `2023-11-20 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231127` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231120` | `2020-11-27 00:00:00 -> 2023-11-27 00:00:00` | `2023-11-27 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231204` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231127` | `2020-12-04 00:00:00 -> 2023-12-04 00:00:00` | `2023-12-04 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231211` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231204` | `2020-12-11 00:00:00 -> 2023-12-11 00:00:00` | `2023-12-11 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | 6570/42/42 |
| `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231218` | `solusdt_4h_sota_low_cost_all_available_sac_warm_ty3_20231211` | `2020-12-18 00:00:00 -> 2023-12-18 00:00:00` | `2023-12-18 00:00:00 -> 2023-12-25 00:00:00` | `2023-12-25 00:00:00 -> 2024-01-01 00:00:00` | 6570/42/42 |

## Skipped

| train years | anchor | reason |
|---:|---|---|
| 3 | `2023-09-18` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-09-11` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-09-04` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-28` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-21` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-14` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-07` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-31` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-24` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-17` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-10` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-03` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-26` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-19` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-12` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-05` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-05-29` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-05-22` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-05-15` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-05-15` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-05-22` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-05-29` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-05` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-12` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-19` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-06-26` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-03` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-10` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-17` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-24` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-07-31` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-07` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-14` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-21` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-08-28` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-09-04` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-09-11` | `INSUFFICIENT_HISTORY` |
| 3 | `2023-09-18` | `INSUFFICIENT_HISTORY` |
