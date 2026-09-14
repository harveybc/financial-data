# financial-data

Data lake, provenance metadata and research substrate for time-series experiments. This
repository holds the organized historical market and contextual datasets, the
feature stores and learned representations derived from them, the automation
scripts that acquire/validate/transform that data, the staged work plan that
governs the effort, and the research corpus used to evaluate strategies and
audit the surrounding repositories. The optional [file-lake service](lake/README.md)
exposes inventory and governed deliveries to [data-gov](https://github.com/harveybc/data-gov).
The data repository and its service adapter have separate setup requirements.

## Status

**Research infrastructure under active development.** Published code and metadata
do not grant access to every dataset referenced by an inventory. A clone is not
a copy of the provisioned lake; paid and restricted datasets are not redistributed.
Dataset terms and availability must be checked separately from the code license.

## Current implementation and research

This default branch includes the file-lake adapter from the tested revision
`13e6b1f47`: download receipts, range materialization and real HTTP-server
regressions. [Service setup and tests](lake/README.md) live with the adapter.
Resource contracts are intentionally empty in the financial default config;
configure factual contracts for your own data rather than assuming a timestamp
is also its publication or availability time.

The broader inventory, characterization and producer-lineage work is available
in the [published research snapshot](https://github.com/harveybc/financial-data/tree/f00bc6c151392d3cc3193f24a1c797c7ba7988d8).
Those campaign artifacts have not all been merged into this default branch.
The [research repository map](https://github.com/harveybc/predictor/blob/master/docs/RESEARCH_STACK.md)
explains how the lake, preprocessing and representation-learning components connect.

## Role and non-responsibilities

`financial-data` is the single home for curated datasets, derived features,
acquisition/validation metadata, experiment evidence and cross-repo research
notes.

It does **not**:

- replace the governance system: policies and experiment accounting belong to
  data-gov; the installable `lake/` adapter serves this repository's data;
- train production models — that is
  [predictor](https://github.com/harveybc/predictor) (autoencoder training
  configs generated here are executed with
  [feature-extractor](https://github.com/harveybc/feature-extractor));
- generate synthetic data — that is
  [synthetic-datagen](https://github.com/harveybc/synthetic-datagen),
  which the phase-4 plan here targets;
- serve predictions or execute trades — that is
  [prediction_provider](https://github.com/harveybc/prediction_provider) and
  [lts](https://github.com/harveybc/lts).

## Repository layout

### Data roots (one directory per data domain)

| Root | Contents |
|---|---|
| [`market_data/`](market_data) | OHLCV price history organized by asset class (forex, crypto, equities, commodities, bonds) |
| [`macro_economic/`](macro_economic) | Macro-economic series |
| [`microstructure/`](microstructure) | Market-microstructure datasets |
| [`derivatives/`](derivatives) | Derivatives-related datasets |
| [`fundamental/`](fundamental) | Fundamental data |
| [`alternative_data/`](alternative_data) | Alternative data sources |
| [`economic_calendar/`](economic_calendar) | Scheduled-event calendars |
| [`reference_data/`](reference_data) | Reference/static data |
| [`features/`](features) | Derived feature stores: cross-source features and statistics, learned inputs and learned models; governed by [`features/MANIFEST.json`](features/MANIFEST.json) and [`features/AVAILABILITY_CONTRACT.md`](features/AVAILABILITY_CONTRACT.md), with its own [`features/README.md`](features/README.md) |

Under `features/learned_inputs/` (untracked local data; tracked parent:
[`features/`](features)), per-asset and
per-timeframe directories carry `feature_extractor_config_template.json`
files — the bridge to
[feature-extractor](https://github.com/harveybc/feature-extractor), which
trains the corresponding autoencoder representations (Stage 2.4).

### Automation (`_scripts/`)

| Subdirectory | Purpose |
|---|---|
| [`_scripts/workers/`](_scripts/workers) | Acquisition/processing worker scripts |
| [`_scripts/orchestration/`](_scripts/orchestration) | Multi-step job orchestration |
| [`_scripts/cron/`](_scripts/cron) | Scheduled-job definitions |
| [`_scripts/systemd/`](_scripts/systemd) | Service unit files for long-running jobs |
| [`_scripts/analysis/`](_scripts/analysis) | Analysis utilities |
| [`_scripts/lib/`](_scripts/lib) | Shared script library code |
| [`_scripts/tests/`](_scripts/tests) | Script-level tests |

### Plan, metadata and evidence

- [`work_plan/`](work_plan) — the staged plan: Phase 1 (storage architecture,
  data catalog, acquisition, validation), Phase 2 (downsampling/resampling,
  technical/statistical features, signal decomposition, learned
  representations), Phase 3 (experiment framework and results synthesis) and
  Phase 4 (synthetic-data augmentation, executed with
  [synthetic-datagen](https://github.com/harveybc/synthetic-datagen)).
- `STAGE_*.md` at the root (e.g.
  [`STAGE_2.4_DELIVERABLE.md`](STAGE_2.4_DELIVERABLE.md)) — point-in-time
  deliverable reports per completed stage.
- `_metadata/` (untracked private records) — data catalog, acquisition
  logs and validation/preflight records (JSON/CSV) that document what was
  ingested, when, and with what quality checks.
- [`_templates/`](_templates), [`configs/`](configs),
  [`artifacts/`](artifacts), [`deliverables/`](deliverables),
  [`experiments/`](experiments), `_logs/` (untracked) — supporting templates,
  run configurations, produced artifacts and logs.

### Research corpus

[`trading_research/`](trading_research) is the cross-repo research authority:
evaluation harnesses, baseline and sensitivity studies, portfolio analyses,
extended-history tooling and audit documents that classify and review the
surrounding repositories. Conclusions recorded here (for example, which
repositories are superseded) are treated as evidence by the rest of the
stack's documentation.

## Requirements and usage

There is no packaging (`setup.py`/`pyproject.toml`) and no installable
entry point — this repository is operated through the scripts in
[`_scripts/`](_scripts) inside the stack's unified Python environment, and
consumed by sibling repositories as files. Typical usage is:

1. consult [`work_plan/`](work_plan) for the stage definition;
2. run the relevant `_scripts/` worker or orchestration script;
3. verify the produced data against the `_metadata/` validation records;
4. record the stage outcome as a `STAGE_*.md` deliverable.

No installation or test commands are claimed here; script execution depends
on locally provisioned data-source access and was not exercised for this
README.

## Reproducibility

Every acquisition and derivation is expected to leave a trace: catalog entries
and acquisition logs in `_metadata/` (untracked), manifests and availability
contracts under [`features/`](features), dataset hashes recorded in commits
and deliverable reports, and per-stage validation JSONs. When re-deriving
data, follow the corresponding `work_plan/` stage document rather than ad-hoc
processing.

## Safety, security and credentials

- **No credentials, API keys or account identifiers are committed** to this
  repository, and none may be added. Acquisition scripts obtain any required
  access configuration from the local environment, outside version control.
- Paid or restricted datasets are not redistributed. This public repository
  contains acquisition code, metadata contracts and only data whose source
  permits publication.
- Private network routes, account fingerprints and operator details remain
  outside version control. See [`SECURITY.md`](SECURITY.md).
- The data here is historical research material. Nothing in this repository
  is financial advice.

## Limitations

- [`INVENTORY.md`](INVENTORY.md) and the early `STAGE_1.x` snapshots are
  historical documents; later stages (see
  [`STAGE_2.4_DELIVERABLE.md`](STAGE_2.4_DELIVERABLE.md) and subsequent
  commits) supersede them. Treat root-level stage reports as point-in-time
  records, not current status.
- There is no package-level test suite; validation lives in per-stage
  validation records and [`_scripts/tests/`](_scripts/tests).
- Large binary datasets make this repository heavy; clone accordingly.

## Related repositories

- [feature-extractor](https://github.com/harveybc/feature-extractor) —
  executes the learned-representation configs templated here.
- [synthetic-datagen](https://github.com/harveybc/synthetic-datagen) —
  executes the phase-4 augmentation plan.
- [predictor](https://github.com/harveybc/predictor) — model training that
  consumes datasets and features prepared here.
- [preprocessor](https://github.com/harveybc/preprocessor) and
  [feature-eng](https://github.com/harveybc/feature-eng) — the dataset
  preparation stages of the same pipeline.
- [prediction_provider](https://github.com/harveybc/prediction_provider) and
  [lts](https://github.com/harveybc/lts) — serving and execution layers
  downstream of the research done here.

## License

No license file is present. No permission to reuse the repository contents is
granted beyond rights supplied by the original data sources.
