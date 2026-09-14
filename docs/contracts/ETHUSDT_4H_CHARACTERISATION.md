# Temporal characterisation: `market_data/crypto/spot_top50/ethusdt/4h.parquet`

Date: 2026-09-14. Author: Satoshi. Review: Musashi.
Status: **characterisation, no installable availability contract**.
Supersedes [`ETHUSDT_4H_CONTRACT_CANDIDATE.md`](ETHUSDT_4H_CONTRACT_CANDIDATE.md), whose
zero-lag availability claim is withdrawn.
Order: N1–N2 of `predictor/docs/handoffs/MUSASHI_TO_SATOSHI_TEMPORAL_SEMANTICS_AND_REAL_HOST_ADOPTION_2026_09_14.md`.

## 1. The five clocks, separated

| clock | status | evidence |
|---|---|---|
| window start | **MEASURED** | `open_time` of every row, tz-aware **UTC** in the physical schema |
| window end | **MEASURED** | `close_time`; modal span = 4 h − 1 ms |
| finalization | **NOT DEMONSTRATED** | the file carries no field saying whether a row is final; 21 rows have a non-nominal span |
| publication | **UNOBSERVED** | no artefact records when the provider published any row |
| reception / ingestion | **UNOBSERVED** | one file-level acquisition timestamp bounds the whole file, not a row |
| revision | **UNKNOWN** | a single acquisition cannot show whether past rows are restated |

The correction that matters: **a window's close is not availability**. A bar closing at
23:59:59.999 can be published the next morning; a UTC stamp shows how the clock is written,
not when the data arrived. The previous candidate copied `close_time` into
`available_time_column` with zero lag while the same submission declared latency UNOBSERVED.
That is withdrawn. `UNOBSERVED` is not `0s`.

## 2. The 21 non-nominal bars, classified from the bytes

| class | count | what the bytes show |
|---|---|---|
| `EMPTY_PLACEHOLDER` | 1 | span 0 ms, volume 0, 0 trades (2017-09-06 16:00Z) |
| `SHORTER_NOMINAL_INTERVAL` | 12 | span exactly 2 h − 1 ms (10), 3 h − 1 ms (2): a clean sub-interval end, not a 4 h window |
| `PARTIAL_AGGREGATE` | 8 | arbitrary spans (28 min, 59 s, 3 h 00 m 14 s …), all with volume and trades |

Eight of the 21 sit immediately before one of the file's 8 gaps — consistent with a
collection boundary. **None of them is demonstrated to be a final bar**, so none may be used
where finality is required; they are excluded from that set with their origin and reason,
and the 8 gaps are left as gaps (nothing is interpolated).

## 3. What the resource is eligible to promise

```
kind:                               ARCHIVE_RETROSPECTIVE
installable availability contract:  NO
point-in-time claim:                REFUSED   (publication time unobserved)
live claim:                         REFUSED
refusals:                           PUBLICATION_TIME_UNOBSERVED, FINALITY_NOT_DEMONSTRATED
```

What would change it: a producer statement or an observation of publication time per row (or
a defensible bound on it), and a field or statement distinguishing final rows from partial
aggregates.

## 4. The minimal schema extension this needs

The existing vocabulary cannot say *"the event geometry is known and publication is not"*:
every use class requires a numeric `completion_lag_max`, which forces an invented number.
The extension is one value and one rule, additive, in the lake:

```json
{"availability": {"label": "WINDOW_END", "completion_lag_max": "UNKNOWN",
                  "timezone_evidence": "PRODUCER_STATEMENT",
                  "use_class": "ARCHIVE_RETROSPECTIVE"}}
```

* only this class may declare `completion_lag_max: "UNKNOWN"`, and it **must**;
* a resource declared this way is delivered **whole** (`AS_IS`) or not at all — a ranged
  delivery is refused with its reason, because a range would be a point-in-time claim;
* under a configured holdout, even the whole delivery is refused: an archive cannot be shown
  to predate the holdout.

Nothing changes for `OFFLINE_DAY_GRANULAR` or `LIVE_EQUIVALENT`, and no installed contract
declares the new class. The archive contract for this resource would be
`a85c3c0767f84ce3174d1143e1a33aa3af17211ee87e688683ef06048152cfb0` — **not installed**.

## 5. Tests

`store/tests/test_ethusdt_4h_characterisation.py`, 19 tests, and the auditor's four
counterexamples frozen in `store/tests/frozen/`:

* an archive is delivered whole; a ranged delivery is refused with its reason; a numeric lag
  is refused for the class;
* **this** resource cannot claim point-in-time or live, asserted as refusals with their
  measurements (the previous test called the validator without expecting a refusal);
* the positive path: an *observed* publication column is what supports availability, and a
  publication column earlier than the window it describes is refused;
* reception on the following day is not availability on the first — the auditor's case;
* a bar that is not final is reported as such rather than delivered silently;
* a late revision changes the delivery identity;
* every invalidating measurement (unreadable file, non-monotonic clock, duplicates, end
  before start, digest ≠ producer's) refuses instead of emitting a contract;
* exact UTC, and the typed refusal of an intrabar range (the previous versions accepted
  `None` and any `Exception`);
* the real resource is characterised as a retrospective archive, with its 21 bars classified.

## 6. Still open, with its owner

| question | owner | next |
|---|---|---|
| publication / delivery latency | the producer chain | a per-row publication field, an acquisition log, or a stated bound |
| finality of the 21 bars | the producer chain | a field or statement; until then they stay excluded from any finality-requiring use |
| revision policy | the producer chain | a second acquisition compares two snapshots; it does not establish a policy |
| usage rights | the data owner | primary terms from the provider; not inferable from an SDK licence or another dataset |
