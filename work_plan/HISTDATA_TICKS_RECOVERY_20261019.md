# Isolated HistData tick recovery

Scope: EURUSD July 2023 only, raw recovery and candidate evidence, independent
of consolidation. User explicitly authorized one normal public GET -> POST.
No admission, merge, interpolation, price fill, calendar/no-trade inference,
GPU, service changes, credentials, retries, polling, or access-control bypass.

## Method And Test Design

Discovery through unit-test-design gates completed before implementation.
Architecture: isolated Requests session, public HTML form parser, bounded raw
ZIP retention, chunked CSV validation, observed-only bid hourly accumulator,
three candidate clocks, read-only FXCM witness, common-support comparison.
Non-ZIP path retains only safe response headers, status, byte count and digest.
Raw tick rows remain in their original ZIP; hourly records carry row bounds.

| Requirement | Test/evidence |
|---|---|
| One normal GET/POST, no token leakage | form and non-ZIP single-POST tests; download.json |
| ZIP <=256 MiB, memory <=2 GiB | hard byte/address-space caps; report.json peak RSS |
| Chunk-safe source bid OHLC/count/gaps | cross-chunk, duplicate, bad/crossed-quote tests |
| Monotonic native times, strict milliseconds | backward and bad-timestamp tests |
| No invented hours/prices; availability at end | empty-hour and candidate-availability tests |
| Clock not assumed from M1 | three candidates; identical common-support tests |
| Unknown or insufficient clock stays unresolved | no-overlap/short-support tests |
| No admission or merge | candidate admitted=false; isolated output root |

Run outputs belong only in the user-authorized external bulk directory.
Publication availability is unknown; hour-end is candidate bar event-time
availability, not a claim of historical provider publication time. Missing
hours remain unknown. Cross-hour gaps are reported separately from within-hour
max intertick gap; first/last ticks expose unobserved edge coverage.

## Actual Alpha Evidence

One GET and one POST both returned 200. Raw ZIP: 9,129,673 bytes;
SHA-256: e2eceddfa96f3cce9cf3c05749fa7692dab829b318d56625fa59fae80e3593b7.
CSV: 59,875,257 bytes, 1,535,263 source/accepted ticks, zero rejected quotes.
Observed native hours: 370; three candidate files: 1,110 records total.
No fills, interpolated values or admissions. Peak RSS: 1,183,002,624 bytes;
hard address-space limit: 2 GiB. ZIP was retained untouched.

Clock comparison: 190 identical common-support hours. Bid OHLC MAE in pips:
fixedEST 5.928026; US Eastern 0.173816; native+5h localized London 0.173816.
The latter mappings coincide in July. Evidence favors their common UTC mapping
over the published fixedEST convention, but cannot identify the underlying
clock convention; selected_clock remains null and clock_state UNRESOLVED.
This is direct tick evidence, not a transferred M1 correction.

Under either tied mapping, ISO week 27 has 318,940 ticks and 85 observed hours.
These are candidate observations, not proof all M1 gaps were recovered.
Unobserved hours remain unknown, not asserted no-trade intervals.

External evidence root: the user-authorized `histdata-ticks-2023-07` bulk
directory. See download.json, report.json, clock_comparison.json,
clock_comparison_common_support.csv, observed_native_hours.parquet and the
three hourly candidate parquet files there.

Current stage: bounded alpha attempt completed; focused offline verification
completed. Beta, release and admission excluded. No commit. Review owner: user.
Next allowed action: review raw/candidate evidence; corroborate clock identity
outside July before any clock-specific admission claim. No automatic retry or
expansion to other months/pairs is authorized by this script.
