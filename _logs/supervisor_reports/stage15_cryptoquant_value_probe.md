# CryptoQuant Subscription Value Probe

Generated: 2026-05-02T03:05:47.560765+00:00

## Decision

- Recommendation: `cancel_unless_historical_export_is_enabled`
- Reason: API coverage is recent-window only, so it cannot support Project 3 historical RL backtests.
- Coverage days: 101
- Best absolute Spearman IC in quick probe: 0.7208

## Coverage

- Files: 97
- Rows: 9700
- Global start: 2026-01-21 00:00:00+00:00
- Global end: 2026-05-01 00:00:00+00:00

## Top Exploratory Lead/Lag Results

| Asset | Metric | Column | Transform | Horizon | Days | Spearman IC | Path |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| btcusdt | stablecoin_supply_all_token | supply_circulating | level | 7 | 95 | -0.7208 | `alternative_data/cryptoquant/stablecoin_network/stablecoin_supply_all_token.parquet` |
| ethusdt | stablecoin_supply_all_token | supply_circulating | level | 7 | 95 | -0.6694 | `alternative_data/cryptoquant/stablecoin_network/stablecoin_supply_all_token.parquet` |
| btcusdt | btc_stablecoins_ratio_all_exchange | stablecoins_ratio_usd | level | 7 | 95 | -0.6322 | `alternative_data/cryptoquant/btc_indicators/btc_stablecoins_ratio_all_exchange.parquet` |
| ethusdt | eth_exchange_reserve_all_exchange | reserve_usd | level | 7 | 95 | -0.5902 | `alternative_data/cryptoquant/eth_exchange_flows/eth_exchange_reserve_all_exchange.parquet` |
| btcusdt | btc_realized_price | realized_price | level | 7 | 95 | -0.5840 | `alternative_data/cryptoquant/btc_indicators/btc_realized_price.parquet` |
| ethusdt | eth_exchange_reserve_binance | reserve_usd | level | 7 | 95 | -0.5596 | `alternative_data/cryptoquant/eth_exchange_flows/eth_exchange_reserve_binance.parquet` |
| btcusdt | stablecoin_supply_usdc | supply_circulating | level | 7 | 94 | -0.5561 | `alternative_data/cryptoquant/stablecoin_network/stablecoin_supply_usdc.parquet` |
| btcusdt | btc_stablecoins_ratio_all_exchange | stablecoins_ratio_usd | level | 3 | 99 | -0.5522 | `alternative_data/cryptoquant/btc_indicators/btc_stablecoins_ratio_all_exchange.parquet` |
| ethusdt | stablecoin_reserve_usdt_eth_all_exchange | reserve | level | 7 | 95 | -0.5506 | `alternative_data/cryptoquant/stablecoin_exchange_flows/stablecoin_reserve_usdt_eth_all_exchange.parquet` |
| btcusdt | stablecoin_capitalization_usdc | market_cap | level | 7 | 95 | -0.5494 | `alternative_data/cryptoquant/stablecoin_market/stablecoin_capitalization_usdc.parquet` |
| ethusdt | eth_exchange_reserve_okx | reserve_usd | level | 7 | 95 | -0.5343 | `alternative_data/cryptoquant/eth_exchange_flows/eth_exchange_reserve_okx.parquet` |
| btcusdt | btc_exchange_reserve_kraken | reserve | zscore | 7 | 85 | -0.5170 | `alternative_data/cryptoquant/btc_exchange_flows/btc_exchange_reserve_kraken.parquet` |

## Interpretation

- The current Professional API data is useful as recent/live context, but not enough for Project 3 historical RL experiments.
- Keep only if CryptoQuant can provide historical export/API coverage back through the training and validation windows.
- Otherwise cancel after preserving the acquired parquet files and documentation.
