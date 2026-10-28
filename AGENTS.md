# AGENTS.md — financial-data

> **Read the [Do not touch](#do-not-touch) section before running anything.**
> This is a data repository, not an application. Its value is the data and the
> evidence trail, both of which an agent can destroy far faster than it can
> rebuild them.

## Project overview

`financial-data` is the data and research substrate of the harveybc trading
stack. It holds organized historical market and contextual datasets, derived
feature stores, the acquisition and validation scripts that produced them, the
staged work plan that governs the effort, and the experiment evidence and
research corpus built on top. Roughly 21,000 files are tracked in git;
the working tree on a provisioned machine is far larger, because the bulk data
itself is deliberately untracked.

It is not an installable application: there is no `setup.py`, no
`pyproject.toml`, no package and no entry point. It does not train production
models, generate synthetic data, serve predictions or execute trades — those
belong to [predictor](https://github.com/harveybc/predictor),
[feature-extractor](https://github.com/harveybc/feature-extractor),
[synthetic-datagen](https://github.com/harveybc/synthetic-datagen),
[prediction_provider](https://github.com/harveybc/prediction_provider) and
[lts](https://github.com/harveybc/lts).

**Read-mostly.** The normal agent task here is to locate a dataset, read it,
validate it against its recorded metadata, and report. Producing new data is a
governed operation described by a `work_plan/` stage document, not something to
improvise.

## Agent quickstart (locate → load → validate → show the user results)

There is nothing to install and nothing to train. The quickstart is: find a
dataset, load it, understand the contract that governs it, and check its
integrity. Every command below was executed from the repository root on Python
3.12.13 and left the working tree clean.

### 1. Environment

Use an existing Python 3 environment with `pandas`, `pyarrow` (for parquet) and
`matplotlib`. There is nothing to install from this repository. `PyYAML` is
needed by one test module and is often missing.

Write every output to a directory **outside this repository**:

```bash
export FD_OUT="${TMPDIR:-/tmp}/financial-data-agent"
mkdir -p "$FD_OUT"
```

### 2. Understand what is actually in a clone

This is the single most important fact about this repository, and it is not
obvious:

```bash
git ls-files '*.parquet' | wc -l     # -> 0
git ls-files '*.csv'     | wc -l     # -> 67
```

`.gitignore` excludes `*.parquet` and `*.csv` globally. **A clone contains no
OHLCV parquet at all.** Under `market_data/` and `features/trading_asset_data/`
you get only the documentation triad — `README.md`, `data_dictionary.md`,
`provenance.json` — describing data that lives on the provisioned machine and
nowhere else. Of the 67 tracked CSVs, 59 are under `trading_research/`.

So there are two distinct cases, and you must say which one you are in:

- **Committed data** — the tracked CSVs under `trading_research/`. Available in
  any clone. Use these for anything that must be reproducible from git alone.
- **The local data lake** — the parquet under `market_data/` and `features/`.
  Present only where it was acquired. Governed by
  [`features/MANIFEST.json`](features/MANIFEST.json) and the per-directory
  `provenance.json` files, which *are* tracked.

### 3. Locate and load a dataset

Confirm a file is committed before you rely on it:

```bash
git ls-files --error-unmatch trading_research/project2/part_II_redux/data/processed/btcusd_4h.csv
```

Three verified, committed candidates:

| Path | Header | Rows | Range |
|---|---|---|---|
| `trading_research/project2/part_II_redux/data/processed/btcusd_4h.csv` | `DateTime,Open,High,Low,Close,Volume` | 18,332 | 2017-08-17 04:00 → 2025-12-31 00:00 |
| `trading_research/extended_data/EUR_USD_daily.csv` | `Date,Close,High,Low,Open,Volume` | 5,806 | 2003-12-01 → 2026-04-17 (volume all zero) |
| `trading_research/feature_store/ETH_USD_daily.csv` | `Date,Close,High,Low,Open,Volume,macro_*,crypto_*,log_return,…` (26 cols) | 2,974 | 2017-11-09 → 2025-12-30 |

Same-schema siblings of the first live beside it: `eurusd_4h.csv`,
`usdjpy_4h.csv`, `eurusd_1h.csv`, plus daily and weekly variants.

Load it read-only and describe it:

```bash
python - "$FD_OUT" <<'PYEOF'
import sys, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = sys.argv[1]
SRC = "trading_research/project2/part_II_redux/data/processed/btcusd_4h.csv"

df = pd.read_csv(SRC, parse_dates=["DateTime"]).set_index("DateTime").sort_index()
print(f"{SRC}\n  rows={len(df)}  columns={list(df.columns)}")
print(f"  range: {df.index[0]} -> {df.index[-1]}")
print(f"  close: min={df.Close.min():,.2f}  max={df.Close.max():,.2f}")

ax = df["Close"].plot(figsize=(12, 5), logy=True, lw=0.8)
ax.set_title("BTC/USD 4h close (log scale)")
ax.set_ylabel("close (USD)")
plt.tight_layout()
plt.savefig(f"{OUT}/btcusd_4h_close.png", dpi=130)
print("wrote", f"{OUT}/btcusd_4h_close.png")
PYEOF
```

Observed output:

```
  rows=18332  columns=['Open', 'High', 'Low', 'Close', 'Volume']
  range: 2017-08-17 04:00:00 -> 2025-12-31 00:00:00
  close: min=2,919.00  max=125,410.81
```

For the local lake, the manifest tells you the path, row count, date range and
column list without opening a single parquet file:

```bash
python -c "
import json
m = json.load(open('features/MANIFEST.json'))
e = m['trading_assets']['ethusdt']['timeframes']['4h']
print(e['path'], e['status'], e['rows'], e['start'], '->', e['end'])
print(e['columns'])"
```

which prints `features/trading_asset_data/ethusdt/4h.parquet ok 18337
2017-08-17T04:00:00+00:00 -> 2025-12-31T20:00:00+00:00` and the eleven
Binance-shaped column names. The manifest covers 50 trading assets across the
`5m` / `15m` / `1h` / `4h` timeframes.

### 4. Data contracts and manifests

| File | What it governs |
|---|---|
| [`features/MANIFEST.json`](features/MANIFEST.json) | Stage 2.1 inventory of the canonical per-asset parquet: path, status, row count, start/end, column list, for 50 assets × 4 timeframes. Tracked; the parquet it points at is not. |
| [`features/AVAILABILITY_CONTRACT.md`](features/AVAILABILITY_CONTRACT.md) | The point-in-time availability rules. Twelve required metadata fields (`event_time`, `available_at_utc`, `vintage_or_revision_id`, `release_lag_policy`, `forward_fill_policy`, `staleness_age_bars`, …), six vintage-policy labels, per-source-family requirements and blocking rules. Declared a **blocking contract** for Stage B promotion and Stage C held-out claims. |
| [`configs/availability_contract.schema.json`](configs/availability_contract.schema.json) | The machine-enforceable JSON Schema counterpart. Required keys include `feature_family`, `provider`, `observation_ts_col`, `available_from_ts_col`, `revision_policy`, `license_scope`. |
| [`configs/experiment_registry.schema.json`](configs/experiment_registry.schema.json) | Schema for experiment registration. |
| `market_data/**/provenance.json`, `features/cross_source_docs/**/provenance.json` | Per-directory acquisition record: source, description, `acquired_at`, and a `files[]` list of `{path, sha256}`. This is the de-facto hash catalog — roughly 140 under `market_data/` and 420 under `features/`. Template: [`_templates/provenance_template.json`](_templates/provenance_template.json). |
| `experiments/stage_a_screening/inputs/<asset>/<tf>/<preset>/train_metadata.json` | Per-screening-dataset record: asset, row count, the full feature-column list, and a `sha256` of the materialized CSV. |
| `experiments/stage_b_validation/manifests/*.json` | Stage B experiment manifests: `experiment_id`, `cost_scenarios[]`, `feature_variants[]`. |
| `experiments/stage3x_*_contract/*.json` and `*.md` | Phase 3X market-state, walk-forward and portfolio evidence contracts. |
| `artifacts/run_ledger.jsonl` | The append-only run ledger, referred to throughout the workers as the **immutable** record. Untracked (local-only). Row keys include `run_id`, `event_type`, `data_version`, `financial_data_git_sha`, `split_version`, `action_space_hash`, `reward_config_hash`, `cost_scenario`. |

Each data directory also carries `README.md` and `data_dictionary.md`. The
triad README + data_dictionary + provenance is enforced by the Stage 1.3 and
1.6 validation workers.

There are **no** `*.sha256`, `checksums` or `CATALOG` files. Hashes live inside
the JSON records above.

### 5. Validate integrity

**There is no general-purpose "verify this repository" command.** No script
walks the `provenance.json` files and re-checks their hashes; the workers only
ever *write* provenance. The one place a recorded hash is actually verified at
runtime is `_scripts/workers/stageb_dsr_pbo_evaluator.py`, which compares a
trace file's `trace_file_sha256` and raises `EvidenceError` on mismatch — and
it skips the check silently when the expected hash is empty.

The hashing primitives are there, so verification is a few lines. This is
read-only and works wherever the lake is present:

```bash
python - <<'PYEOF'
import json, sys, pathlib
sys.path.insert(0, "_scripts/workers")
from stage13_common import sha256_file

prov = json.load(open("market_data/forex/g10/eurusd/provenance.json"))
print("source:", prov["source"], "| files recorded:", len(prov["files"]))
for e in prov["files"]:
    p = pathlib.Path(e["path"])
    if not p.exists():
        print(f"  MISSING (local-only lake, not in a clone): {p}")
        continue
    print(f"  {'OK  ' if sha256_file(p) == e['sha256'] else 'FAIL'} {p}")
PYEOF
```

Observed on a provisioned machine: `source: HistData | files recorded: 4`,
then `OK` for `5m.parquet`, `15m.parquet`, `4h.parquet` and `1h.parquet`. In a
bare clone every line reports `MISSING`, which is the correct and expected
result.

Related helpers: `_scripts/lib/artifact_metadata.py` provides
`compute_file_hash`, `compute_config_hash` (canonical sorted JSON) and
`compute_manifest_hash`; `_scripts/lib/provenance.py` re-exports `sha256_file`;
`_scripts/lib/validation.py` provides `read_table`, `validate_non_empty_table`
and `validate_ohlcv_shape`.

Structural and quality validation is done by the Stage 1.6 workers, which take
`--machine` and `--roots` and write their reports into the untracked
`_metadata/`:

```bash
python _scripts/workers/stage16_preflight_validation_worker.py --help
python _scripts/workers/stage16_quality_worker.py --help
```

### 6. Tests

```bash
python -m pytest _scripts/tests -q --ignore=_scripts/tests/test_p3x_feature_redundancy_stability.py
```

401 tests collect. The ignore is required: without it collection is
interrupted by `ModuleNotFoundError: No module named 'yaml'` — `PyYAML` is
missing even though the repository ships `configs/cost_scenarios.yaml` and
`configs/unsupervised/p3x_defaults.yaml`.

Verified execution is limited to one module:
`python -m pytest _scripts/tests/test_stageb_dsr_pbo_evaluator.py -q` →
**27 passed** in 0.74 s, with the working tree clean afterwards. The remaining
400 tests were collected but not executed here.

### 7. Final message to the user

Report exactly this, with `<out>` replaced by the value of `$FD_OUT`:

> Done. Nothing in the repository was modified — everything was read-only, and
> all output went outside the repo to `<out>/`:
>
> - `<out>/btcusd_4h_close.png` — the BTC/USD 4-hour close series on a log
>   scale, from `trading_research/project2/part_II_redux/data/processed/btcusd_4h.csv`:
>   **18,332 bars, 2017-08-17 04:00 → 2025-12-31 00:00**, close ranging
>   2,919.00 → 125,410.81.
>
> Two things worth knowing about this repository:
>
> - A clone contains **no** parquet and only 67 CSVs. The `market_data/` and
>   `features/` trees ship documentation and `provenance.json` hash records
>   only; the data itself exists solely on a provisioned machine.
>   `features/MANIFEST.json` tells you what *should* be there — 50 assets ×
>   4 timeframes, with row counts and date ranges — without needing the files.
> - Integrity checks are recorded but not automated. Every data directory has a
>   `provenance.json` with per-file SHA-256, and re-verifying them takes about
>   ten lines (see step 5 of `AGENTS.md`), but no shipped command does it.
>
> There is no web UI; these are files on disk.
>
> **Analysis to try first:** reconcile `features/MANIFEST.json` against the
> filesystem — for each of the 50 assets and 4 timeframes, report whether the
> parquet exists, and where it does, whether its row count and start/end match
> the manifest. That single pass tells you exactly how much of the declared
> lake this machine actually holds and whether any of it has drifted from its
> recorded state. It is read-only, and it is the check the repository documents
> but does not ship.

## Build, test and lint commands

There is no build. There is no package. There is no linter, formatter or CI
configuration.

```bash
# Tests (the ignore is required; PyYAML is missing)
python -m pytest _scripts/tests -q --ignore=_scripts/tests/test_p3x_feature_redundancy_stability.py

# Worker help
python _scripts/workers/stage16_preflight_validation_worker.py --help
python _scripts/workers/stage16_quality_worker.py --help
```

Most workers have no argparse interface at all — they expose a `main()` and are
driven by the orchestration layer.

## Layout

| Path | Contents |
|---|---|
| `market_data/` | OHLCV by asset class: `forex/{g10,emerging_markets}`, `crypto/{spot_top50,perpetuals,funding_rates}`, `equities/`, `commodities/`, `bonds/`. **Documentation and `provenance.json` only in a clone**; the parquet is local-only. |
| `features/` | Derived stores: `trading_asset_data/` (canonical per-asset parquet), `trading_asset_features/`, `cross_source_features/`, `cross_source_docs/`. `cross_source_statistical/`, `learned_inputs/` and `learned_models/` are gitignored. Governed by `MANIFEST.json` and `AVAILABILITY_CONTRACT.md`. |
| `macro_economic/` | Series by provider: `fred/`, `ecb/`, `imf/`, `oecd/`, `bls/`, `bea/`, `boj/`, `world_bank/`, `yield_curves/`, `inflation_expectations/`. |
| `alternative_data/` | COT reports, on-chain BTC/ETH, DeFi metrics, ETF and exchange flows, SEC filings, analyst estimates. |
| `economic_calendar/` | `scheduled_events/`, `release_actuals/`, `release_surprises/`. |
| `reference_data/` | Calendars, holidays, index constituents, sector classifications, symbol mappings. |
| `derivatives/`, `fundamental/`, `microstructure/` | Scaffolding only — `.gitkeep` placeholders, no data yet. |
| `experiments/` | The largest tree. Stage A screening, Stage B validation, Stage 3X contracts, portfolio supervisor. Tracked content is almost entirely JSON evidence. |
| `trading_research/` | Cross-repo research corpus and **the only committed bulk CSV data**. Analysis modules (`evaluation_harness.py`, `extend_history.py`, `naive_baseline.py`, `edge_over_bh.py`, …) plus `feature_store/`, `extended_data/`, `results/`, `project2/`. |
| `work_plan/` | The staged plan, numbered markdown from `00_PROJECT_3_MASTER_PLAN.md` through `40_PHASE_4_SYNTHETIC_DATA_AUGMENTATION.md`. Read this before deriving anything. |
| `_scripts/workers/` | ~103 stage workers: `stage13_*` acquisition, `stage15_*` paid sources, `stage16_*` validation, `stage2x_*` derivation, `stage31_*`/`stage32_*` screening and synthesis, `stage3x_*` causal, `stage_b_*` validation. |
| `_scripts/lib/` | Shared library: `validation.py`, `artifact_metadata.py`, `provenance.py`, `split_guard.py`, `feature_alignment.py`, `experiment_ledger.py`, `acquisition_log.py`, `gpu_lock.py`. |
| `_scripts/orchestration/`, `_scripts/cron/`, `_scripts/systemd/` | Multi-host daemons, watchdogs and scheduled jobs. Require SSH access to a GPU cluster configured out of band. |
| `_scripts/tests/` | 35 pytest modules named after the workers they cover. |
| `configs/`, `_templates/` | Schemas, cost scenarios, and the README / data_dictionary / provenance templates. |
| `_metadata/`, `_logs/`, `artifacts/run_ledger.*` | Untracked local records: data catalog, acquisition logs, validation JSONs, run ledger, worker logs. |
| `STAGE_*.md`, `INVENTORY.md` at the root | Point-in-time deliverable reports. Historical — later stages supersede earlier ones, and `INVENTORY.md` (2.44 GB, 1,662 files) badly understates the current lake. |

### Column naming — three conventions, and they do not agree

1. **Parquet lake, lowercase.** `market_data/forex/g10/*/`:
   `datetime, open, high, low, close`. `features/trading_asset_data/*/`:
   `timestamp, open, high, low, close, volume, close_time, quote_volume,
   trade_count, taker_buy_base_volume, taker_buy_quote_volume`.
2. **`trading_research/` CSVs, TitleCase, Close before High:**
   `Date,Close,High,Low,Open,Volume` — yfinance ordering.
3. **`trading_research/project2/` CSVs, TitleCase, conventional order:**
   `DateTime,Open,High,Low,Close,Volume`.

There is no all-caps `DATE_TIME,OPEN,HIGH,LOW,CLOSE,VOLUME` convention in this
repository, unlike the sibling repos in the stack. Do not assume it.
`_scripts/lib/validation.py` normalizes with `.lower()` and tolerates all
three. Feature columns are snake_case with numeric suffixes (`log_return_20`,
`close_sma_ratio_100`, `roll_skew_ret_252`, `fracdiff_d_0.6`).

## Conventions and constraints

- **Evidence over assertion.** Every acquisition and derivation is expected to
  leave a trace: a `provenance.json`, a manifest entry, a validation record in
  `_metadata/`, a ledger row, and a `STAGE_*.md` deliverable. A result without
  its trace does not count.
- **Stage discipline.** To derive data, follow the corresponding `work_plan/`
  stage document. Do not improvise ad-hoc processing.
- **Held-out firewall.** 2025 held-out windows and Stage C data are walled off
  from model selection. `_scripts/lib/split_guard.py` and the Stage C firewall
  in `stageb_dsr_pbo_evaluator.py` enforce it. Never widen a split, disable a
  guard or read Stage C data into a selection-time path.
- **The run ledger is immutable.** Append only; never rewrite or truncate.
- **Credentials come from the environment,** never from the repository.
  Acquisition workers read `FRED_API_KEY`, `BEA_API_KEY`, `ETHERSCAN_API_KEY`,
  `CRYPTOQUANT_API_KEY`, `FXMACRODATA_API_KEY`, `TELEGRAM_BOT_TOKEN` and
  similar from the process environment or from ignored files under
  `_metadata/`. Never commit a value, and never echo one into a log, a report
  or a commit message.
- **This repository is public.** See [`SECURITY.md`](SECURITY.md). Do not add
  provider credentials, broker account identifiers or fingerprints, personal
  identity details, private-network addresses, SSH endpoints or machine
  credentials, or paid datasets that may not be redistributed. Examples use
  placeholders and documentation-reserved addresses only — keep it that way,
  and use `<your-host>` rather than naming a machine.
- **Absolute home paths already leak into some tracked JSON evidence**
  (`train_metadata.json` `output_csv`/`sources`, some `provenance.json`
  descriptions), and a few orchestration scripts hardcode an SSH login and a
  non-standard port. Do not add more, and do not copy any of them into
  documentation.
- **Network access is required** by the ~17 acquisition workers that call
  provider HTTP APIs, and the orchestration layer additionally needs SSH to a
  GPU cluster plus `rsync`. None of that is available from a bare clone.

## Do not touch

This section matters more here than anywhere else in the stack. This
repository holds primary data. Much of it is expensive or impossible to
re-acquire, and much of it is untracked, which means **git will not save you**.

- **Never modify, move, rename, delete, re-sort, re-index, resample, clean,
  deduplicate, re-compress or "tidy" any dataset.** Not the parquet under
  `market_data/` or `features/`, not the CSVs under `trading_research/`, not
  the raw `.txt`/`.xml` under `alternative_data/`. Read them. That is all.
- **Do not reorganize the directory tree.** The layout is a contract:
  `MANIFEST.json`, every `provenance.json`, and thousands of JSON evidence
  records store paths. Moving one directory silently invalidates all of them.
- **Untracked means unrecoverable.** `*.parquet`, `*.csv`, `*.zip`, `*.gz` and
  `*.jsonl` are gitignored globally, and `_metadata/`, `_logs/`,
  `features/learned_inputs/`, `features/learned_models/`,
  `features/cross_source_statistical/` and several `experiments/` subtrees are
  ignored in full. Deleting any of it destroys it permanently. Never run a
  bulk `rm`, `find -delete`, `git clean -x`, `git clean -f` or `git reset
  --hard` here.
- **Do not regenerate provenance, manifests or validation records** to make a
  check pass. A hash mismatch is a finding to report, not a file to rewrite.
- **Do not edit the run ledger** (`artifacts/run_ledger.jsonl`) or any
  `STAGE_*.md` deliverable. They are point-in-time records.
- **Do not write outputs into this repository.** Send plots, extracts,
  scratch files and reports to a directory outside it (`$FD_OUT` above).
- **Do not run acquisition workers casually.** They hit paid and rate-limited
  provider APIs, they consume quota, and they overwrite data in place.
- **Do not run the orchestration or cron scripts.** They dispatch jobs to a
  GPU cluster over SSH and will interfere with running training work.
- **Do not touch other repositories** from here.
- **Do not commit anything the [`SECURITY.md`](SECURITY.md) boundary forbids**,
  and do not commit large binaries — the gitignore rules exist to keep bulk
  data out of git and must not be relaxed.

### Known documentation defects

Report these rather than working around them:

- [`README.md`](README.md) contradicts itself on visibility: it opens with
  "Private data lake" and states "It is a **private** repository", but later
  says "This public repository", and [`SECURITY.md`](SECURITY.md) states the
  repository is public. The public reading is the current one.
- `README.md` presents `market_data/` as holding OHLCV price history without
  saying that a clone contains none of it.
- `README.md` claims "There is no package-level test suite" — 401 tests
  collect from `_scripts/tests/`.
- `README.md` directs readers to "verify the produced data against the
  `_metadata/` validation records", which a cloner cannot do: `_metadata/` is
  gitignored in full.
- `INVENTORY.md` is stale by orders of magnitude.
