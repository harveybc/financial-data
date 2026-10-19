# Admitted-core selection handoff

Owner request2026-10-19: actually compare SAC direct and the existing temporal
representation on identical selected information. This is a scoped first
comparison, NOT completion of admission/selection of the external catalogue.

## Requirements And Tests

| ID | Requirement | Behavioral evidence |
|---|---|---|
| CS01 | Read the actual admitted EURUSD receipt and verify source/calendar hashes | Changed price or closure bytes rejected |
| CS02 | Reuse the existing feature-eng technical generator without fitting | Prefix invariance and future perturbation; record generator digest |
| CS03 | No interpolation, centered transforms or fabricated closed-hour rows | Exact observed keys preserved; only declared leading indicator warmup removed |
| CS04 | Select only on TRAIN2020-2023; VALIDATION2024 never affects selection | Change all validation prices and reproduce identical TRAIN bundle |
| CS05 | Targets mature in elapsed hours, on actual observations and inside business support | Exact t+h lookup; weekend/buffer/boundary masks, no positional shift |
| CS06 | Individual/pairwise/nine filters use existing pinned selector engines | Real engine terminals, local readback and published metric receipts |
| CS07 | Predeclare a filter subset, not a retrospectively chosen trading winner | MRMR k12 union over return4h/return12h/absolute-return12h, then existing TRAIN redundancy clusters; no validation tuning |
| CS08 | Same selected information feeds both SACs | Names/order/data/availability/selection digests bound in both contracts |
| CS09 | Scope and uncertainty remain explicit | full_inventory_complete=false; no causal-identification claim from profiling |

Architecture: financial-data verifies admitted prices and prepares the bundle;
feature-eng's `normalize_phase1b.add_derived_features` supplies22 existing
technical/seasonal transforms; eight admitted RAW-derived columns complete a
30-candidate population. Technical warmup is a leading prefix, never filled.
The existing feature-selector adapter computes individual metrics, pairwise
metrics and nine filter methods. The prospective policy uses the union of the
MRMR k12 sets for the three TRAIN-only targets, followed by one representative
per existing TRAIN Spearman cluster; this is a filter-selected
experimental input, not a proven optimal subset or full causal selection.
No feature is rejected merely because a causal effect is not identified.

Timestamp semantics: admitted bar-start plus1h is decision availability; the
current completed bar is included. Indicators use observed bars, not synthetic
weekend bars. Inputs may span closures. Targets cannot cross a closure or the
12h force-flat/reopen buffers, or a TRAIN/fold boundary. Source-calendar limits
remain those of the admitted conservative operating policy.

Unit design before implementation: hash/membership/schema refusals; finite
numeric output; leading-only warmup; exact horizon lookup; buffer equality;
split-end purge; prefix invariance; validation perturbation; changed output
binding refuses reuse. Integration: real admitted bundle through pinned
engines, then selected columns and saved SAC policies with frozen validation.
System: bounded CPU preparation/selection, sequential5090 fits, durable status,
warehouse readback and two physical copies. Do not modify DOIN or reuse retired
metrics/weights. TEST is excluded from this experiment.

## Execution And Evidence

The actual preparation uses24862 TRAIN rows across48 months and6221 validation
rows across12 months, after33 leading indicator-warmup observations. Exact
real prefix equality holds at512 and4096 rows. Six focused tests pass. This
is admission of the30 reproducible core-derived candidates, not the external
catalogue. The fixed source receipt/closure layout is the bounded interface.

Before a selected input is consumed, `_scripts.attest_core_candidate_transport`
re-runs the same preparation and requires exact equality of the existing
TRAIN/VALIDATION candidate frame, then binds its parquet SHA256, TRAIN bundle
SHA256 and preparation-binding SHA256 in `TRANSPORT_VERIFICATION.json`.
This closes the review finding that the combined transport was not explicitly
bound in the initial preparation proof. Recording an arbitrary new transport
digest is not enough: source and recipe are recomputed first.

```bash
CUDA_VISIBLE_DEVICES='' python -m _scripts.core_selection_bundle \
  --admission-root "$ADMITTED_CORE" --generator-root "$FEATURE_ENG" \
  --output "$PREPARED_BUNDLE"
CUDA_VISIBLE_DEVICES='' python -m _scripts.attest_core_candidate_transport \
  --admission-root "$ADMITTED_CORE" --generator-root "$FEATURE_ENG" \
  --bundle "$PREPARED_BUNDLE"
```

The current filter selection is15 of30, with37198 native OLAP rows, exact
readback, zero pending/mismatched rows and two physical copies. The selection
and original code/source identities live in the owning feature-selector
receipt; no large data or metrics database is committed. No causal-effect
identification or full external-catalogue completion is claimed.
