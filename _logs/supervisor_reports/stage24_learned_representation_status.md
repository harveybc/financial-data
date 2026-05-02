# Stage 2.4 Learned Representation Status

Generated: 2026-05-02T02:00:22.510139+00:00

## LSTM Bootstrap

- Completed metadata files: 10

| Machine | Asset | TF | Val Loss | Rows | Output |
| --- | --- | --- | ---: | ---: | --- |
| dragon | btcusdt | 1h | 0.458023 | 73221 | `features/trading_asset_features/btcusdt/1h/learned_lstm.parquet` |
| dragon | btcusdt | 4h | 0.681573 | 18306 | `features/trading_asset_features/btcusdt/4h/learned_lstm.parquet` |
| dragon | btcusdt_perp | 1h | 0.523398 | 55288 | `features/trading_asset_features/btcusdt_perp/1h/learned_lstm.parquet` |
| dragon | btcusdt_perp | 4h | 0.644217 | 13807 | `features/trading_asset_features/btcusdt_perp/4h/learned_lstm.parquet` |
| dragon | ethusdt | 1h | 0.306742 | 73221 | `features/trading_asset_features/ethusdt/1h/learned_lstm.parquet` |
| gamma | ethusdt | 4h | 0.382124 | 18306 | `features/trading_asset_features/ethusdt/4h/learned_lstm.parquet` |
| gamma | eurusd | 1h | 0.158116 | 129810 | `features/trading_asset_features/eurusd/1h/learned_lstm.parquet` |
| gamma | eurusd | 4h | 0.126586 | 33732 | `features/trading_asset_features/eurusd/4h/learned_lstm.parquet` |
| gamma | usdjpy | 1h | 0.337662 | 129789 | `features/trading_asset_features/usdjpy/1h/learned_lstm.parquet` |
| omega | usdjpy | 4h | 0.367894 | 33727 | `features/trading_asset_features/usdjpy/4h/learned_lstm.parquet` |

## CNN Bootstrap

- Completed metadata files: 10

| Machine | Asset | TF | Val Loss | Rows | Output |
| --- | --- | --- | ---: | ---: | --- |
| dragon | btcusdt | 1h | 0.495557 | 73221 | `features/trading_asset_features/btcusdt/1h/learned_cnn.parquet` |
| omega | btcusdt | 4h | 0.553109 | 18306 | `features/trading_asset_features/btcusdt/4h/learned_cnn.parquet` |
| dragon | btcusdt_perp | 1h | 0.484438 | 55288 | `features/trading_asset_features/btcusdt_perp/1h/learned_cnn.parquet` |
| dragon | btcusdt_perp | 4h | 0.532272 | 13807 | `features/trading_asset_features/btcusdt_perp/4h/learned_cnn.parquet` |
| dragon | ethusdt | 1h | 0.429318 | 73221 | `features/trading_asset_features/ethusdt/1h/learned_cnn.parquet` |
| omega | ethusdt | 4h | 0.413717 | 18306 | `features/trading_asset_features/ethusdt/4h/learned_cnn.parquet` |
| gamma | eurusd | 1h | 0.247430 | 129810 | `features/trading_asset_features/eurusd/1h/learned_cnn.parquet` |
| gamma | eurusd | 4h | 0.200630 | 33732 | `features/trading_asset_features/eurusd/4h/learned_cnn.parquet` |
| gamma | usdjpy | 1h | 0.583787 | 129789 | `features/trading_asset_features/usdjpy/1h/learned_cnn.parquet` |
| gamma | usdjpy | 4h | 0.495066 | 33727 | `features/trading_asset_features/usdjpy/4h/learned_cnn.parquet` |

## SOTA Low-Cost Features

- Jobs ok: 42
- Jobs failed: 0
- Report: `_logs/supervisor_reports/stage25_sota_feature_enrichment_omega.md`

## 15m Learned Input Prep

- Gamma jobs ok: 2/5
- Crypto 15m failed on Gamma because ignored `features/trading_asset_data/<crypto>/15m.parquet` was not present there; route those prep jobs through Omega or sync crypto feature data before retrying.
