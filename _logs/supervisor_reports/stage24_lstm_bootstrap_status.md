# Stage 2.4 LSTM Bootstrap Status

Generated: 2026-05-02T01:27:57.544494+00:00

## Status

- Bootstrap GPU learned-representation jobs completed on Dragon and Gamma.
- GPU locks were acquired and released on both machines.
- These outputs are first-pass LSTM embeddings while the full feature-extractor wrapper is being integrated.

## Results

- dragon: btcusdt 1h final val loss 0.458023; output `features/trading_asset_features/btcusdt/1h/learned_lstm.parquet`; encoder `features/learned_models/btcusdt/1h/lstm_autoencoder/encoder.keras`.
- gamma: eurusd 1h final val loss 0.158116; output `features/trading_asset_features/eurusd/1h/learned_lstm.parquet`; encoder `features/learned_models/eurusd/1h/lstm_autoencoder/encoder.keras`.
