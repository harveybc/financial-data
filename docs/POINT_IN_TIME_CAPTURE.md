# Point-in-time capture: what we knew, and when we knew it

Started 2026-09-25. `m5phet.point_in_time.v1`.

Every macro archive on this machine records what a number turned out to be. None of them records **when it reached
us**, and no archive can be made to record it afterwards — a receipt clock exists only if something was running when
the number arrived. This package is that something. It costs a timer. It buys one fact per release that cannot be
bought later at any price, and it is worth reading what that fact is and is not before anyone plans on it.

## What it is

| Piece | Path |
|---|---|
| The store | [`_scripts/lib/point_in_time_store.py`](../_scripts/lib/point_in_time_store.py) |
| The collector | [`_scripts/workers/stage13_point_in_time_capture_worker.py`](../_scripts/workers/stage13_point_in_time_capture_worker.py) |
| The schedule | [`_scripts/systemd/financial-data-point-in-time-capture.{service,timer}`](../_scripts/systemd/), installed by `install_point_in_time_capture.sh` |
| The tests | [`_scripts/tests/test_point_in_time_capture.py`](../_scripts/tests/test_point_in_time_capture.py) |
| The rows | **outside this repository**: `$XDG_STATE_HOME/financial-data/point_in_time` (default `~/.local/state/…`), one JSON file per row, sharded by key |

The collector reads two local parquet files and nothing else:
`economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet` (896 scheduled releases, 2026-02 → 2027-07)
and `economic_calendar/release_actuals/fxmacrodata/announcements.parquet`. **No new external source, no credential,
no network call, no GPU.** The value of this package is not new data; it is the timestamp on data we already had.

## The three clocks, and the one this adds

* `scheduled_at` — when the calendar said the release would happen. A schedule, not an event.
* `source_publication_at` — when the **source** says the number was announced. The source's claim; we did not witness
  it. Null wherever the source declares none, and nothing substitutes one.
* `received_at` — when **this system** first held the value. Our own clock, stamped inside the collector process.
  There is no flag that sets it, and a test asserts there is none: a collector whose receipt clock can be supplied is
  a machine for inventing availability.

Every row carries this reading, in the row, in `publication_bound`:

> **A receipt clock is not a publication clock.** It bounds the publication instant **from above and never from
> below**: the number existed no later than the moment we read it, and may have existed for hours before. Substituting
> one for the other would place a release inside or outside an event window by guesswork, and the guess would be
> invisible in the number that comes out.

This is the same boundary `feature-eng`'s `app/economic_calendar.py` already enforces between `release_surprise` (the
source's clock) and `available_surprise` (ours), and the same one its `MISSING_PUBLICATION_CLOCK` refusal names. This
store produces the **available** side only.

## The store's rules

Taken from the discipline `news-signal`'s `shadow.py` and `collector.py` already enforce in this fleet, restated
because a cross-repository import is not available:

* **Opaque keys by record identity.** A key is a digest this store computes from what the row *is* — the release
  (calendar source, economy, series, scheduled instant) and the observation (source, status, value, period, unit).
  A provider's identifier is kept inside the row, never in a filename.
* **Append-only; exclusive create.** The only write is `os.link` onto a new key. There is no code path that replaces
  a live row. A value that changes is a **new row with a higher `revision_index`**; the earlier row keeps its bytes,
  its digest and its receipt clock. An attempt to put different facts under an existing key is refused by name:
  `ROW_REWRITE_REFUSED`.
* **Reading the same value again is not a revision.** Our clock is deliberately outside the key, so a pass over an
  unchanged archive returns `DUPLICATE` and writes nothing. The store is a history of the number, not of the cadence.
* **Three integrity questions, not one.** Does the row hash to its own digest; do its own fields derive the key it
  carries; is that the key it was found under. The last is the one a true row for *another* release, copied onto this
  key, answers wrongly and silently.
* **Quarantine by bytes, never re-signing.** A row that fails validation is moved to `quarantine/<key>.<bytes>.json`
  and stays out of every count. Re-signing it would recompute its digest over corrupted content and make the
  corruption credible; deleting it would erase what went wrong.
* **Nothing is invented.** A release whose scheduled instant has passed with no value in any source we read is
  recorded `AWAITED` — a row that says *we looked at this instant and there was nothing*. A source carrying two
  different numbers for one release is `AMBIGUOUS_SOURCE` with neither chosen. Neither ever carries a value.

Reading it back: `PointInTimeStore.known_at(T)` returns, per release, the last valid row received no later than `T`.
A row received after `T` is **absent**, not ranked lower.

## The schedule

`systemd --user`, `OnCalendar=*-*-* 00,03,06,09,12,15,18,21:07:00 UTC`, `Persistent=true`, `MemoryMax=1G`,
`CPUQuota=50%`, `CUDA_VISIBLE_DEVICES=` blanked.

**Why three hours.** The receipt clock's resolution is the interval between passes, so the interval is the width of
the upper bound this store puts on a publication instant. Three hours costs nothing and bounds every release to the
pass that first saw it. Going finer would not buy a tighter bound today, because the archives it reads are refreshed
by acquisition workers that run far less often than that — the binding constraint is the **source's** refresh cadence,
not ours. `Persistent=true` because a missed pass is a hole nobody can fill afterwards.

