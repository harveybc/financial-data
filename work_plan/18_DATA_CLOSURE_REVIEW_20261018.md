# Data closure review

Reviewed lane D at `9c371fe88`, based on `dd14510cf`. Integrated as
diagnostic engineering, NOT data admission or recovered feature selection.
The original return is a point-in-time report; the qualifications below
supersede its affected counts and classifications.

## Corrections reproduced before implementation

| Finding | Correction | Evidence |
|---|---|---|
| A gap >=100 hours was called SOURCE_FILE_ABSENT without a failed download | Duration is never evidence of source failure | Long-gap regression |
| ISO week used Gregorian year; one label covered the entire gap | Split by ISO year/week and classification, preserve every missing hour | Year-boundary and support-conservation regressions |
| An ISO-week match was treated as proof of the missing archive | SOURCE_WEEK_FAILURE_CANDIDATE only; provider archive intervals still need mapping, especially Sundays | `source_absence_verified=false` |
| Inventory nonfinite count ignored positive/negative infinity | Count NumPy nonfinite values, including nullable missing values | Infinity/nullable regression |
| Distinct conflicting rows could be counted as identical duplicates | Count exact duplicate rows separately from conflicting timestamp groups | Four-row regression |

PRE: 5 failed, 11 passed in the closure test module. POST: 16 passed.
Broader focused recovery/publication suite: 60 passed, 1 skipped. Four pandas
timezone-to-period warnings remain; no source timestamp is modified by them.
No live recovery/controller/publication code or configuration changed.

## New bounded source check

Downloaded the real Forexite archives for 2023-10-27 and 2023-10-30 into a
separate diagnostic directory, without changing the lake or recovery inputs.
Each pair has 1,379 and 1,440 minute observations respectively. The per-date
witness contains four pair-date records; all clocks and quote sides remain
explicit hypotheses, not accepted transformations.

EURUSD bid-close comparison, absolute price difference:

| Date | Paired hours | Fixed UTC+1 p95 | Europe/Berlin p95 |
|---|---:|---:|---:|
| 2023-10-27 | 22 | 0.0020755 | 0.0002000 |
| 2023-10-30 | 24 | 0.0002470 | 0.0002470 |

Fixed UTC+2 gives p95 0.0018860 on October 30. GBPUSD shows the same
clock preference change. This supports a seasonal clock hypothesis; it does
not establish quote side, minute endpoint semantics, or permission to splice.
Witness SHA-256: `4da0ca2acad1a783e429549b24910b13c25e723468e118278ffc35e5d953ea8d`.
Raw archives and full witness stay outside Git under the configured bulk root,
in `forexite-dst-october-audit/`. Reproduce with the existing acquisition CLI
(`--dates 2023-10-27 2023-10-30`) and `clock_witness_by_date.py`.

Regenerated session diagnostic v2 preserves totals: EURUSD 1,103 missing
assumed-open hours = 960 source-week candidates + 130 calendar candidates +
13 other missing quotes; GBPUSD 1,108 = 960 + 135 + 13. These are investigation
buckets, NOT established closures or repaired hours. The previous 975/126/2
EURUSD causal breakdown is not authoritative. New local diagnostics have not
been published to the governed warehouse; the existing four delivered quality
reports and their two verified physical copies remain unchanged.

## Remaining work

### Provider clock resolved from primary documentation

The official Forexite page explicitly defines its GMT+1 label as CET in winter
and CEST in summer, including the MetaStock minute archive family:
https://www.forexite.com/free_forex_quotes/forex_history.html . The earlier
unknown-clock qualification above is superseded for this source convention.
The retained Windows-1251 HTML has SHA-256
`f5c2e0a29e0f6744ef575373e2f94bb687bf385621c5469f8c97703ce930b6f0`.
`configs/forexite_metastock_clock.v1.json` binds that primary evidence and the
independent October witness. Europe/Berlin implements those seasonal offsets.
This does NOT establish bid/ask/mid or minute-start versus minute-end labels.

`_scripts/normalize_forexite_clock.py` completed 86/86 candidate Parquet files,
206,858 rows, into a separate output tree. Prices/native labels are preserved,
`timestamp_utc_label` is added, no availability instant is invented, and no
interpolation or lake admission occurs. Ambiguous/nonexistent DST labels raise
an explicit error. These 86 files include diagnostic dates outside the recovery
request cohort; they are not the 84/110 requested-date coverage statistic.

