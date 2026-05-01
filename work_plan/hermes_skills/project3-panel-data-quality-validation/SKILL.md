---
name: project3-panel-data-quality-validation
description: Use when validating Project 3 financial datasets where repeated timestamps can be valid because the file is panel data keyed by symbol, series, venue, accession, security type, or other entity dimensions.
version: 1.0.0
author: Project 3 Codex/Hermes team
license: MIT
metadata:
  hermes:
    tags: [project3, financial-data, validation, panel-data, time-series-quality]
    related_skills: [project3-deliverable-validator, project3-autonomous-supervisor, systematic-debugging]
---

# Project 3 Panel Data Quality Validation

## Trigger

Use this skill when a quality check reports duplicate timestamps, non-monotonic dates, or duplicate-key warnings in a dataset that may contain multiple entities per timestamp.

Examples:

- BEA NIPA tables keyed by `TimePeriod`, `SeriesCode`, and `LineNumber`.
- OECD panel data keyed by `period`, `REF_AREA`, `MEASURE`, and other dimensions.
- SEC filings keyed by `ticker` and `accession_number`.
- FINRA short-volume data keyed by `Date`, `Symbol`, `Market`, and `venue_file`.
- Treasury rates keyed by `record_date`, `security_type_desc`, and `security_desc`.

## Procedure

1. Read the stage work plan and the dataset documentation first.
2. Inspect columns and identify the natural key. Do not assume timestamp alone is unique.
3. Check full-row duplicates separately from duplicate timestamps.
4. For panel data, validate duplicates on `[time_column] + natural_key_columns`, not on the time column alone.
5. Treat exact full-row duplicates as low/medium data anomalies and remove only when the operation is deterministic and provenance is updated.
6. Treat repeated timestamps across different symbols/series/entities as advisory, not a blocker.
7. Write a classification report if the generic checker flags panel structure as suspicious.

## Escalation

Escalate to Tier 4/Codex if:

- the natural key is ambiguous;
- duplicate natural keys remain after deterministic cleanup;
- cleanup would touch more than a small, source-specific set of files;
- a source-specific data dictionary contradicts the assumed key.

## Evidence To Report

- dataset path;
- time column;
- natural key columns;
- full-row duplicate count;
- duplicate natural-key count;
- rows before/after cleanup if any;
- provenance path updated;
- confidence and unverified assumptions.
