# Project 3 Event Token / Transformer Context Agent Spec

Date: 2026-06-17
Status: READY FOR CODING AGENT

## Business Objective

Improve next-week trading performance in the weekly walk-forward pool by giving
the SAC agent a better representation of variable-length market/event context.

The business unit of evaluation remains:

```text
weekly anchor:
  train: historical data before the decision cutoff
  train_tail: final slice of train for early-stop score
  validation: next week
  test: following week, never used for selection
```

Selection remains:

```text
composite = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

Test return is recorded only after selection.

## Current Implemented Bridge

Codex has implemented a safe first bridge:

```text
agent-multi/tools/project3_weekly_materialize.py
context_embedding_profile.family = event_token_attention_v1
```

This bridge:

- fits the encoder only on each subjob training window;
- reads event/context columns selected by prefix, initially `event_`;
- learns train-only token relevance weights from correlation to next-bar
  returns inside the training window;
- writes a derived CSV under the weekly-pool run directory;
- appends `ctx_evt_*` embedding columns to `feature_list`;
- emits `context_embedding_manifest.json` with fit window, source columns,
  scores, means, stds, and generated columns.

This is not the final transformer architecture. It exists to make the
embedding lane executable immediately without leakage.

## Required Coding Agent Work

Implement the heavier train-only event-token encoder as a second profile:

```text
context_embedding_profile.family = event_token_transformer_v1
```

The implementation may live in a new module if cleaner, but must be callable
from `project3_weekly_materialize.py` with the same contract as
`event_token_attention_v1`.

## Data Contract

Input is the original weekly-pool CSV.

Token sources:

- `event_*` columns first;
- later optional source groups: market-state columns, cross-asset columns,
  technical indicators, and calendar distance-to-event columns;
- all selected columns must be known at the row timestamp.

Required generated columns:

```text
ctx_evt_tr_00
ctx_evt_tr_01
...
ctx_evt_tr_{embedding_dim-1}
ctx_evt_tr_attn_mass
ctx_evt_tr_token_count
```

Required manifest fields:

```json
{
  "schema_version": "project3_context_embedding_manifest_v1",
  "family": "event_token_transformer_v1",
  "fit_scope": "train_only",
  "fit_window_start": "...",
  "fit_window_end": "...",
  "source_columns": [],
  "embedding_columns": [],
  "diagnostic_columns": [],
  "training_summary": {},
  "model_config": {}
}
```

## Architecture Guidance

Keep the first transformer small and robust:

- token value normalization fitted on train only;
- token type embedding by source group;
- time/calendar embedding if present;
- 1-2 transformer encoder blocks;
- attention pooling to one fixed vector per row;
- supervised auxiliary target: next-bar or next-window return inside train only;
- optional denoising/reconstruction auxiliary loss;
- export row-level embeddings for train/validation/test using frozen train-fit
  encoder.

Do not train on validation/test targets. Do not fit scalers on validation/test.

## Integration Requirements

The weekly pool must be able to enqueue jobs with:

```json
"context_embedding_profile": {
  "enabled": true,
  "family": "event_token_transformer_v1",
  "source_prefixes": ["event_"],
  "output_prefix": "ctx_evt_tr",
  "embedding_dim": 16,
  "fit_scope": "train_only_per_subjob",
  "required": true
}
```

`project3_weekly_phase_orchestrator.py` should then add a phase after
`event_token_embedding_phase4_v1`:

```text
event_token_transformer_phase_next_v1
```

only after the profile passes tests and a tiny dry-run.

## Tests Required

Add tests proving:

1. The transformer profile refuses to fit with no source columns.
2. Fit metadata reports `fit_scope=train_only`.
3. Validation/test rows are transformed but not used for fitting.
4. Generated embedding columns are added to `feature_list`.
5. Materialized config points to the derived CSV, not the original CSV.
6. Stage C firewall remains unchanged.
7. The phase orchestrator dry-run can generate the transformer phase without
   enqueueing duplicate subjobs.

## Performance Acceptance

The transformer lane is useful only if it beats matched baselines on aggregate
composite. Initial acceptance:

- compare against `event_token_attention_v1`;
- compare against raw `event_engineered_v1`;
- require at least 6 completed weekly anchors before ranking;
- rank by average composite, not by best single test week.

## Do Not Do

- Do not use validation/test labels for encoder fitting.
- Do not use Stage C rows.
- Do not optimize by best test return.
- Do not launch broad GPU jobs before a tiny materialization/training dry-run
  proves the profile works.
