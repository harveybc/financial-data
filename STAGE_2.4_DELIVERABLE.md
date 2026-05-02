# Stage 2.4 Deliverable

Generated: 2026-05-02T03:08:20.898156+00:00

## Status

- Learned-representation generation is complete for the active Stage A universe.
- LSTM and CNN autoencoder embeddings are available for BTC/USDT, ETH/USDT, BTCUSDT perpetual, EUR/USD, and USD/JPY across 5m, 15m, 1h, and 4h.
- Duplicate metadata exists for two 5m CNN jobs because Dragon and Gamma briefly duplicated work before the scheduler reservation fix; the resulting feature path is the same canonical deliverable path for each asset/timeframe.

## Counts

- Autoencoder metadata records: 42
- Learned parquet feature files: 40
- Model files: 120

## Output Roots

- `features/trading_asset_features/<asset>/<tf>/learned_lstm.parquet`
- `features/trading_asset_features/<asset>/<tf>/learned_cnn.parquet`
- `features/learned_models/<asset>/<tf>/<method>_autoencoder/`
- `_metadata/stage24_*_autoencoder_<machine>_<asset>_<tf>.json`

## Job Summary

| Asset | TF | Method | Machine | Rows | Final Val Loss | Metadata |
| --- | --- | --- | --- | ---: | ---: | --- |
| btcusdt | 15m | cnn | gamma | 293020 | 0.475757 | `_metadata/stage24_cnn_autoencoder_gamma_btcusdt_15m.json` |
| btcusdt_perp | 15m | cnn | omega | 221338 | 0.454018 | `_metadata/stage24_cnn_autoencoder_omega_btcusdt_perp_15m.json` |
| ethusdt | 15m | cnn | dragon | 293020 | 0.371579 | `_metadata/stage24_cnn_autoencoder_dragon_ethusdt_15m.json` |
| eurusd | 15m | cnn | gamma | 518623 | 0.243716 | `_metadata/stage24_cnn_autoencoder_gamma_eurusd_15m.json` |
| usdjpy | 15m | cnn | dragon | 518536 | 0.497860 | `_metadata/stage24_cnn_autoencoder_dragon_usdjpy_15m.json` |
| btcusdt | 15m | lstm | gamma | 293020 | 0.281495 | `_metadata/stage24_lstm_autoencoder_gamma_btcusdt_15m.json` |
| btcusdt_perp | 15m | lstm | omega | 221338 | 0.312934 | `_metadata/stage24_lstm_autoencoder_omega_btcusdt_perp_15m.json` |
| ethusdt | 15m | lstm | dragon | 293020 | 0.219074 | `_metadata/stage24_lstm_autoencoder_dragon_ethusdt_15m.json` |
| eurusd | 15m | lstm | gamma | 518623 | 0.143080 | `_metadata/stage24_lstm_autoencoder_gamma_eurusd_15m.json` |
| usdjpy | 15m | lstm | dragon | 518536 | 0.294272 | `_metadata/stage24_lstm_autoencoder_dragon_usdjpy_15m.json` |
| btcusdt | 1h | cnn | dragon | 73221 | 0.495557 | `_metadata/stage24_cnn_autoencoder_dragon_btcusdt_1h.json` |
| btcusdt_perp | 1h | cnn | dragon | 55288 | 0.484438 | `_metadata/stage24_cnn_autoencoder_dragon_btcusdt_perp_1h.json` |
| ethusdt | 1h | cnn | dragon | 73221 | 0.429318 | `_metadata/stage24_cnn_autoencoder_dragon_ethusdt_1h.json` |
| eurusd | 1h | cnn | gamma | 129810 | 0.247430 | `_metadata/stage24_cnn_autoencoder_gamma_eurusd_1h.json` |
| usdjpy | 1h | cnn | gamma | 129789 | 0.583787 | `_metadata/stage24_cnn_autoencoder_gamma_usdjpy_1h.json` |
| btcusdt | 1h | lstm | dragon | 73221 | 0.458023 | `_metadata/stage24_lstm_autoencoder_dragon_btcusdt_1h.json` |
| btcusdt_perp | 1h | lstm | dragon | 55288 | 0.523398 | `_metadata/stage24_lstm_autoencoder_dragon_btcusdt_perp_1h.json` |
| ethusdt | 1h | lstm | dragon | 73221 | 0.306742 | `_metadata/stage24_lstm_autoencoder_dragon_ethusdt_1h.json` |
| eurusd | 1h | lstm | gamma | 129810 | 0.158116 | `_metadata/stage24_lstm_autoencoder_gamma_eurusd_1h.json` |
| usdjpy | 1h | lstm | gamma | 129789 | 0.337662 | `_metadata/stage24_lstm_autoencoder_gamma_usdjpy_1h.json` |
| btcusdt | 4h | cnn | omega | 18306 | 0.553109 | `_metadata/stage24_cnn_autoencoder_omega_btcusdt_4h.json` |
| btcusdt_perp | 4h | cnn | dragon | 13807 | 0.532272 | `_metadata/stage24_cnn_autoencoder_dragon_btcusdt_perp_4h.json` |
| ethusdt | 4h | cnn | omega | 18306 | 0.413717 | `_metadata/stage24_cnn_autoencoder_omega_ethusdt_4h.json` |
| eurusd | 4h | cnn | gamma | 33732 | 0.200630 | `_metadata/stage24_cnn_autoencoder_gamma_eurusd_4h.json` |
| usdjpy | 4h | cnn | gamma | 33727 | 0.495066 | `_metadata/stage24_cnn_autoencoder_gamma_usdjpy_4h.json` |
| btcusdt | 4h | lstm | dragon | 18306 | 0.681573 | `_metadata/stage24_lstm_autoencoder_dragon_btcusdt_4h.json` |
| btcusdt_perp | 4h | lstm | dragon | 13807 | 0.644217 | `_metadata/stage24_lstm_autoencoder_dragon_btcusdt_perp_4h.json` |
| ethusdt | 4h | lstm | gamma | 18306 | 0.382124 | `_metadata/stage24_lstm_autoencoder_gamma_ethusdt_4h.json` |
| eurusd | 4h | lstm | gamma | 33732 | 0.126586 | `_metadata/stage24_lstm_autoencoder_gamma_eurusd_4h.json` |
| usdjpy | 4h | lstm | omega | 33727 | 0.367894 | `_metadata/stage24_lstm_autoencoder_omega_usdjpy_4h.json` |
| btcusdt | 5m | cnn | dragon | 879166 | 0.441691 | `_metadata/stage24_cnn_autoencoder_dragon_btcusdt_5m.json` |
| btcusdt | 5m | cnn | gamma | 879166 | 0.442055 | `_metadata/stage24_cnn_autoencoder_gamma_btcusdt_5m.json` |
| btcusdt_perp | 5m | cnn | gamma | 664138 | 0.412284 | `_metadata/stage24_cnn_autoencoder_gamma_btcusdt_perp_5m.json` |
| ethusdt | 5m | cnn | dragon | 879166 | 0.329205 | `_metadata/stage24_cnn_autoencoder_dragon_ethusdt_5m.json` |
| ethusdt | 5m | cnn | gamma | 879166 | 0.326370 | `_metadata/stage24_cnn_autoencoder_gamma_ethusdt_5m.json` |
| eurusd | 5m | cnn | gamma | 1551965 | 0.234545 | `_metadata/stage24_cnn_autoencoder_gamma_eurusd_5m.json` |
| usdjpy | 5m | cnn | dragon | 1551181 | 0.457368 | `_metadata/stage24_cnn_autoencoder_dragon_usdjpy_5m.json` |
| btcusdt | 5m | lstm | dragon | 879166 | 0.281515 | `_metadata/stage24_lstm_autoencoder_dragon_btcusdt_5m.json` |
| btcusdt_perp | 5m | lstm | gamma | 664138 | 0.258029 | `_metadata/stage24_lstm_autoencoder_gamma_btcusdt_perp_5m.json` |
| ethusdt | 5m | lstm | dragon | 879166 | 0.184675 | `_metadata/stage24_lstm_autoencoder_dragon_ethusdt_5m.json` |
| eurusd | 5m | lstm | gamma | 1551965 | 0.142540 | `_metadata/stage24_lstm_autoencoder_gamma_eurusd_5m.json` |
| usdjpy | 5m | lstm | dragon | 1551181 | 0.281716 | `_metadata/stage24_lstm_autoencoder_dragon_usdjpy_5m.json` |

## Validation Evidence

- `_logs/supervisor_reports/stage24_progress_audit_omega.md` reports 40/40 jobs complete.
- The event daemon status is `_logs/supervisor_reports/project3_event_daemon_status.md`.
- GPU lock handling and duplicate assignment prevention are implemented in `_scripts/orchestration/project3_event_daemon.py`.

## Phase 3 Readiness Note

Stage 3.1 can consume the 1h/4h learned LSTM/CNN files immediately. The 5m learned files are now also complete, but Phase 3 should still honor the pre-registered design and avoid held-out 2025 reuse outside Stage C.
