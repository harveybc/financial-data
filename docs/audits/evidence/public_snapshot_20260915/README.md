# One public comparison of the ETHUSDT 4h archive, 2026-09-15

R5 of the standing order. Executed on **dragon** (a host that does not run the lake), against
a read-only copy of the archive whose sha256 matches the characterisation's, so nothing in the
lake was opened for writing.

Bounds honoured, as declared before any request: **3 requests**, 1000 bars each, 529,443 bytes
in total (limit 5 MiB), 30 s timeout, no retry after a denial, no account key, no order.

| window | why it was chosen | bars | matched | differing | materially differing |
|---|---|---|---|---|---|
| anomalous | the first bar whose window span is not nominal | 1000 | 1000 | 0 | 0 |
| ordinary | the middle of the archive | 1000 | 1000 | 59 | **0** |
| end_bound | the last bars, at the producer's fixed END_MS | 1000 | 1000 | 86 | **0** |

## What was found

**No revision.** Across 3,000 bars matched by `open_time`, not one differs materially.

**A property of our own artefact, which is the real finding.** 145 bars differ in the last
digits of `quote_volume` and `taker_buy_quote_volume`, by a relative 2e-16 — one unit in the
last place of a float64. The producer sends decimal strings; the archive stores them as
float64 and cannot hold the final digits. So those two columns do not round-trip, and any
future byte-level comparison against the endpoint will always "differ" there unless the
comparison is done in decimal.

## What this does not settle

Agreement at one moment is not a policy. It does not establish finality, it does not
establish that revisions never happen, and it says nothing about the 21 anomalous bars'
construction — those matched exactly today, which is one observation, not an explanation.

Evidence: `DECLARED_WINDOWS.json` (written before the first request, with its own digest),
`FETCH_RECEIPT.json` (request and receipt times, status and sha256 per response),
`COMPARISON.json` (field-level differences, each classified representation or material).
