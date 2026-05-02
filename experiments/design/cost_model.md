# Stage 3.1 Cost Model

Updated: 2026-05-02

## Purpose

RL policies must be judged after realistic frictions. A candidate that survives only zero or optimistic costs is not a production-quality discovery and cannot advance without an explicit exception.

## Cost Scenarios

| Scenario | Purpose | Promotion use |
| --- | --- | --- |
| `optimistic` | Best reasonable fee/spread assumption for sanity and sensitivity | Not sufficient for promotion |
| `base` | Default realistic evaluation assumption | Required for Stage A promotion |
| `pessimistic` | Stress case for slippage/spread/financing/turnover | Required for Stage B and Stage C reporting |

## Default Parameters

These defaults are conservative placeholders until market-specific fee schedules are finalized.

| Asset class | Scenario | Fee bps | Spread bps | Slippage bps | Turnover penalty | Funding / financing |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Spot crypto | optimistic | 2 | 1 | 1 | 0.00 | none |
| Spot crypto | base | 5 | 3 | 3 | 0.05 | none |
| Spot crypto | pessimistic | 10 | 8 | 8 | 0.15 | none |
| Crypto perpetual | optimistic | 2 | 1 | 1 | 0.00 | observed funding where available |
| Crypto perpetual | base | 5 | 4 | 4 | 0.05 | observed funding plus stale fallback |
| Crypto perpetual | pessimistic | 10 | 10 | 10 | 0.15 | adverse funding stress |
| FX | optimistic | 0.2 | 0.5 | 0.2 | 0.00 | overnight financing ignored for intraday |
| FX | base | 0.5 | 1.0 | 0.5 | 0.02 | conservative financing for multi-day holds |
| FX | pessimistic | 1.0 | 3.0 | 1.5 | 0.08 | adverse financing stress |

## Required Report Fields

Every Stage A/B/C candidate report must include:

```text
asset_class
exchange_or_market
cost_scenario
fee_bps
spread_bps
slippage_model
funding_model
borrow_or_financing_model
minimum_order_notional
max_position_size
turnover_penalty
gross_return
net_return
turnover
trade_count
cost_to_gross_pnl_ratio
```

## Promotion Rules

- Stage A may use simplified cost assumptions, but not zero cost for promotion.
- Stage B must evaluate base and pessimistic scenarios.
- Stage C must report all three scenarios.
- Reject candidates with positive gross returns but non-positive base-cost net returns.
- Flag candidates where costs consume more than 50% of gross PnL unless there is a clear low-capital exploratory reason to keep them.
