# Financial Data Lake — Project 3

## Purpose

Comprehensive multi-asset, multi-source financial data repository for systematic RL trading research. Built during Project 3 (2026).

## Organization

| Top-level folder | Contents |
|------------------|----------|
| `_templates/` | README, data dictionary, provenance templates |
| `_metadata/` | Project-wide metadata, acquisition logs, audit trails |
| `market_data/` | Price + volume data: equities, forex, crypto, commodities, bonds |
| `macro_economic/` | Macroeconomic indicators: rates, inflation, employment, GDP |
| `alternative_data/` | News, sentiment, on-chain, COT, options flow, etc. |
| `microstructure/` | Order book, trade volume profile, spreads |
| `derivatives/` | Options chains, futures curves, IV surfaces |
| `fundamental/` | Earnings, balance sheets, income statements, ratios |
| `reference_data/` | Calendars, holidays, index constituents, classifications |

## Standards

Every data folder MUST contain:
- `README.md` — Folder description (use _templates/README_template.md)
- `data_dictionary.md` — Schema description (if folder contains datasets)
- `provenance.json` — Machine-readable source tracking

## Update procedures

Each data folder's README documents its update procedure (one-time historical pull vs ongoing daily/weekly update).

## See also

- Project 3 master plan: `work_plan/00_PROJECT_3_MASTER_PLAN.md`
- Data catalog: `work_plan/12_STAGE_1_2_DATA_CATALOG.md`

## Current Active Project 3 Path

As of 2026-06-04, the active path is a **weekly-retrained walk-forward pool**.
The previous short-window short-window smoke/optimization artifacts were
deleted because they used insufficient training windows and are not valid
profit/risk evidence.

Active operating documents:

- `00_PROJECT_3_MASTER_PLAN.md` — canonical master plan.
- `30_PHASE_3_OVERVIEW.md` — active Phase 3 framing.
- `31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md` — weekly walk-forward experiment
  framework.
- `32_STAGE_3_2_RESULTS_SYNTHESIS.md` — weekly/portfolio synthesis contract.
- `PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md` — canonical
  protocol for weekend retrain, `train_years=1..10`, 7-day validation,
  7-day test, SQLite job pool, AdminLTE dashboard, and OLAP-style aggregation.
- `PROJECT3_WEEKLY_WALKFORWARD_POOL_AGENT_SPECS_2026_06_04.md` — copy-ready
  implementation specs for the coding agents.
- `project3_orchestrator_event_context_representation_addendum_2026_06_09.md`
  — active event/calendar/news context lane. Event context is tested as a
  candidate input family in the weekly pool, starting with point-in-time
  engineered features and matched baselines.
- `PROJECT3_RESEARCH_AGENT_PRAGMATIC_CONTEXT_2026_06_09.md` — context packet
  for external research agents so recommendations fit the weekly retrained
  business loop instead of static academic benchmarks.
- `PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md` — broker/regulatory
  trade-frequency policy reference.
- `PROJECT3_DATA_CONTEXT_AND_PAID_SOURCE_GAP_SPEC_2026_05_13.md` and
  `PROJECT3_CRYPTOQUANT_SUBSCRIPTION_DECISION_2026_05_13.md` — paid/free data
  source context and subscription decisions.

Data inventories, acquisition plans, and Phase 1/2 feature-engineering
documents remain active reference material. One-off prompts, executed reviews,
and obsolete short-window Stage 3X plans are not active instructions.
