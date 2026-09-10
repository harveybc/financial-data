# Incremental canonical census

Two grains, kept separate on purpose:

- **physical appearance** — one materialized slice (file, period, source,
  frequency, declared schema, bytes, digest when policy allows);
- **conceptual variable** — one stable logical id with semantics, unit, role,
  availability and lineage, carrying the list of appearances it materializes in.

An appearance is never counted as a variable, a physical path is never a
logical identity, equivalences and conflicts are declared rather than resolved
by name, `event_time` and `available_time` are separate fields, and an
undeclared field stays `UNKNOWN`/`UNAVAILABLE`.

## Files

- `CENSUS_SUMMARY.v1.json` — the small, reviewable summary (coverage, gaps by
  both grains, declared conflicts, delta). This is what belongs in Git.
- `CENSUS_RECEIPT.v1.json` — reproducibility receipt: census digest, file
  digest, code identity, manifest digest. Grants nothing.
- the full census is **content-addressed outside the repository** as
  `census-<sha256>.json`; the receipt names its digest and size.

## Reproduce

```bash
python _scripts/build_incremental_census.py \
  --censused-at 2026-09-10T00:00:00Z \
  --out-dir <state_root>/financial_data_census \
  --summary features/census/CENSUS_SUMMARY.v1.json \
  --receipt features/census/CENSUS_RECEIPT.v1.json \
  --external-full-profile ../predictor/examples/research/crispdm_dataset_inventory.v1.json \
  --value-profile-per-class 6
```

Add `--previous <state_root>/financial_data_census/census-<sha>.json` for the
`ADDED`/`UNCHANGED`/`CHANGED`/`MISSING` delta; only slices whose bytes changed
(or that are explicitly `--select`ed) are re-digested, so an incremental run
does not re-read the lake.

## Value sweep

Level 1 is the FULL profile of the active model-ready views, bound by digest
from the consuming repository (`predictor`'s CRISP-DM inventory) — this census
never re-profiles bytes another repository already profiled.
Level 2 is a deterministic, declared SAMPLE per source class. A sampled profile
is labelled `SAMPLED_HEAD_NOT_A_COMPLETE_PHYSICAL_CENSUS` and is never
presented as a complete physical census.
