# Project 3 Parametric Data / Preprocessing Search Space

Generated UTC: `2026-05-18T17:00:56.601380+00:00`

- Stage C access: `DENIED`
- Training launched: `False`
- Input datasets discovered: `443`
- Assets: `20`
- Timeframes: `3`
- Feature presets: `10`
- CPU-screening seed genomes: `1728`

## Purpose

This is the active search surface for Project 3. The object being searched is not just a model; it is the full data contract: asset, timeframe, source family, feature selector, preprocessing profile, seasonal context, and later SAC hyperparameters.

## Guardrail

The seed population is CPU-screening only. DEAP/NSGA-II may consume this schema after target-relation screening reduces the feature universe. No Stage C rows and no uncounted GPU trial are allowed.
