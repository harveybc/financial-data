# Observed clock and price consolidation

Owner authorization continues without another approval. Complete the raw-source
time correction, assemble observed replacements, recheck coverage and publish
the accepted inventory before rebuilding selection and running static RL.

## Clock decision

For the six retained EURUSD/GBPUSD annual HistData ASCII archives, 2023-2025,
the observed time convention is `(native + 5 hours)` interpreted in
`Europe/London`, converted to UTC. This is a cohort-specific empirical correction
of the conflicting fixed-EST metadata. Bind the exact six compressed hashes;
it is not a blanket reinterpretation of other downloads.

Before producing corrected bars, replay independent Forexite original ZIPs
for 2023-01-03, 2023-06-30 and 2023-07-10, using its documented CET/CEST clock
and completed-minute endpoints. Compare HistData minute-close endpoints under
the chosen rule with -60, -1, +1 and +60 minute negative controls on common
timestamps. Correlate differences only across consecutive observed minutes;
never count a jump across a missing interval as a one-minute return.

Engineering acceptance: at least 120 consecutive pairs in each pair/date
witness, aligned return correlation >= 0.75 and at least 0.25 above every
negative control, and p95 absolute quote difference <= 0.0006. The price
difference admits independent OTC quote levels; no fitted price adjustment
is applied. These bounds are calibration checks, not predictor or trading
performance. Recheck the chosen rule against the independent FXCM H1 sources.

## Output

Replay the existing raw parser and clock conversion. Aggregate OHLC only for
hours containing all 60 distinct minute bars. Preserve observed prices and
retain raw minute identity/count, UTC bar start, bar-end availability and the
source per hour. An incomplete hour remains explicitly incomplete. No price
fill, interpolation or calendar closure can be inferred from its absence.

Write a new immutable candidate tree with atomic manifests and resumable
verification, never overwrite native sources. `clock_verified` means the
cohort correction passed independent witnesses. Whole-lake admission remains
conditional on coverage, business calendar, replacements and feature lineage.

## Tests Before Implementation

1. Correct UTC output on winter/summer and both sides of DST transitions;
   ambiguous native times rejected.
2. Common-support negative controls reject an intentional one-minute shift;
   changes across missing minutes excluded from correlation.
3. Missing minute prevents an hourly bar; OHLC and availability exact.
4. Modified source archive/contract/output rejected; restart reuses exact files.
5. Corrected raw prices unchanged, no future dependence in prefix output.

After this acceptance, consolidate native H1, authenticated boundary quotes and
corrected complete replacement hours with per-bar source identity. Recompute
monthly coverage and every source transition. Publish the actual unresolved
timestamps and recover them, then rebuild admitted preprocessing/selection.
