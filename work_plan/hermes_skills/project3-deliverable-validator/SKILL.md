---
name: project3-deliverable-validator
description: Use when validating Project 3 work-plan task deliverables against the exact work-plan requirements, produced files, provenance, logs, and validation reports; uncertainty must be escalated instead of guessed.
version: 1.0.0
author: Project 3 Codex/Hermes team
license: MIT
metadata:
  hermes:
    tags: [project3, financial-data, deliverable-validation, escalation, evidence]
    related_skills: [project3-autonomous-supervisor, systematic-debugging, test-driven-development]
---

# Project 3 Deliverable Validator

## Non-Negotiable Rule

Never mark a Project 3 task as complete from memory, assumption, or optimistic inference. Validate against both:

1. the relevant work-plan task spec, usually under `work_plan/`;
2. the produced deliverable files, provenance/docs, logs, and validation output.

If the evidence is incomplete, contradictory, or outside the local model's confidence, escalate to Tier 4/Codex. Do not guess and do not silently downgrade the requirement.

## Required Context

Before validating a task, read or inspect:

- `work_plan/00_PROJECT_3_MASTER_PLAN.md` for standing rules;
- the stage work-plan document that defines the task and deliverable;
- the produced deliverable path(s);
- `_metadata/acquisition_log.csv`;
- relevant `README.md`, `data_dictionary.md`, and `provenance.json`;
- relevant worker logs under `_logs/`;
- `_logs/supervisor_reports/stage13_deliverable_validation.md` when present.

## Validation Contract

For each task, report:

- exact stage and task id;
- work-plan requirement summary;
- deliverable path(s);
- evidence inspected;
- checks performed;
- status: `validated`, `in_progress`, `partial`, `failed`, or `needs_codex`;
- confidence;
- anomaly or gap, if any;
- next action;
- `context_to_pass_forward`.

Use `needs_codex` for questions involving plan interpretation, provider/subscription decisions, ambiguous quality thresholds, or any case where confidence is below 0.8.

## Escalation Rules

Escalate to Tier 4/Codex when:

- the work-plan requirement and produced artifact do not clearly match;
- a provider says data requires a paid tier;
- a required dataset is absent but a worker claims completion;
- generated metrics look plausible but validation evidence is weak;
- the local model would need to assume intent, quality, or sufficiency;
- fixing the issue would change more than two files or alter stage gates.

Escalation must include the exact work-plan doc path, task id, deliverable path, log evidence, confidence, and the precise question Codex should answer on the next status check.

## What Good Looks Like

A validation result is acceptable only when a reviewer can trace it from work-plan requirement to artifact evidence. The supervisor should be strict and honest: a partial but well-documented result is more useful than a confident-looking guess.
