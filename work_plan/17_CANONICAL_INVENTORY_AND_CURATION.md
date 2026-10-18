# Canonical Inventory, Repair, Curation And Selection

Owner directive: 2026-10-18. This supersedes acquisition policies that admitted
every plausible source before checking quality. A file's existence, a wide date
range, a successful download and a high finite-value fraction are insufficient.
This is the required procedure. Deployment and whole-inventory acceptance are
not yet complete; do not describe this document as proof that the lake is clean.

## 1. Scope And Responsibilities

Inventory every variable in the configured research population, including all
raw dependencies of derived features, targets, prices and market calendars.
The initial financial split is TRAIN2020-2023, VALIDATION2024, TEST2025.
Rolling training windows are additional declared views, not substitute years.

`financial-data` owns source acquisition, quality, repair and canonical files.
`financial-data-store` publishes those files through the existing `data-lake`
host. `data-gov` handles deliveries. Preprocessing and feature generation stay
in their existing repositories. The selector uses the existing phase-1/2/3
engines and predictive validation, and the warehouse stores their new metrics.
Do not build a competing data-lake, selector or distributed optimizer.

## 2. Inventory Record, One Row Per Variable

Each record must contain the following, not just a dataset filename:

| Group | Fields |
|---|---|
| Identity | dataset_id, variable_id, instrument/entity, raw/derived role, path, column, byte size, content hash, schema/version |
| Meaning | numeric/categorical type, unit, currency, bid/ask/mid, price adjustment/roll rule, transformation and raw dependencies |
| Time | native cadence, timezone, bar start/end/event time, availability time, calendar/session rule, release lag, revision/vintage and staleness rule |
| Required support | purpose, asset/target/horizons, required start/end, TRAIN/VALIDATION/TEST and rolling windows, minimum warmup/context |
| Actual support | first/last observation, rows per month/year, distinct timestamps, missing expected observations, nonfinite cells, longest missing runs |
| Validity | duplicate/conflicting rows, monotonicity, numeric parse failures, nonpositive prices, OHLC consistency, incompatible units |
| Distribution | min/max and quantiles, median/MAD/IQR, constant/near-constant runs, potential outlier counts/severity, shift relative to TRAIN |
| Repair | provider queries actually attempted, response coverage, recovered timestamps, overlap comparisons and verified replacements |
| Disposition | REQUIRED_REPAIR, ADMITTED, UNUSED or UNRECOVERABLE; exact failed checks; no automatic scientific eligibility from a label |

Identify required variables from the configured population and dependencies,
not from which files happen to exist. Otherwise missing files vanish from the
denominator. Inventory source columns before creating aligned feature tables.
Preserve full dates and counts; annual averages cannot hide lost months.

## 3. Recovery Before Discarding

For every required incomplete series:

1. Compute exact missing timestamps on that source's actual calendar. Separate
   absent rows, present nonfinite values, legitimate closures and warmup.
2. Request the missing interval, with overlap on both sides, from the existing
   paid and free adapters. Use the available subscription without buying a new
   plan or account. Paginate and verify the returned interval; HTTP200 is not
   proof of useful coverage.
3. Inspect native resolution. A daily fixing is not an hourly candle. Do not
   upsample Yahoo daily data or macro reference rates into missing hourly data.
   A provider's historical retention limit is an observed capability, not a
   reason to abandon other providers.
4. Compare independent observations at matching instrument, quote side, units,
   timezone and bar boundaries. Report overlap n, median/p95/max difference,
   rounded-precision agreement and discontinuities. Do not require identical
   prices from different OTC venues, or silently treat bid and mid as equal.
5. If source labels are doubtful, corroborate actual values and clocks against
   an independent feed. Investigate offsets around DST and session boundaries.
   Do not stop solely because a provider name is undocumented; do not conceal
   a demonstrated one-hour timing discrepancy either.
6. Use actual observed replacements. Prefer a coherent complete replacement
   series when venue differences would create artificial returns at a splice.
   If combining observed sources is necessary, record the provider per bar,
   compare overlaps and test every boundary. No fitted offsets to make prices
   agree, no interpolated/forward/back-filled prices and no synthetic weekends.
7. Recompute all dependent features after repair. Replacing only the price
   while retaining old volatility/returns or old selection scores is invalid.
8. Re-run the same quality checks. If recovery is genuinely impossible after
   applicable sources were attempted, remove the series from the configured
   usable population and remove unused/bad bytes under the cleanup rules.

Download into temporary acquisition storage outside the admitted lake. Resume
completed verified downloads; obey provider rate limits and access controls.
Do not repeatedly download an unchanged deficient annual archive and call it
repair. Never log credentials or put paid raw data in a public repository.

## 4. Outliers And Invalid Observations

Distinguish impossible/corrupt quotes from valid market extremes. Verify
suspect timestamps against independent observed quotes before removal.

- Hard checks: parseability, finite values, strictly positive prices, coherent
  OHLC, duplicate conflicts and quote-side consistency.
- Diagnostic screens: modified z-score using TRAIN median/MAD and IQR fences,
  magnitude/severity, persistence and associated gaps. A modified absolute
  z-score above3.5 is a flag, not a deletion instruction. Zero MAD/IQR produces
  an undefined flag calculation, not a fictitious zero-outlier count.
