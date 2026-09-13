# financial-data lake service

Operator UI + HTTP adapter for [data-gov](https://github.com/harveybc/data-gov).
This is **the file lake**, not a toy glob of one parquet.

- UI: http://127.0.0.1:5056 — inventory, globs, holdout, coverage probe
- API for data-gov: `/api/v1/discover`, `/coverage`, `/read`, `/download`
- Discover walks `market_data`, `macro_economic`, … with `stat()` only
- Coverage reads the time column only (parquet: that column; CSV: `usecols` in chunks)
- Content `sha256` is computed **on download**, never on inventory
- Holdout: `to` ≥ `holdout_start` → 403; `from`/`to` are calendar days (`YYYY-MM-DD`)

```bash
cd lake
pip install -r requirements.txt
pip install -e .
python -m pytest tests -q
sh scripts/serve.sh
```

AAA (who may call the API) is **data-gov**, not this process. Bind is localhost.

## `GET /api/v1/download?resource=&from=&to=`

What is delivered is a file that exists on this disk; its sha256 is the identity.

- **No range**: the source file `AS_IS`. Under `holdout_start` this needs the resource's
  `t_max < holdout_start` (from the time column alone) or the resource listed under `untimed`;
  otherwise 403 `spans holdout: request a range` / `no time column under holdout`.
- **Range**: `from`/`to` calendar days, `from <= to`, `to < holdout_start`. Rows with
  `from 00:00 <= t < (to + 1 day) 00:00` on the column's **own wall clock** (tz-aware values
  compared after dropping the zone) are kept. The cut is `var/cuts/<source_sha256>/<from>_<to>.<ext>`,
  materialised once, never rewritten. A cut that removes no rows is not written: the source is
  served `AS_IS`. After the cut `max(t) < holdout_start` is asserted (else 403 `holdout`).
- CSV cuts are a byte subset of the source (header + kept lines); multi-line quoted records are
  422 `unsupported csv`. Parquet cuts filter by row group with pinned writer options
  (snappy, format 2.6, dictionary, statistics, the source's row group size).
- The time column is `time_columns[resource]`, else `time_column`, else the first column named
  `ts,time,date,datetime,timestamp` or containing `time`/`date`. String columns must be ISO 8601;
  numbers (epoch) or blanks are 422 `unparseable time column`.
- Headers on 200: `Content-Disposition`, `Content-Length`, `X-Content-SHA256`,
  `X-Source-SHA256`, `X-Delivery` (`AS_IS`|`CUT`), `X-Time-Column`.
- Errors: 400 invalid from/to, 401, 403, 404 unknown resource, 422, 503 with `Retry-After: 30`
  when the `max_downloads` slots are busy.

## Operational rules

- Every intermediate file lives under `var/` (gitignored): `spool_dir` (default `var/spool/`,
  swept at process start, never `tempfile`) and `cuts_dir` (default `var/cuts/`).
- `var/source_sha256.json` memoises file hashes per `(path, size, mtime_ns)`; hashing streams
  1 MiB chunks.
- `max_downloads` (default 2) bounds concurrent downloads; the slot is held until the response
  is closed.

## Config keys

| key | default | meaning |
|---|---|---|
| `holdout_start` | `2025-01-01` | first day that can never be served |
| `time_column` | `null` | lake-wide time column name |
| `time_columns` | `{}` | `resource_id → column` overrides |
| `untimed` | `[]` | resources without a time axis, served `AS_IS` (declared by a human) |
| `spool_dir` / `cuts_dir` | `var/spool`, `var/cuts` | on-disk intermediates and cuts |
| `max_downloads` | `2` | concurrent download slots |
