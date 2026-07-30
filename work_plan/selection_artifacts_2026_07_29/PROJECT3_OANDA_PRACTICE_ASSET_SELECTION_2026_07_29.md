# OANDA Practice Asset Selection

This table is generated from validation-only E4 evidence and the comparable
Project3 annual survey. The score orders live-observation effort; it is not
a claim that unlike experimental protocols have a common financial scale.

| Priority | Instrument | Role | TF | Score | E4 seeds | E4 annual return | E4 annual RAP | Historical trades/week | Artifact |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `EUR_USD` | execution_control | 1h | 34.5 | - | - | - | 0.000 | `-` |
| 2 | `GBP_JPY` | activity_diversification_shadow | 1h | 80.3 | 3 | -1.739% | -7.344% | 10.863 | `e4__gbpjpy__1h__seed2701__c977321ae9c812ab` |
| 3 | `USD_CAD` | long_horizon_alpha_shadow | 4h | 74.0 | 3 | -0.053% | -0.690% | 0.000 | `e4__usdcad__4h__seed2703__fdc025aaa9b531a9` |
| 4 | `USD_JPY` | activity_alternate | 1h | 71.8 | 3 | -2.553% | -8.455% | 8.275 | `e4__usdjpy__1h__seed2701__7e94950e30223142` |
| 5 | `NZD_USD` | short_horizon_alpha_shadow | 1h | 68.2 | 3 | -0.182% | -0.953% | 0.000 | `e4__nzdusd__1h__seed2701__eb64de262982b935` |
| 6 | `EUR_JPY` | historical_positive_comparator | 4h | 42.0 | - | - | - | 2.647 | `-` |

## Decision

- Observe all listed instruments during the 24-hour read-only phase.
- Use `USD_CAD` and `NZD_USD` as the first model-linked shadows.
- Keep `GBP_JPY` and `USD_JPY` to expose the higher-activity path.
- Keep `EUR_USD` as the execution control and `EUR_JPY` as a historical comparator.
- Submit no order until account preflight, 24-hour observation, and explicit protected-canary authorization pass.

One live day calibrates plumbing and costs. One live week supplies descriptive
execution drift; it is not enough evidence to promote or reject an alpha model.
