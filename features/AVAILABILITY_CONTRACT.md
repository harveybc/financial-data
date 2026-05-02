# Feature Availability Contract

Updated: 2026-05-02

## Purpose

Phase 3 must evaluate only information that would have been observable at the decision time. Timestamp alignment alone is not enough for macro, calendar, on-chain, funding, COT, and revised economic data. Every feature family consumed by Stage 3.1 must declare its event time, availability time, revision policy, and staleness behavior.

This document is a blocking contract for Stage B promotion and Stage C held-out claims. Existing Stage A smoke jobs may continue, but no configuration may advance unless its feature families satisfy this contract or are explicitly labeled as research-only / non-live-equivalent.

## Required Metadata

Every cross-source feature family must provide or reference these fields:

| Field | Meaning | Required for |
| --- | --- | --- |
| `source_family` | Human-readable source or derived feature family id | All feature families |
| `native_frequency` | Native source cadence before resampling or forward-fill | All cross-source families |
| `event_time` | Economic period, market event time, funding interval, filing date, or bar timestamp represented by the value | All non-static features |
| `available_at_utc` | Earliest UTC timestamp when the strategy could have observed the value | All non-static features |
| `source_timestamp` | Provider ingestion or publication timestamp where available | Cross-source and provider-derived features |
| `vintage_or_revision_id` | Vintage date, revision date, snapshot id, or `not_revised` | Macro/economic/provider-revised data |
| `release_lag_policy` | Explicit lag rule when true publication time is unavailable | Macro, calendar, COT, regulatory, fundamentals |
| `forward_fill_policy` | Maximum fill horizon and whether fills are allowed after source staleness | Forward-filled features |
| `staleness_age_bars` | Number of simulation bars since the latest available source update | Forward-filled or low-frequency features |
| `source_is_stale` | Boolean or categorical stale flag used by experiments | Forward-filled or low-frequency features |
| `known_limitations` | Any non-live-equivalent or final-revised caveat | All feature families |

## Vintage Policy Labels

Use exactly one of these labels per feature family:

| Label | Meaning | Promotion rule |
| --- | --- | --- |
| `real_time_vintage` | Values are retrieved or reconstructed from the vintage visible at decision time | Eligible for Stage B/C |
| `release_lagged_actual` | Values are final/revised but lagged by a conservative release policy | Eligible if documented |
| `final_revised_research_only` | Values are final revised and not live-equivalent | Stage A research only, blocked from live-tradability claims |
| `provider_snapshot` | Values reflect a provider snapshot with an ingestion timestamp | Eligible if snapshot time is before decision time |
| `synthetic_proxy` | Derived proxy for unavailable consensus/surprise/availability semantics | Eligible only as a proxy family, not as a true surprise/vintage family |
| `not_revised` | Market data, OHLCV, or derived causal features not subject to provider revision | Eligible if causal windows are documented |

## Source-Family Requirements

| Source family | Event time | Availability rule | Revision policy | Staleness policy |
| --- | --- | --- | --- | --- |
| Trading OHLCV | Bar close time | Bar close plus exchange/API latency assumption | `not_revised` unless exchange corrections are documented | No forward-fill across missing trading bars without a missingness flag |
| Technical/statistical features | Last source bar used | Same as source OHLCV last bar | `not_revised` | Rolling-window warmup rows dropped or flagged |
| Signal decomposition | Last source bar used | Same as source OHLCV last bar | `not_revised` | Must be causal; centered transforms are blocked |
| Learned embeddings | Last source bar used | Same as training input availability | Fitted-transform metadata required | Fit window must exclude held-out data |
| FRED/BLS/BEA/OECD/Treasury macro | Economic period or release date | Official release time if known; otherwise conservative release lag | Prefer `real_time_vintage`; otherwise label final revised | Add `bars_since_release` and stale flags |
| Economic calendar / surprise proxy | Release timestamp | Release timestamp plus ingestion lag | Proxy or consensus label required | Add release-window and bars-since-release features |
| CFTC/FINRA/SEC/regulatory | Report period and publication timestamp | Publication timestamp, not report-period end | Provider/revision id if available | Forward-fill age required |
| Binance funding | Funding interval timestamp | Funding publication/settlement time | `not_revised` or provider snapshot | Add `bars_since_last_funding` and `bars_until_next_funding` |
| On-chain/DeFi metrics | Chain block time or provider metric timestamp | Provider availability timestamp or conservative lag | Provider snapshot | Forward-fill age required |
| Paid providers | Provider timestamp and source event time | Provider documented availability | Provider snapshot or vintage | Must map to subscription-value family |

## Blocking Rules

- Missing `available_at_utc` or release-lag policy blocks Stage B promotion for any cross-source family.
- Final-revised macro data may be used for exploratory Stage A only when labeled `final_revised_research_only`.
- No Stage C candidate may consume a fitted transform or source value that used 2025 held-out observations, revisions, or calibration.
- Forward-filled low-frequency values must include age/staleness features or be excluded from promotion evidence.
- The Stage A summary must distinguish live-equivalent, conservative-lag, proxy, and research-only evidence.
