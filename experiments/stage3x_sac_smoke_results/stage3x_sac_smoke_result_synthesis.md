# Stage 3X SAC Smoke Result Synthesis

- Generated: `2026-05-19T10:37:22.375693+00:00`
- Stage C access: `DENIED`
- Task count: `12`
- Done / failed / running / pending: `11` / `1` / `0` / `0`
- Evidence files validated: `11`

## Contract Summary

| contract | broker profile | policy band (target/warn/hard) | median val tpw | median test tpw | test cost/gross | costs | done | failed | median val return | median test return | force-close obs | action | blockers | warnings |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- |
| `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected` | `crypto_exchange_perp` | `3-6 / >12 / 24` | 1.98 | 2.26 | 0.51 | `base` | 3 | 0 | -0.05050602333670684 | 0.04598392347549418 | `True` | `eligible_for_stage3x_micro_nsga` | `` | `COST_TO_GROSS_EDGE_HIGH, NON_POSITIVE_MEDIAN_VALIDATION_RETURN, MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN, MICRO_NSGA_BASE_COST_ONLY` |
| `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p04__selected` | `crypto_exchange_perp` | `3-6 / >12 / 24` | 1.98 | 2.26 | 0.51 | `base` | 3 | 0 | -0.05050602333670684 | 0.04598392347549418 | `True` | `eligible_for_stage3x_micro_nsga` | `` | `COST_TO_GROSS_EDGE_HIGH, NON_POSITIVE_MEDIAN_VALIDATION_RETURN, MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN, MICRO_NSGA_BASE_COST_ONLY` |
| `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p05__selected` | `crypto_exchange_perp` | `3-6 / >12 / 24` | 1.98 | 2.26 | 0.51 | `base` | 3 | 0 | -0.05050602333670684 | 0.04598392347549418 | `True` | `eligible_for_stage3x_micro_nsga` | `` | `COST_TO_GROSS_EDGE_HIGH, NON_POSITIVE_MEDIAN_VALIDATION_RETURN, MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN, MICRO_NSGA_BASE_COST_ONLY` |
| `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p06__selected` | `crypto_exchange_perp` | `3-6 / >12 / 24` | 1.98 | 2.26 | 0.51 | `base` | 2 | 1 | -0.05050602333670684 | 0.04598392347549418 | `True` | `eligible_for_stage3x_micro_nsga` | `` | `COST_TO_GROSS_EDGE_HIGH, FAILED_OR_ABORTED_SEEDS, NON_POSITIVE_MEDIAN_VALIDATION_RETURN, MICRO_NSGA_WILL_OPTIMIZE_NON_POSITIVE_VALIDATION_RETURN, MICRO_NSGA_SEED_FAILURES_REMAIN_IN_LEDGER, MICRO_NSGA_BASE_COST_ONLY` |

## Decision

- Broad GPU launch allowed: `False`
- Stage C allowed: `False`
- Next action: `prepare_stage3x_micro_nsga_plan`

## Trade-Frequency Policy (FINRA/OANDA memo §5.2)

- FX 4h: target 3/week, warn >6/week, hard max 12/week.
- FX 1h: target 6/week, warn >12/week, hard max 24/week.
- OANDA crypto 4h: target 1-3/week, warn >3/week, hard max 12/week.
- OANDA crypto 1h: target 3-6/week, warn >12/week, hard max 24/week.
- Non-OANDA crypto/perp 4h: target 3-6/week, warn >12/week, hard max 24/week.
- Non-OANDA crypto/perp 1h: target 6-12/week, warn >24/week, hard max 36/week.

## Notes

- This smoke run validated that feature hashes and evidence files are now emitted for completed cells.
- Force-close/calendar observation fields present in all completed evidence: `True`.
- Eligible targeted follow-up contracts: ``.
- Eligible Stage 3X micro-NSGA contracts: `btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p03__selected, btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p04__selected, btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p05__selected, btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p06__selected`.
- Broker profiles are explicitly resolved for every summarized smoke contract.
- Cost-to-gross-edge warning threshold: `0.75`.
