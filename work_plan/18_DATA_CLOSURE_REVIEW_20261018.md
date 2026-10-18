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

Map missing observations to actual provider file intervals and actual session
closures, resolve timestamp/quote semantics, verify replacements, then admit
the inventory and recompute preprocessing/selection. The candidate inventory
is 394 records across different roles, not 394 accepted features. Its original
nonfinite counts must be regenerated before admission using the corrected code.
No inference, interpolation, training or calendar acceptance occurred here.
