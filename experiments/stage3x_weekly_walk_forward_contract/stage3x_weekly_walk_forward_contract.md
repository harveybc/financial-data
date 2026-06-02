# Stage 3X Weekly Walk-Forward Contract

- schema_version: `project3_stage3x_weekly_walk_forward_contract_v1`
- stage_c_access: `DENIED`
- training_launched: `false`
- mode: `tiny`
- anchors: `4`
- contracts: `12`
- train_days: `14`
- validation_days: `7`
- test_days: `7`

## Anchors

| anchor | train | validation | test |
| --- | --- | --- | --- |
| anchor_2024-06-03 | 2024-05-13 to 2024-05-26 | 2024-05-27 to 2024-06-02 | 2024-06-03 to 2024-06-09 |
| anchor_2024-06-10 | 2024-05-20 to 2024-06-02 | 2024-06-03 to 2024-06-09 | 2024-06-10 to 2024-06-16 |
| anchor_2024-06-17 | 2024-05-27 to 2024-06-09 | 2024-06-10 to 2024-06-16 | 2024-06-17 to 2024-06-23 |
| anchor_2024-06-24 | 2024-06-03 to 2024-06-16 | 2024-06-17 to 2024-06-23 | 2024-06-24 to 2024-06-30 |

## First Contracts

| contract | target | broker | input assets |
| --- | --- | --- | --- |
| `btcusdt_perp__weekly__anchor_2024-06-03` | `btcusdt_perp` | `crypto_exchange_perp` | `ethusdt_perp,eurusd,audusd,gbpusd,usdjpy` |
| `eurusd__weekly__anchor_2024-06-03` | `eurusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,audusd,gbpusd,usdjpy` |
| `audusd__weekly__anchor_2024-06-03` | `audusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,eurusd,gbpusd,usdjpy` |
| `btcusdt_perp__weekly__anchor_2024-06-10` | `btcusdt_perp` | `crypto_exchange_perp` | `ethusdt_perp,eurusd,audusd,gbpusd,usdjpy` |
| `eurusd__weekly__anchor_2024-06-10` | `eurusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,audusd,gbpusd,usdjpy` |
| `audusd__weekly__anchor_2024-06-10` | `audusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,eurusd,gbpusd,usdjpy` |
| `btcusdt_perp__weekly__anchor_2024-06-17` | `btcusdt_perp` | `crypto_exchange_perp` | `ethusdt_perp,eurusd,audusd,gbpusd,usdjpy` |
| `eurusd__weekly__anchor_2024-06-17` | `eurusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,audusd,gbpusd,usdjpy` |
| `audusd__weekly__anchor_2024-06-17` | `audusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,eurusd,gbpusd,usdjpy` |
| `btcusdt_perp__weekly__anchor_2024-06-24` | `btcusdt_perp` | `crypto_exchange_perp` | `ethusdt_perp,eurusd,audusd,gbpusd,usdjpy` |
| `eurusd__weekly__anchor_2024-06-24` | `eurusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,audusd,gbpusd,usdjpy` |
| `audusd__weekly__anchor_2024-06-24` | `audusd` | `oanda_us_fx` | `btcusdt_perp,ethusdt_perp,eurusd,gbpusd,usdjpy` |
