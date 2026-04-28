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

- Project 3 master plan: `[path to project root]/docs/00_PROJECT_3_MASTER_PLAN.md`
- Data catalog: `[path to project root]/docs/12_STAGE_1.2_DATA_CATALOG.md`