- Real crashes, jumps and regime changes remain. Do not erase them merely to
  improve stationarity, SNR, prediction MAE or selection scores.
- Low-frequency macro steps/repeated as-of values use their own source update
  calendar; they are not hourly market-price flatlines.
- No target cleaning. No automatic clipping, winsorization or smoothing.
  Any later robust scaling comparison must be TRAIN-fitted and independently
  configured; it cannot alter TEST or retrospectively improve old metrics.

## 5. Admission To The Lake

Admission requires all applicable checks to have actual evidence:

1. Required temporal coverage exists at native cadence, month by month.
2. Source values and clocks pass the checks and cross-source comparisons.
3. Every required field is usable or has an explicitly supported typed mask;
   loss of a required month cannot be accepted as masked training data.
4. Per-source expected schedules are correct: FX sessions/DST/holidays,
   equity exchange sessions, macro publication schedules and24x7 crypto differ.
5. Derived features reproduce from accepted raw dependencies and use no value
   available after the decision time. Revision-sensitive data are handled by
   their actual availability, not just their economic-period date.
6. Immutable canonical files, an admitted-variable inventory and per-variable
   quality results agree by hash. A changed input invalidates dependent stages.

Publish canonical Parquet with explicit UTC event/availability columns, types
and units. For the file-store provider, configure its `root_path` to contain
only admitted resources. `include_globs` alone is NOT an access/admission gate:
the current provider's direct reads resolve files under root independently of
discovery filtering. Therefore unaccepted acquisition files must stay outside
that root, not hidden behind a discovery-only glob.

Render the existing provider JSON from the admitted inventory; use its existing
`resource_contracts` for time/availability semantics. Before switching the live
root, test discovery, metadata, actual downloaded bytes/hashes and a direct
request for an unadmitted resource (must not return its data). Atomic root
switch and readback follow real acceptance, not a documentation-only approval.

## 6. Preprocessing

Define business time and split boundaries before fitting any transformation.
Inputs can use observed prior-week history; closed-market hours do not count
as invented input ticks. Targets and evaluation use the configured strategy
mask: forced flat12h before market close, no new positions before12h after
opening, entry cutoff and target maturity before forced close.

Construct one UTC decision grid from the actual versioned market calendar.
Join by time and availability with bounded staleness, not positional indexes.
Keep a source-to-aligned-row accounting: source rows, absent slots, release
lag exclusions, warmup, business exclusions and target-specific masks.

Returns spanning an unexplained open-session gap are not one-hour returns.
Use actual elapsed offsets and closed-session flags where designed. Do not
compress arbitrary missing observations into adjacent fixed-cadence ticks.
Source-native daily macro/market observations may be carried forward only
after actual availability and within their declared source-specific staleness
policy; that does not authorize filling missing price candles.

Fit imputers (where applicable to non-price inputs), scalers and learned
transforms on the permitted TRAIN of each fold/update. Freeze their state for
subsequent inference. No global scaler, backward fill, centered rolling
filter, full-series decomposition or future-aware denoising. No denoised target.
Downsample inputs relative to current t, including t, without smoothing and
without changing the requested hourly forecast origins/horizons.

Validate again AFTER preprocessing and AFTER window creation. Count retained
origins per month and per horizon. Pairwise/common-support intersections must
not silently turn a declared four-year interval into a few partial years.

## 7. Recompute Feature Selection

Old metrics, correlations, rankings, selected manifests, learned extractors
and downstream models from affected inputs are deleted, not reused or copied
into the new cube. Recompute on the admitted population with a new identity.

1. Individual evidence: coverage and quality first, then distributions,
   robust outlier diagnostics, temporal structure, stationarity, spectral and
   nonlinear profiles. Record actual cadence/support and undefined results.
2. Cross-variable evidence: aliases, linear/nonlinear dependence, lagged
   relations and redundancy. Store support n for every pair and lag; do not
   compare metrics computed on unknown different populations.
3. Candidate subsets: reuse existing mRMR/JMI/clustering and control methods;
   study temporal stability and relevance/redundancy jointly. Causal evidence
   retains assumptions and NOT_IDENTIFIED; it is not proof of irrelevance.
4. Predictive validation: temporal folds and the configured weekly business
   protocol, with a per-horizon naive on exactly the same rows/scale. Mark
   VALIDATION tuning as development, never as independent performance.
5. Only after these stages: feature extraction/model architecture experiments,
   strategy simulation and DEMO/PAPER as specified in the master work plan.

Partition content is immutable. Quality inspection of already-used TEST does
not make it a pristine future holdout. Do not silently change the held-out
claim or rerank on TEST after repair.

## 8. Automation And Operations

The high-level sequence is inventory -> recovery -> native validation -> lake
admission -> preprocessing -> aligned/window validation -> individual metrics
-> cross metrics -> subsets -> predictive selection. A scheduler advances only
from actual terminal outputs, with no agent watching logs or approving normal
steps. Typed failures trigger bounded retries only when retryable; they never
turn bad data into successful admission.

