# Phase 1 Overview — Data Acquisition

**Phase goal:** Acquire ALL plausibly relevant data sources for RL trading research, organized into a documented data lake. Acquire defensively but avoid redundancy.

**Phase output:** Complete data lake at `~/Documents/financial_data/` with:
- All raw data acquired
- Per-folder READMEs describing contents
- Per-dataset data dictionaries
- Provenance tracking (source URLs, acquisition dates, licenses)
- Validation reports per dataset
- No redundant data sources (one primary per data type, cross-validation only when justified)

---

<!-- AGENT_INFRA_NOTE_v2 -->
## Agent Infrastructure Note

This stage is executed by the multi-tier agent system defined in `01_AGENT_INFRASTRUCTURE.md` (architecture v2). Read that document before executing this stage. Key rules:

- **Tier 2 (OpenCode Go on Omega) dispatches** the per-machine tasks listed below; you (the user) do not run them by hand.
- **Tier 1 supervisors** (Hermes + Gemma 3 31B on Dragon and Gamma, cron-invoked, GPU-lockfile-aware) watch worker logs and produce status reports.
- **Heavy GPU jobs MUST acquire `/tmp/gpu_busy.lock`** via `_scripts/lib/gpu_lock.py` before starting. See infrastructure doc §4.
- **Auto-validation is full auto** (master plan Rule M.15). When you confirm a manual prerequisite is done, the agents proceed through validation, deliverable generation, and downstream prep automatically. Only blockers ping you.
- **Escalation routing (v2 simplified — no automated frontier API):**
  - Code/data anomalies, scope ≤2 files, severity ≤ high → Tier 3 (local Hermes + Gemma 31B, bounded: max 3 attempts, max 2 files, 30 min/attempt). If Tier 3 confidence <0.7 or attempts exhausted → hands off to Tier 4.
  - Plan decisions, synthesis, final-report writing, blocker severity, or scope >2 files → Tier 4 (you, with ChatGPT 5.5 Pro via Codex / Copilot Opus 4.7 / Claude Pro Max as your tools).
  - **No automated frontier API calls anywhere.** Frontier models are human-driven only.

The "machine assignment" tables below describe which machine runs which workers. The dispatcher (Tier 2) handles SSH, conda activation, and result collection.
---

## Phase 1 Stages

| Stage | Document | Purpose |
|-------|----------|---------|
| 1.1 | `11_STAGE_1.1_STORAGE_ARCHITECTURE.md` | Build folder structure + templates |
| 1.2 | `12_STAGE_1.2_DATA_CATALOG.md` | Document EVERY data source with redundancy analysis |
| 1.3 | `13_STAGE_1.3_FREE_DATA_ACQUISITION.md` | Acquire free sources first |
| 1.4 | `14_STAGE_1.4_REGISTRATIONS_AND_KEYS.md` | User performs manual subscriptions/registrations AFTER 1.3 inventory |
| 1.5 | `15_STAGE_1.5_PAID_DATA_ACQUISITION.md` | Acquire ONLY non-redundant paid sources |
| 1.6 | `16_STAGE_1.6_VALIDATION_AND_DOCUMENTATION.md` | Validate, document, audit |

---

## Stage Dependencies

```
1.1 Storage Architecture (foundation)
    │
    ▼
1.2 Data Catalog (full catalog with redundancy analysis)
    │
    ▼
1.3 Free Data Acquisition (DO FIRST — establishes what we already have)
    │
    ▼
1.3.5 Free data inventory checkpoint (NEW — prevents redundant subscriptions)
    │
    ▼
1.4 Registrations and Keys (only for sources providing data NOT covered by free)
    │
    ▼
1.5 Paid Data Acquisition (only non-redundant paid sources)
    │
    ▼
1.6 Validation and Documentation (final stage)
```

**Critical change vs original ordering:** Stage 1.3 (free) executes BEFORE Stage 1.4 (registrations). This way, after Stage 1.3 we know exactly what data we already have free, and Stage 1.4 only registers for subscriptions providing genuinely additional data.

