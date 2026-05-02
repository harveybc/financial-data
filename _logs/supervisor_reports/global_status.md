# Project 3 Global Status

Updated: 2026-05-02T07:20:22.672521+00:00

## Current Stage

Phase 2 is active. Stage 2.1, 2.2, and 2.3 generation are complete. Stage 2.4 input preparation has completed for the first Stage A assets.

## Machine Status

- Omega: OpenCode Go / `deepseek-v4-pro`; completed Stage 2.3 FX decomposition and is coordinating manifests/docs.
- Dragon: Hermes worker / `deepseek-v4-flash:cloud`; completed Stage 2.3 crypto decomposition and Stage 2.4 crypto learned-input prep.
- Gamma: Hermes worker / `deepseek-v4-flash:cloud`; completed Stage 2.2 cross-source statistics and Stage 2.4 FX learned-input prep.

## Deliverables

- Stage 2.2: trading jobs 200/200 ok; cross-source 1464/1480 ok; skipped nonnumeric 16; actionable failures 0.
- Stage 2.3: signal decomposition jobs 200/200 ok.
- Stage 2.4 input prep: 10/10 jobs ok; training wrapper setup next.

## Blockers

- No user-side blocker right now.
- Technical setup item: `feature-extractor` must be invoked with explicit `PYTHONPATH=/home/harveybc/Documents/GitHub/feature-extractor:/home/harveybc/Documents/GitHub/feature-extractor/app` because the generic `feature_extractor` console command is currently colliding with another installed CLI.