One source/column job per admitted memory slot, bounded Arrow/CSV batches and
measured peaks. Keep SQLite queues/locks on ext4; bulk candidate/canonical data
on the configured large storage volume. Reserve host RAM and disk before work.
No GPU while this data/selection repair remains incomplete. No concurrent
heavy5090/5070Ti jobs on their shared-memory host.

Every level exposes a read-only status with denominators, completed/remaining,
current action, failures/retries, recovered/remaining holes and measured ETA or
an explicit unavailable estimate. The code, effective policies and tests go to
Git; raw datasets/analytical databases do not. Metrics are written idempotently
to the existing warehouse and accepted only after exact readback. A healthy
physical analytical copy is verified separately from the live writer.

## 9. Cleanup

Remove affected runtime results, weights, effective configs, forecasts, model
rankings, registries, logs, local outboxes, analytical rows, payload archives,
snapshots and remote copies. Disable their timers/followers first so they cannot
recreate or republish them. Do not create a replacement archive of invalid runs.
Remove stale result claims from active project documents and dashboards.

For raw/derived source files, finish applicable recovery attempts and admit
the replacement before deleting the defective predecessor. Repoint the lake
catalog and dependents, then remove superseded/bad/unused files on every host.
Never delete unrelated datasets simply because they share a backup file:
remove affected rows from mixed analytical stores and preserve independent
populations. Do not claim every historical Git object, third-party clone or
SSD remnant has disappeared merely because active files were removed.

## 10. Verification And Acceptance

### Native Hourly Recovery Subplan

Download native FXCM H1 quotes before attempting minute aggregation. Reuse the
existing parser in predictor, with its code identity pinned by the controller.
Both pairs cover the required 2020-2025 years, requesting weeks 1-53 so a final
partial week cannot disappear. A provider refusal or empty week remains an
explicit failure; completeness is checked against the independent required
date range, not the number of downloaded files.

The configured price view is BID. Retain source ask columns and flag any
crossing between side-bar endpoints, without claiming that their cause is
known or that bid/ask endpoints form a synchronous executable spread. Do not
silently flip sides, change prices or use them to calibrate trading costs.
Independent bid-price corroboration is still required before admission.

The unattended CPU controller advances through all years, retries a partial
download at most once, resumes verified year terminals and exposes read-only
status/ETA. Native bid/ask, source timestamps and bar-end availability remain
unchanged; no synthetic minutes, interpolation or automatic lake admission.
The service runs with a 2 GiB process-group cap; it reserves memory/disk before
each acquisition year and forces GPUs invisible.

| Requirement | Behavioral acceptance |
|---|---|
| NR01 | H1 gap stays a gap; actual quotes survive unchanged; no minute files |
| NR02 | Off-grid native H1 timestamps and altered materialized outputs fail |
| NR03 | All months are in the denominator even if entirely absent |
| NR04 | NY DST/session exclusions are distinct from missing open hours; calendar remains explicitly assumed |
| NR05 | Conflicting duplicate quotes or false availability fail; identical boundary duplicates are accounted |
| NR06 | Return-outlier reference is TRAIN-only; zero scale is NOT_ESTIMABLE |
| NR07 | Bounded retries, sequential successors, restart identity and read-only status are tested |
| NR08 | Acquisition success does not imply admission, selection or training permission |
| NR09 | Quality-only reports preserve undefined metrics, verify actual source digests and cannot relabel old experiments |
| NR10 | The existing governed outbox requires exact warehouse readback; closed analytical copies are hashed locally and on a second host |
| NR11 | Missing-hour dates trigger bounded alternative-source acquisition with adjacent overlap; native clocks stay unchanged |
| NR12 | Alternative-source dates are checked, provider cooldowns respected and completed batches not redownloaded |

These tests precede implementation. Real source readback, clock witnesses and
native coverage are required afterwards. This is not an authorization to
replace a missing quote with a fitted price or to treat assumed holidays as
verified market closures.

Tests must demonstrate detection of a missing month despite100% finite retained
rows, one missing open hour versus a weekend, conflicting duplicates, bad OHLC,
misaligned timezone/DST, publication after t, future perturbations, stale daily
values, wrong units/quote side, wrong split, wrong feature order and window
support collapse. Real repaired data must pass the same tests and readbacks.
Synthetic tests alone are insufficient to admit a financial dataset.

See the companion JSON policy for explicit defaults. The policy is a contract;
it is not proof that a consumer or deployment has already implemented every
field. The completion statement must list what is actually verified and what
remains, with no absolute claim that errors are impossible.

## Primary References

- https://tensorflow.github.io/tfx/guide/tfdv/
- https://scikit-learn.org/stable/common_pitfalls
- https://otexts.com/fpp3/tscv.html
- https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h.htm
- https://www.itl.nist.gov/div898/handbook/eda/section3/eda356.htm
- https://docs.feast.dev/getting-started/concepts/point-in-time-joins
- https://www.jmlr.org/beta/papers/v18/17-514.html
- https://www.jmlr.org/beta/papers/v11/cawley10a.html
- https://pmc.ncbi.nlm.nih.gov/articles/PMC6881151/
