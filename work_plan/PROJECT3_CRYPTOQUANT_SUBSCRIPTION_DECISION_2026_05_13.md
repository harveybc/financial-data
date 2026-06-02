# Project 3 CryptoQuant Subscription Decision

Generated: 2026-05-13

## Decision

Do not keep paying for CryptoQuant for Project 3 historical RL work unless
CryptoQuant enables or provides historical data export that covers the actual
train/validation/test research windows.

Recommended action:

```text
cancel_or_pause_unless_historical_export_is_confirmed
```

This is not because CryptoQuant is low quality. It is because the acquired API
payload is recent-window only and therefore cannot support the current Project 3
historical Stage B/Stage C workflow.

## Evidence From Repo

Acquisition report:

- `_logs/supervisor_reports/stage15_cryptoquant_acquisition.md`
- requested endpoints: `97`
- successful endpoints: `97`
- empty endpoints: `0`
- failed endpoints: `0`
- rows acquired: `9700`
- files: `97`

Value probe:

- `_logs/supervisor_reports/stage15_cryptoquant_value_probe.md`
- recommendation: `cancel_unless_historical_export_is_enabled`
- global start: `2026-01-21`
- global end: `2026-05-01`
- coverage days: `101`

Local parquet scan on 2026-05-13 confirmed:

- files: `97`
- global min timestamp: `2026-01-21 00:00:00+00:00`
- global max timestamp: `2026-05-01 00:00:00+00:00`

## Why This Blocks Project 3 Use

Project 3 needs historical training and validation data before Stage C.
The current Stage C heldout boundary is:

```text
2025-01-01
```

The acquired CryptoQuant data begins in 2026, so it is after the Stage C
firewall. It cannot be used to tune, select, repair, or justify candidates in
the current Stage B workflow.

It may be useful for:

- future live-monitoring research;
- a future post-Project-3 forward paper-trading lane;
- deciding whether historical CryptoQuant export is worth buying;
- exploratory source-family design.

It is not enough for:

- Stage B train/validation evidence;
- Stage C promotion evidence;
- source-family ablation over 2017-2024;
- deciding that CryptoQuant improves RL trading performance historically.

## Keep Subscription Only If

Keep or renew only if CryptoQuant support confirms one of these:

1. API access to the required endpoints back to at least `2017-01-01`, or
2. downloadable historical export for BTC/ETH/stablecoin exchange-flow,
   leverage, whale, reserve, SOPR/MVRV, and miner-flow families, with usable
   timestamp semantics.

Minimum required coverage for Project 3:

- BTC and ETH;
- exchange inflow/outflow/netflow/reserve by all-exchange and major venues;
- stablecoin supply/reserve/flow metrics;
- leverage/open-interest style metrics if available;
- miner flow/reserve metrics for BTC;
- daily or better timestamp coverage;
- availability/release timestamp or a documented provider lag;
- no rows at or after `2025-01-01` used for candidate selection.

## Message To Send CryptoQuant Support

```text
Hello,

I am using CryptoQuant for private quantitative research. The Professional API
calls currently return roughly the most recent 100 daily rows per endpoint. I
need historical export/API access for BTC, ETH, and stablecoin metrics back to
at least 2017-01-01, including exchange inflow/outflow/netflow/reserve,
stablecoin supply/reserve/flows, leverage/market indicators, SOPR/MVRV-style
metrics, whale ratios, and BTC miner flows.

Can my current plan access that history through API parameters or a downloadable
export? If not, which plan/export product is required, what is the cost, and
what timestamp/availability semantics are included?

This is for internal research only, not redistribution.
```

## Next Project Action

Do not spend GPU time on CryptoQuant Stage B ablations until historical access
is confirmed.

If historical access is confirmed, create a matched diagnostic lane:

```text
best_free_crypto_stack
vs
best_free_crypto_stack_plus_cryptoquant
```

Matched on:

- asset;
- timeframe;
- algorithm;
- seed;
- split;
- cost scenario;
- run budget.

If historical access is not confirmed, keep the acquired parquet files for
documentation and cancel/pause the subscription before the next billing cycle.
