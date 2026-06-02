# Unsupervised And Causal Audit Design

This design governs the Phase 3X unsupervised/causal lane. The lane is additive, narrow, and evidence-oriented. It does not replace fixed PPO/SAC/DQN experiments.

## Scope

Initial target:

- asset: `ETHUSDT`
- timeframe: `4h`
- algorithm: `SAC`
- feature family: `tech_stat`

Approved P0 artifact families:

- train-only regime features;
- train-only OOD/anomaly scores;
- train-only feature redundancy/stability reports;
- lag-only causal/leakage audit reports.

## Split Rules

- Training fit window: candidate-specific and strictly before validation.
- Validation window: transform/score only.
- Stage C heldout: rows at or after `2025-01-01T00:00:00Z`; forbidden before final locked evaluation.

Any artifact with unknown split provenance is invalid for RL consumption.

## Artifact Rules

Every artifact must record:

- input paths and hashes;
- fit window;
- transform/scoring window;
- heldout boundary;
- model/scaler class;
- config hash;
- code commit;
- seed;
- generated output paths;
- `uses_heldout=false`.

## Variant Rules

The following operations require a new registered paired RL variant:

- adding regime probabilities;
- adding OOD scores;
- applying an OOD exposure overlay;
- reducing feature columns via clustering;
- applying a causal/invariant feature mask;
- adding self-supervised embeddings.

Synthetic, stress, causal, or OOD-only metrics are diagnostics. Real validation is the judge.

## Kill Rules

Kill or quarantine an artifact if:

- any train-fitted object consumed validation or Stage C rows;
- current-bar availability is not provable;
- a threshold or mask was selected after validation/Stage C inspection;
- metadata is incomplete;
- output timestamps are non-monotonic, duplicated, or misaligned;
- the artifact cannot be reproduced from its config hash and input hashes.

## First Acceptance Test

For `ETHUSDT 4h + tech_stat`, produce one train-only regime artifact and one OOD artifact that:

- pass split guard tests;
- include complete metadata;
- can be left-joined to the candidate feature table by timestamp;
- introduce no post-`2025-01-01` rows;
- produce a registered paired variant config without changing PPO/SAC/DQN hyperparameters.
