# CryptoQuant

Stage 1.5 paid CryptoQuant acquisition for Project 3.

The worker fetches high-value Professional-tier endpoints that validated at runtime: BTC/ETH exchange flows, BTC miner flows, selected BTC/ETH market and flow indicators, and stablecoin supply/exchange-flow metrics.

Observed API behavior on 2026-05-01: the Professional plan accepts current/recent daily pulls, while older explicit ranges such as 2024 and 2017 return `Out of allowed request range` for tested metrics. Treat this acquisition as recent-window paid data unless CryptoQuant support confirms a historical export path.

Generated: 2026-05-02T00:00:28.234939+00:00
