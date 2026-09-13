# financial-data lake service

Operator UI + HTTP adapter for [data-gov](https://github.com/harveybc/data-gov).
This is **the file lake**, not a toy glob of one parquet.

- UI: http://127.0.0.1:5056 — inventory, globs, holdout, coverage probe
- API for data-gov: `/api/v1/discover`, `/coverage`, `/read`
- Discover walks `market_data`, `macro_economic`, … with `stat()` only
- Content `sha256` is computed **on read**, never on inventory
- Holdout: `from`/`to` ≥ `2025-01-01` → 403

```bash
cd lake
pip install -r requirements.txt
pip install -e .
python3 -m pytest tests -q
sh scripts/serve.sh
```

AAA (who may call `/read`) is **data-gov**, not this process. Bind is localhost.
