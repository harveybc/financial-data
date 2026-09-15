# Candidate availability contract: `market_data/crypto/spot_top50/ethusdt/4h.parquet`

> **SUPERSEDED on 2026-09-14** by
> [`ETHUSDT_4H_CHARACTERISATION.md`](ETHUSDT_4H_CHARACTERISATION.md) after Musashi's review.
> Its central claim — `available_time_column: close_time` with `completion_lag_max: "0s"` —
> **is withdrawn**: a window's close is when the window ended, not when the data could be
> known, and the same submission declared delivery latency UNOBSERVED. The measurements below
> stand; the contract they were used to justify does not. The file is kept, not edited away.

Date: 2026-09-14. Author: Satoshi. Review: Musashi. Status: **withdrawn, superseded**.
Order: A2 of `predictor/docs/handoffs/MUSASHI_TO_SATOSHI_CONTRACTS_AND_CONSUMER_ADOPTION_2026_09_14.md`.

This is the first financial resource followed to its producer. It is not installed: making a
resource deliverable under governance changes what a scientific run may consume, and that
belongs to review. Everything below is measured from the bytes, with the tool and the tests
committed next to it.

## 1. Why this resource

It is the raw input of the lineage the census and characterisation work already traced:
`features/census/ETH_H4_SUCCESSOR_TEMPORAL_CONTRACT.v3.json` binds the successor dataset to
this file by exact value match, and the earlier `ETH_H4_TEMPORAL_CONTRACT.v2` did the same
for the historical one. Reusing that work is the point: no new census was started.

## 2. Producer

| | |
|---|---|
| source | Binance Spot (declared in `market_data/crypto/spot_top50/ethusdt/provenance.json`) |
| acquisition | one acquisition, `2026-05-01T15:58:56Z`, by the repository's acquisition script |
| pinned digest | `7a6b79833355d7c22a3db30e6494ced078d628338d76e671af320a06b35fc9e5` |
| digest of the bytes read here | identical — the file is what its producer declared |
| variables | `open_time, open, high, low, close, volume, close_time, quote_volume, trade_count, taker_buy_base_volume, taker_buy_quote_volume` |
| units | prices in USDT, volumes in the base and quote assets, `trade_count` a count |
| frequency | 4 h, nominal 14,400 s |

## 3. What the bytes show (18,337 rows)

| property | measurement |
|---|---|
| time zone | `open_time` and `close_time` are `datetime64[ms, **UTC**]` in the physical schema — a producer statement in the file, not a column name |
| timestamp meaning | `open_time` is the **bar open**; `close_time` is the bar's last millisecond |
| close convention | modal `close_time − open_time` = 14,399,999 ms = 4 h − 1 ms (`INCLUSIVE_LAST_MILLISECOND`) |
| ordering | strictly increasing, 0 duplicates |
| grid | 18,337 of 18,337 rows on the nominal 4 h grid, 0 off-grid |
| gaps | 8 (absent intervals stay absent; nothing is interpolated) |
| truncated bars | 21 bars close earlier than the nominal close; 1 of them closes at its own open |
| span | `2017-08-17T04:00:00Z` → `2025-12-31T20:00:00Z` (open times) |

## 4. The candidate contract

```json
{"event_time_column": "open_time", "available_time_column": "close_time",
 "timezone": "UTC", "time_unit": null, "frequency": "4h",
 "availability": {"label": "WINDOW_END", "completion_lag_max": "0s",
                  "timezone_evidence": "PRODUCER_STATEMENT",
                  "use_class": "OFFLINE_DAY_GRANULAR"}}
```

`contract_sha256` = `998e3f80d0a5d2ab15d9a04235a6ec2c418ff8f784a630a45c755405eff0792d`
(the value the lake would publish in `X-Availability-Contract-SHA256`).

Why `completion_lag_max` is `0s` and why that is not a live claim: the availability column
**is** the bar's own completion time, so no further lag is claimed against it. What happens
after that — when the provider published the bar, and when we could have fetched it — is
unobserved, and that is exactly why the use class is `OFFLINE_DAY_GRANULAR`. Historical
offline use is what this contract supports; live equivalence it does not.

## 5. What is still unknown, and why

| property | status | why |
|---|---|---|
| provider delivery latency | `UNOBSERVED` | no artefact records when the provider published any bar. The acquisition timestamp bounds the whole file, not a bar. **Unobserved is not zero** |
| revision policy | `UNKNOWN` | one acquisition with a pinned digest; whether past bars are ever restated cannot be seen from a single snapshot. A second acquisition would settle it |
| usage rights | `UNKNOWN` | the provenance names the source; no licence or terms of use are recorded in this repository. A scientific publication needs this answered |

None of the three is filled with a convenient estimate. The first is the reason live use is
refused; the second and third are open questions for the producer, not for the lake.

## 6. Tests, before installing anything

`store/tests/test_ethusdt_4h_contract.py` — 11 tests over bytes, against the provider that
serves the deployed lake:

* the contract validates, and the live class stays refusable;
* **extremes**: a bar completing exactly at the range end is excluded (`available + lag < end`);
* a bar is delivered on the day its window closes, not the day it opened;
* **truncated bar**: a bar that closed early is available then, and both such bars land in
  the day of their real close;
* **time zone**: the cut follows the schema's UTC, not the reader's locale;
* an intrabar range is refused;
* **partitions**: train / calibration / confirmation are disjoint and their union is the
  whole range;
* **future tail**: appending later bars leaves an earlier delivery byte-identical;
* **revisions**: changing a past bar changes the delivery identity — revisions are not
  claimed to be absent, they are made detectable;
* the real resource still matches every measured fact and its producer's pinned digest.

## 7. What installing it would take

1. review of this candidate (it changes what a governed campaign may consume);
2. adding the entry to the financial lake host's **pending** configuration and activating it
   in a deliberate window — the pending file is not an authorisation;
3. a governed micro-run that consumes the resource end to end, with the contract identity in
   the delivery headers and in the terminal.

Nothing above was done here.