---

## Phase 1 User Gates

After each stage, agent produces deliverable, halts, awaits user approval:

- After 1.1: User reviews folder structure
- After 1.2: User reviews catalog and approves data acquisition list (subscription decisions deferred)
- After 1.3: User reviews free data acquisition results AND approves subscription list based on what's still missing
- After 1.4: User confirms all registrations complete and credentials provided
- After 1.5: User reviews paid data acquisition results
- After 1.6: User approves Phase 1 complete, Phase 2 may start

---

## Phase 1 Deliverables Summary

By end of Phase 1, the following must exist:

1. Complete data lake at `~/Documents/financial_data/` with all subfolders populated
2. README.md in every folder
3. data_dictionary.md for every dataset folder
4. provenance.json for every dataset folder
5. `PHASE_1_COMPLETION_REPORT.md` documenting:
   - Inventory of all acquired data
   - Total data volume
   - Source breakdown (free vs paid)
   - Total monthly subscription cost
   - Subscriptions evaluated vs accepted (rejection reasons)
   - Any sources that failed to acquire (with reasons)
   - Coverage gaps known
   - Validation summary

---

## Critical Rules for Phase 1

### Rule P1.1: Acquire defensively but not redundantly

When in doubt about a source's value, acquire it. BUT do not acquire same data from multiple sources unless one is for cross-validation purpose with explicit justification.

For FX data specifically: HistData is primary. OANDA / TrueFX / Dukascopy used as cross-validation ONLY if HistData has gaps for specific period. For most pairs and most years, HistData alone is sufficient.

### Rule P1.2: Document at acquisition time

Do NOT defer documentation. As each dataset is acquired, immediately write its README, data_dictionary, and provenance. "Documentation later" means "documentation never."

### Rule P1.3: Validate at acquisition time

Each dataset acquired runs through validation tests (Stage II-0b 6-test battery for time-series price data; appropriate variants for other data types). Failed validation triggers ESCALATION.

### Rule P1.4: Original data preserved

Acquired raw data never modified. If transformations needed (resampling, cleaning), they happen in Phase 2 and produce new files. Raw is sacred.

### Rule P1.5: Source credentials never committed to git

API keys, subscription credentials in `.env` files. All `.env` files in `.gitignore`. Commit credential references, not credential values.

### Rule P1.6: Free data first, paid data after inventory

Stage 1.3 (free) executes BEFORE Stage 1.4 (subscriptions). Subscription decisions wait until we know what's already covered free.

### Rule P1.7: News and sentiment data EXCLUDED

Project 3 does NOT acquire:
- General news headlines (GDELT, NewsAPI, Polygon News)
- Social media sentiment (Twitter, Reddit, StockTwits)
- News article text bodies

Reason: Sentiment analysis on these data is overkill for current project scope. Sentiment-derived features would require: text preprocessing, language model embedding or fine-tuning, sentiment scoring, temporal aggregation. This is a substantial separate project.

Project 3 DOES acquire:
- Economic calendar with scheduled events (CPI release dates, FOMC meetings, NFP, etc.)
- Actual vs estimate vs prior values for economic releases (the numerical surprise data, NOT the news article)
- These provide direct numerical features without text processing

If after Project 3 phases complete, sentiment data appears valuable, it can be added in a future Project 4.

### Rule P1.8: Acknowledge what we are NOT acquiring

Stage 1.2 documents exclusions with reasons. Examples:
- Bloomberg Terminal (cost-prohibitive, alternatives sufficient)
- Real-time tick data archives (not needed for non-HFT research)
- News article text + sentiment (Rule P1.7)
- 1-minute bar data (Rule M.11)
- Daily/weekly bar data as primary simulation (Rule M.11; only for forward-fill)

---

## Approval to Begin Phase 1

User approves Phase 1 overview. Agent reads `11_STAGE_1.1_STORAGE_ARCHITECTURE.md` and begins Stage 1.1.
