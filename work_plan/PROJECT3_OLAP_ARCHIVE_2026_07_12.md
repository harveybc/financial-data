# Project 3 OLAP Archive - 2026-07-12

## Purpose

This archive preserves the consolidated Project 3 weekly walk-forward state and
OLAP evidence before the repositories are cleaned and supervision moves to a
different workstation. It intentionally excludes long stdout logs, temporary
training progress, return traces and other reproducible runtime noise.

GitHub release:

```text
https://github.com/harveybc/financial-data/releases/tag/project3-olap-2026-07-12
```

The release is the canonical remote binary backup. Source code, schema,
procedures and this evidence record remain in Git.

## Integrity Evidence

The backup was created with
`agent-multi/tools/project3_weekly_pool_backup.py`, which uses SQLite's online
backup API and requires `PRAGMA integrity_check = ok` before exporting.

Canonical snapshot:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `project3_weekly_pool.sqlite.gz` | 86,876,983 | `f8453acadb34678c30000ee69e1f3b4605ba6daf8c91c8297671facbfa4c4a83` |

The release also contains `manifest.json`, `schema.sql`, job/subjob exports and
all current OLAP views. `manifest.json` records the SHA-256 of every export.

## Coverage Snapshot

| Object | Rows |
| --- | ---: |
| `jobs` | 1,232 |
| `subjobs` | 26,976 |
| `weekly_result_olap` | 16,939 |
| `weekly_result_test_year_olap` | 891 |
| `weekly_result_validation_year_olap` | 992 |
| `weekly_result_full_year_protocol_olap` | 242 |
| `weekly_result_artifact_olap` | 55,652 |

Subjob status at snapshot time: `done=16,939`, `deferred=7,386`,
`superseded=2,624`, `failed=27`. These are historical Project 3 states, not a
queue that should be restarted automatically.

## Restore

1. Download `project3_weekly_pool.sqlite.gz` and `manifest.json` from the
   release.
2. Verify the compressed SHA-256 above and the per-file hashes in the manifest.
3. Decompress to a new path; do not overwrite another active SQLite database.
4. Run `PRAGMA integrity_check` and compare the object counts above.
5. Point Metabase or analysis scripts to the restored database in read-only
   mode until a new supervisor is explicitly promoted.

No Project 3 cron job, service or shell startup hook is required to analyze the
archive.
