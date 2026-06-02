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

As of 2026-05-23, Stage B still has no promotion-ready candidate and Stage C
remains locked. The active path is no longer a static long-horizon model
benchmark. Project 3 is now a **weekly-retrained, data-first portfolio system**:
the system retrains over the weekend, trades only the next week, and learns from
many historical weekly walk-forward anchors.

Active operating documents:

- `00_PROJECT_3_MASTER_PLAN.md` — canonical master plan and current pivot.
- `30_PHASE_3_OVERVIEW.md` — active Phase 3 framing.
- `31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md` — active weekly walk-forward
  experiment contract.
- `32_STAGE_3_2_RESULTS_SYNTHESIS.md` — active weekly/portfolio synthesis
  contract.
- `PROJECT3_WEEKLY_RETRAINED_PORTFOLIO_PROTOCOL_2026_05_22.md` — production
  mechanics: weekend retrain, next-week validation target, cross-asset inputs,
  portfolio supervisor, no-trade/risk overlay.
- `PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md` — SAC-first
  DEAP/NSGA data, preprocessing, and hyperparameter optimization protocol.
- `PROJECT3_STAGE3X_AGENT_SPEC_KIT_2026_05_14.md` — current agent handoff kit.
- `PROJECT3_STAGE3X_PORTFOLIO_ENV_AGENT_SPECS_2026_05_19.md` — portfolio-mode
  mechanical plumbing and evidence contract.
- `PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO.md` — broker/regulatory
  trade-frequency policy reference.
- `PROJECT3_DATA_CONTEXT_AND_PAID_SOURCE_GAP_SPEC_2026_05_13.md` and
  `PROJECT3_CRYPTOQUANT_SUBSCRIPTION_DECISION_2026_05_13.md` — paid/free data
  source context and subscription decisions.

Data inventories, acquisition plans, and Phase 1/2 feature-engineering
documents remain active reference material and were intentionally not archived.

Superseded one-off prompts, already-executed external-agent specs, old SOTA
side memos, and deferred synthetic-data research notes are archived under:

- `archive_superseded_2026_05_14/`
- `archive_superseded_2026_05_23_weekly_data_first/`

Archived files are not active instructions. They are retained only for history
and references.