```sh
sh _scripts/systemd/install_point_in_time_capture.sh [PYTHON] [STORE_ROOT]
systemctl --user list-timers financial-data-point-in-time-capture.timer
systemctl --user start financial-data-point-in-time-capture.service   # one pass, now
tail -1 ~/.local/state/financial-data/logs/point_in_time_capture.log  # one JSON summary per pass
```

Verification without the timer: `python3 _scripts/workers/stage13_point_in_time_capture_worker.py --once --store <dir>`.
All machine-specific paths live in `~/.config/financial-data/point-in-time-capture.env`, written by the installer,
outside the repository and untracked.

## The first pass (2026-09-25)

| | |
|---|---|
| scheduled releases read | 896 (2026-02-05 → 2027-07-14) |
| past at the moment of the pass | 727 — all recorded |
| still in the future | 169 — not recorded; a release that has not happened is not an observation |
| rows written | 727, one per release, 0 revisions, 0 quarantined, 0 integrity failures |
| `OBSERVED` (a value) | **45** (43 matched on the exact scheduled instant, 2 on the same UTC date — the rule is recorded per row) |
| `AWAITED` (we looked, nothing there) | **682** |
| series covered | 154 (economy × release) across 14 economies |
| receipt clocks | 2026-09-25T17:58:57Z → 2026-09-25T17:58:58Z (one pass) |

Second pass over the same archive: 727 `DUPLICATE`, nothing written, every file byte-identical.

## What a year of this will support

1. **Availability-correct backtesting.** A feature built at decision time `T` may use exactly the rows with
   `received_at <= T`. That is the question `known_at(T)` answers, and after a year it answers it with real receipts
   instead of an assumption. Today every study on this machine assumes a release was knowable when it was scheduled
   (`ASSUMED_SCHEDULED_PUBLICATION` in `feature-eng`'s event ladder); those rows will not need the assumption.
2. **Revision analysis with a real first print.** The first row for a release is what we first saw; each later row is
   a revision with the receipt clock of the revision. First-print-versus-revised studies, and "how long did the
   original stand", become measurable rather than reconstructed.
3. **Publication-lag bounds.** `received_at − scheduled_at` is an upper bound on the release's delay, per series.
   With a year of passes it gives a per-series distribution of *how late we can be*, which is the honest input to any
   availability rule.
4. **Evidence that the record was kept.** `AWAITED` rows prove the collector looked. A gap in the record is then
   visibly a gap, not an ambiguity between "nothing happened" and "nothing was running".

## What it will NOT support — no matter how long it runs

1. **It does not produce a publication clock.** Only an upper bound, at the resolution of the pass that saw the value.
   Any study needing the instant the market learned the number still needs a source that observes it.
2. **It does not produce a consensus, so it does not produce a surprise.** This is the sentence that matters. The
   event study is `NOT_IDENTIFIED` (see `feature-eng`'s `docs/EVENT_STUDY_DATA_STATUS.md`) because no source here
   carries *consensus + actual + publication instant* together. This package adds the third's upper bound. It adds
   **nothing** to the first. A year of it will not make a calendar-surprise event study identified.
3. **It does not reach backwards.** It begins on 2026-09-25. Nothing gives 2011–2025 a receipt clock.
4. **It is only as live as the source underneath it.** The collector records a value when it first appears *in a
   source we already read*. Today `announcements.parquet` was last acquired on 2026-05-01, which is why 682 of 727
   past releases are `AWAITED`: the world published those numbers and this machine has not fetched them. Until an
   acquisition worker refreshes that archive on a schedule, most receipt clocks record **when we fetched**, not
   **when it was published** — and the gap between them is the fetch schedule, not the release lag. This is a real
   limit, not a caveat: the capture is honest either way, but it is only *informative* to the extent the archive
   beneath it is kept current.
5. **It is not a unit or a vintage system.** The source carries numbers without units; rows record `unit: null` with
   `unit_reason: SOURCE_DECLARES_NO_UNIT` rather than guessing one. Comparing two series' values is the consumer's
   problem, and `feature-eng` refuses `INCOMPARABLE_SERIES` for a reason.
6. **A year away.** The first rows are worth reading as evidence the record exists. They are not worth a study.

## What would still have to be bought or captured

* **A consensus feed with point-in-time coverage** — Trading Economics' calendar or FXStreet's Economic Calendar API,
  both paid or credentialed (`economic_calendar/release_surprises/stage13_consensus_gap.md` records the refusals:
  HTTP 410 without a subscription, and OAuth). This is the only thing that turns a release into a *surprise*, and it
  is a purchasing decision, not a bug. A consensus captured prospectively by this same mechanism would carry our
  receipt clock, which is enough to compute `available_surprise` — never `release_surprise`.
* **A historical calendar with consensus *and* publication timestamps for 2011–2021**, which would make the existing
  bar history usable at once. No capture started today can substitute for it.
* **A scheduled refresh of the actuals archives** (point 4 above). That is an existing acquisition worker against a
  credentialed API; running it is the owner's decision, not this package's.
* **An observed publication instant from the venue** — a wire, or the statistical agency's own release feed — if any
  study ever needs the lower bound this store cannot provide.

Until the first of those exists, the event study stays `NOT_IDENTIFIED`, and WP28's `MODEL_BASED_EXPECTATION` — an
expectation fitted from a series' own vintage history and called by that name everywhere — remains the only honest
substitute. This store is what makes such a vintage history exist prospectively.