Reproduction (bulk roots are operator configuration, never checked into Git):

```bash
python _scripts/normalize_forexite_clock.py \
  --candidate-root <native-candidates> --output-root <new-normalized-directory> \
  --contract configs/forexite_metastock_clock.v1.json \
  --source-evidence <retained-provider-html>
python _scripts/normalize_forexite_clock.py --status --output-root <normalized-directory>
```

`publish_forexite_clock.py` checks source/output bytes and counts, then uses the
existing governed outbox, warehouse readback and closed DuckDB copies. Its
`--root` must remain on ext4 (queue/lock), with `--local-copy` on bulk storage.
Its `--status --root <publication-root>` reports delivery separately from data
admission. All file/metric identities are new; previous reports are not relabeled.
New focused tests: 25 passed (clock normalization, source comparison and
publication validation); initial publisher test collection failed before its
implementation. Public source artifacts remain outside Git.

Publication executed at code pin `f7d051754`: 1 report, 6 metrics delivered and
read back, 0 pending, 0 mismatched. Physical snapshot 1,585,152 bytes, SHA-256
`739f3bfd5ef8a71378c99b2c2c23be3c56ea37c8d9412808547eb39263e2ef1a`, verified
on the coordinator, bulk partition and second machine. The bounded publisher
finished in 4.392 s with 104.3 MiB peak memory and no swap. Normalization and
publication receipts are separate: neither means prices are admitted.

Expanded recovery/quality suite after these changes: 75 passed, 1 skipped,
4 timezone-to-period warnings. The warnings do not change source timestamps.

### Next source-clock check

The separately acquired HistData annual 2023 candidates are present, not merely
unavailable downloads. Their fixed-EST interpretation must NOT be spliced into
the primary feed yet: an exploratory monthly overlap check against native FXCM
found seasonal disagreement despite the provider's fixed-EST documentation.
Reproduce on complete 60-minute hourly candidates, matching their bar-end label
to FXCM's bar start plus one hour, with explicit -1/0/+1-hour negative controls.
Resolve this using raw-minute observations around both US and European DST
transitions and independent source overlap. Do not automatically choose the
lowest-error offset, silently change the clock, or mark those candidate hours
repaired. The retained source ZIPs and Parquet manifests remain unchanged.

Map missing observations to actual provider file intervals and actual session
closures, resolve timestamp/quote semantics, verify replacements, then admit
the inventory and recompute preprocessing/selection. The candidate inventory
is 394 records across different roles, not 394 accepted features. Its original
nonfinite counts must be regenerated before admission using the corrected code.
No inference, interpolation, training or calendar acceptance occurred here.

## Raw clock replay and source-boundary recovery

`histdata_clock_resolution.py` now replays the original 2023 ZIPs, checks OHLC,
counts only complete 60-minute hours and compares fixed EST, US Eastern and a
European-DST cohort hypothesis on identical timestamps. Empty common support
is an error, not completed evidence. Seven tests pass, including a changed
retained metric rejected by a fresh raw-source replay before publication.

Actual comparison: 1,539 pair/date/hypothesis rows; EURUSD has 4,205 shared
hours over 257 dates, GBPUSD 4,319 over 256 dates. Disagreement with declared
fixed EST changes at European DST dates, not US dates. This is evidence of a
source-clock conflict, NOT an automatic choice of whichever offset scores best.
Raw archives and the current lake remain unchanged. The new report digest is
`c2ef457e30ff75acf2ba1813d80469a4a12f39b24f1e46b3eb9f56afbe9a57ab`.

Publication at `b6ae8413f`: 2 reports / 7,695 metrics read back, zero pending or
mismatched reports. Closed 2,895,872-byte DuckDB copies match on two machines:
`7b7fedd9ad674688b1be1568df2b94687aeee0becdc5e5b2f2426a9f11a1aa8e`.
The publisher reused the existing outbox/warehouse and stayed within 164.2 MiB,
without swap; elapsed 67.063 s. Expanded focused suite: 82 passed, 1 skipped,
4 existing timezone-to-month/week warnings. No financial training.

Reproduce with operator-configured roots (no credentials in command arguments):

```bash
python _scripts/histdata_clock_resolution.py --primary-root <native-hourly-root> \
  --histdata-root <raw-annual-root> --year 2023 --output <fresh-report-path>
python _scripts/publish_forexite_clock.py --root <ext4-publication-root> \
  --histdata-report <report-path> --primary-root <native-hourly-root> \
  --histdata-root <raw-annual-root> --predictor-root <predictor-checkout> \
  --warehouse-url <configured-warehouse> --code-commit <verified-code-pin> \
  --local-copy <bulk-closed-copy> --mirror-host <configured-mirror> \
  --mirror-relative-path <closed-copy-relative-to-home>
python _scripts/publish_forexite_clock.py --root <ext4-publication-root> --status
```

Actual source boundaries, not filename years, recover missing observations:
FXCM `H1/{EURUSD,GBPUSD}/2019/53.csv.gz` contains 40 missing hours per pair,
2020-01-02 06:00 through 2020-01-03 21:00 UTC. The two original compressed
response hashes are respectively
`f8fc2ef1c558eb4b73759886222df9c0ef9b60803a94b36442d67d3446c961e7`
and `fc0875b0e27323b59a8dc4dd2043457588521d09d99aea73af4258398e3ccfc0`.
Seven genuinely absent session weeks remain per pair; the 24 failed URL names
were not 24 missing session weeks. A bounded minute-archive fallback for both
pairs in 2024 weeks 35/51/52 and 2025 weeks 2/29/30 returned 12 HTTP 404s.
Retained acquisition STATUS receipts distinguish absence from successful repair;
do not poll the same missing URLs as though that were advancing the repair.

Calendar investigation found indicative Saturday quotes in native archives.
Do not treat a published quote as proof that trading was open. Dated regional
holiday notices also conflict with archive boundaries; those dates must remain
explicitly unresolved until the operational calendar is established. None of
these findings permits interpolation or treating closed hours as missing ticks.

Boundary candidate builder `recover_fxcm_boundary.py` (@5866040b6) executed:
40 original missing rows for each pair, original prices preserved, zero overlap
with baseline files, no interpolation or merge. It authenticates the two source
responses, checks all twelve baseline file hashes and writes a completion
manifest atomically with fsync. Its read-only status checks output hashes and
counts. Manifest digest:
`40026a5e33b174525668205a90401db3dfeec5286ffe7d87beee49590bb1db7d`.
25 tests pass when PREDICTOR_ROOT points to the actual parser checkout; omission
of that environment variable skips parser integration tests and is not acceptance.

```bash
python _scripts/recover_fxcm_boundary.py --predictor-root <parser-checkout> \
  --primary-root <native-hourly-root> --evidence-root <retained-fetch-evidence> \
  --output-root <new-boundary-directory>
python _scripts/recover_fxcm_boundary.py --status --output-root <boundary-directory>
```

The annual alternative download, unlike the unsuccessful monthly fallback,
completed four new original ZIPs, both pairs for 2024 and 2025, without failure:

| Pair/year | Observed minutes | Candidate hours | Hours missing at least one minute |
|---|---:|---:|---:|
| EURUSD 2024 | 372379 | 6243 | 733 |
| EURUSD 2025 | 372024 | 6225 | 497 |
| GBPUSD 2024 | 372047 | 6243 | 711 |
| GBPUSD 2025 | 371031 | 6225 | 640 |

These hour counts are acquisition candidates, not coverage certification. The
unchanged acquisition parser records the provider's declared fixed-EST clock;
that conflicts with the observed seasonal alignment and must not silently become
the admitted clock. HistData's primary ASCII specification identifies OHLC as
bid prices: https://www.histdata.com/f-a-q/data-files-detailed-specification/ .
The raw-clock comparison was also executed for 2024 (1518 comparison rows) and
2025 (1521); it still does not select a timezone automatically.

Next concrete recovery work: resolve and freeze the cohort-specific time rule
against independent raw observations, produce verified replacement hours with
explicit source provenance, account separately for holiday closures and genuine
missing observations, and rebuild the admitted inventory. The source ZIPs now
exist locally; do not report them as waiting for a download or credentials.

The 2024/2025 diagnostics were subsequently published and read back as well:
2 reports / 7,590 metrics (2024) and 2 reports / 7,605 metrics (2025), zero
pending/mismatches. Together with 2023: 6 reports / 22,890 metrics. Each closed
snapshot has matching copies on two machines. Respective snapshot SHA-256:
`45419a616fead78543a5913becbe032a71c22c99fd85a976bcef3ecdcb929f13`
and `8110c25d0cd2ad2243d555c13fccaef2c28ab617097c4366de661c7783ed4aae`.
