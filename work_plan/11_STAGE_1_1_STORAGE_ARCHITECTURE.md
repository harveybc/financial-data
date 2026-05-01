# Stage 1.1 — Storage Architecture

**Stage goal:** Create the complete folder structure for the financial data lake. Set up README templates, data dictionary templates, and provenance.json templates.

**Inputs:** None (this is foundation stage).

**Outputs:**
- Complete empty folder structure at `/home/harveybc/Documents/GitHub/financial-data/`
- Templates in `/home/harveybc/Documents/GitHub/financial-data/_templates/`
- `STAGE_1.1_DELIVERABLE.md` confirming structure created

**Machine:** Omega (local).

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

## 1. Pre-Flight: SSH and Conda Verification

If working on Omega locally, no SSH activation needed (interactive shell, .bashrc already sourced).

If running this stage via SSH from another location, agent verifies conda env active using:

```bash
ssh omega-host "echo \$CONDA_DEFAULT_ENV"
```

If output `tensorflow` → already active (don't re-activate).
If output empty → use `source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && <command>` for each remote command.

This stage is local file creation, mostly via `mkdir`, no Python required, but documenting the pattern for downstream stages.

---

## 2. Folder Structure (CREATE EXACTLY THIS)

Execute these commands in order on Omega:

```bash
cd ~/Documents
mkdir -p financial_data
cd financial_data

# Top-level categories
mkdir -p _templates
mkdir -p _metadata
mkdir -p _scripts
mkdir -p market_data
mkdir -p macro_economic
mkdir -p alternative_data
mkdir -p microstructure
mkdir -p derivatives
mkdir -p fundamental
mkdir -p reference_data
mkdir -p economic_calendar

# Market data subcategories
mkdir -p market_data/equities
mkdir -p market_data/equities/us_indices
mkdir -p market_data/equities/us_individual
mkdir -p market_data/equities/eu_indices
mkdir -p market_data/equities/eu_individual
mkdir -p market_data/equities/asia_indices
mkdir -p market_data/equities/asia_individual
mkdir -p market_data/equities/emerging
mkdir -p market_data/equities/etfs

mkdir -p market_data/forex
mkdir -p market_data/forex/g10
mkdir -p market_data/forex/emerging_markets

mkdir -p market_data/crypto
mkdir -p market_data/crypto/spot_top50
mkdir -p market_data/crypto/perpetuals
mkdir -p market_data/crypto/funding_rates

mkdir -p market_data/commodities
mkdir -p market_data/commodities/precious_metals
mkdir -p market_data/commodities/energy
mkdir -p market_data/commodities/agriculture
mkdir -p market_data/commodities/industrial_metals

mkdir -p market_data/bonds
mkdir -p market_data/bonds/us_treasuries
mkdir -p market_data/bonds/sovereign_global
mkdir -p market_data/bonds/corporate

# Macro economic data
mkdir -p macro_economic/fred
mkdir -p macro_economic/oecd
mkdir -p macro_economic/imf
mkdir -p macro_economic/world_bank
mkdir -p macro_economic/eurostat
mkdir -p macro_economic/boj
mkdir -p macro_economic/ecb
mkdir -p macro_economic/central_banks_other
mkdir -p macro_economic/inflation_expectations
mkdir -p macro_economic/yield_curves

# Economic calendar (NEW separate top-level — replaces news folder)
mkdir -p economic_calendar/scheduled_events
mkdir -p economic_calendar/release_actuals
mkdir -p economic_calendar/release_surprises

# Alternative data (NO news/sentiment subfolders per Rule P1.7)
mkdir -p alternative_data/sec_filings
mkdir -p alternative_data/insider_trading
mkdir -p alternative_data/earnings_estimates
mkdir -p alternative_data/analyst_recommendations
mkdir -p alternative_data/short_interest
mkdir -p alternative_data/etf_flows
mkdir -p alternative_data/cot_reports

# Crypto-specific alternative data
mkdir -p alternative_data/onchain_btc
mkdir -p alternative_data/onchain_eth
mkdir -p alternative_data/onchain_other
mkdir -p alternative_data/exchange_flows
mkdir -p alternative_data/whale_movements
mkdir -p alternative_data/defi_metrics

# Microstructure
mkdir -p microstructure/trade_volume_profile
mkdir -p microstructure/spread_data

# Derivatives
mkdir -p derivatives/options_chains
mkdir -p derivatives/options_greeks
mkdir -p derivatives/futures_curves
mkdir -p derivatives/vix_term_structure
mkdir -p derivatives/implied_volatility_surfaces

# Fundamental
mkdir -p fundamental/earnings
mkdir -p fundamental/balance_sheet
mkdir -p fundamental/income_statement
mkdir -p fundamental/cash_flow
mkdir -p fundamental/ratios

# Reference data
mkdir -p reference_data/calendars
mkdir -p reference_data/holidays
mkdir -p reference_data/index_constituents
mkdir -p reference_data/sector_classifications
mkdir -p reference_data/symbol_mappings
```

**Folders REMOVED from original plan (per TODOs):**
- `alternative_data/news_sentiment/` — Excluded per Rule P1.7 (no news data)
- `alternative_data/social_sentiment/` — Excluded per Rule P1.7
- `alternative_data/google_trends/` — Excluded (sentiment-adjacent)
- `alternative_data/wikipedia_traffic/` — Excluded (sentiment-adjacent)
- `microstructure/order_book_snapshots/` — Excluded (HFT scope, not us)
- `market_data/forex/exotic_pairs/` — Excluded (low priority, focus on G10 + EM)

This creates ~62 folders (down from ~70 in original). Do not create additional folders unless approved.

---

## 3. Templates Directory Contents

Create these template files at `/home/harveybc/Documents/GitHub/financial-data/_templates/`:

### Template 1: README.md template

File: `/home/harveybc/Documents/GitHub/financial-data/_templates/README_template.md`

```markdown
# [Folder Name]

## Purpose

[1-2 sentences: what this folder contains and why it exists]

## Contents

[List of subfolders or files with brief description each]

## Update Frequency

[How often is this data refreshed? e.g., "Daily", "Monthly", "One-time historical pull"]

## Periodicity

[For data folders: at what frequencies is data stored? e.g., "5m, 15m, 1h, 4h", "daily only", "monthly"]

## Last Updated

[YYYY-MM-DD]

## Related Folders

[Links to related folders if applicable]

## Notes

[Any caveats, known issues, version info]
```

### Template 2: data_dictionary.md template

File: `/home/harveybc/Documents/GitHub/financial-data/_templates/data_dictionary_template.md`

```markdown
# Data Dictionary: [Dataset Name]

## Source

- **Provider:** [e.g., FRED, Binance, Polygon.io]
- **URL:** [base URL]
- **License:** [e.g., Public Domain, CC-BY, Proprietary - Subscription]
- **Acquisition method:** [API, bulk download, manual download]

## Coverage

- **Date range:** [YYYY-MM-DD to YYYY-MM-DD]
- **Periodicity:** [5m | 15m | 1h | 4h | daily (forward-fill use only) | monthly | quarterly]
- **Total observations:** [number]
- **Coverage gaps:** [any known gaps in data]

## Use in Project 3

- **As trading asset price (simulation env):** YES/NO. If YES, at what timeframes.
- **As feature input (observation space):** YES/NO. If YES, at what periodicity (forward-fill or aggregate to sim timeframe).

## Schema

| Column | Type | Description | Units | Example | Notes |
|--------|------|-------------|-------|---------|-------|
| timestamp | datetime | UTC timestamp | ISO 8601 | 2024-01-01T00:00:00Z | |
| ... | | | | | |

## Known Issues

- [Any quirks, errors, or anomalies]

## Validation Status

- [ ] Bar count realistic (for time series)
- [ ] Schema matches specification
- [ ] No duplicate timestamps
- [ ] No future timestamps
- [ ] Statistical validation (Stage II-0b 6 tests where applicable)

## Provenance

See `provenance.json` in same folder.
```

### Template 3: provenance.json template

File: `/home/harveybc/Documents/GitHub/financial-data/_templates/provenance_template.json`

```json
{
  "dataset_name": "DATASET_NAME_HERE",
  "source": {
    "provider": "PROVIDER_NAME",
    "url": "https://provider.example.com",
    "api_endpoint": "/v1/endpoint",
    "api_version": "v1"
  },
  "acquisition": {
    "acquired_date": "YYYY-MM-DD",
    "acquired_by": "Project 3 Stage 1.X",
    "acquisition_method": "API|bulk_download|manual",
    "script_used": "scripts/fetch_X.py",
    "script_git_sha": "GIT_HASH_HERE"
  },
  "coverage": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "periodicity": "1h",
    "total_observations": 0
  },
  "use_in_project_3": {
    "as_trading_asset": false,
    "trading_asset_timeframes_supported": [],
    "as_feature_input": false,
    "feature_input_periodicity": null,
    "primary_or_validation": "primary"
  },
  "license": {
    "type": "Public Domain|CC-BY|Proprietary-Subscription|Other",
    "details": "License details if relevant"
  },
  "cost": {
    "type": "free|subscription",
    "monthly_cost_usd": 0,
    "subscription_provider": null
  },
  "redundancy_analysis": {
    "duplicate_of_free_source": false,
    "free_alternative": null,
    "justification_for_acquiring": ""
  },
  "validation": {
    "validated_date": null,
    "tests_passed": [],
    "tests_failed": [],
    "validation_report_path": null
  },
  "checksum": {
    "algorithm": "sha256",
    "value": null
  }
}
```

---

## 4. Top-Level README

Create file: `/home/harveybc/Documents/GitHub/financial-data/README.md`

```markdown
# Financial Data Lake — Project 3

## Purpose

Comprehensive multi-asset, multi-source financial data repository for systematic RL trading research. Built during Project 3 (2026).

## Organization

| Top-level folder | Contents |
|------------------|----------|
| `_templates/` | README, data dictionary, provenance templates |
| `_metadata/` | Project-wide metadata, acquisition logs, audit trails |
| `_scripts/` | Acquisition scripts (not committed to git) |
| `market_data/` | Price + volume data: equities, forex, crypto, commodities, bonds |
| `macro_economic/` | Macroeconomic indicators: rates, inflation, employment, GDP |
| `economic_calendar/` | Scheduled events + release actuals + surprise values (NOT news headlines) |
| `alternative_data/` | On-chain, COT, options flow, insider trading, fundamentals (NO news/sentiment) |
| `microstructure/` | Trade volume profile, spreads (NO order book snapshots) |
| `derivatives/` | Options chains, futures curves, IV surfaces |
| `fundamental/` | Earnings, balance sheets, income statements, ratios |
| `reference_data/` | Calendars, holidays, index constituents, classifications |

## Periodicities Used

This data lake stores price/volume data at the following periodicities ONLY:
- 5m, 15m, 1h, 4h (RL simulation timeframes)
- Daily, monthly, quarterly (forward-fill inputs and economic indicators only)

NO 1m data. NO weekly data.

## Standards

Every data folder MUST contain:
- `README.md` — Folder description (use _templates/README_template.md)
- `data_dictionary.md` — Schema description (if folder contains datasets)
- `provenance.json` — Machine-readable source tracking with redundancy analysis

## Update procedures

Each data folder's README documents its update procedure (one-time historical pull vs ongoing updates).

## See also

- Project 3 master plan: `[path to project root]/docs/00_PROJECT_3_MASTER_PLAN.md`
- Data catalog: `[path to project root]/docs/12_STAGE_1.2_DATA_CATALOG.md`
```

---

## 5. Metadata Files

Create these initial metadata files at `/home/harveybc/Documents/GitHub/financial-data/_metadata/`:

### File 1: `acquisition_log.csv`

```
timestamp,stage,dataset,source,status,notes
```

(Empty CSV with headers. Each acquisition appends one row.)

### File 2: `subscriptions.json`

```json
{
  "active_subscriptions": [],
  "evaluated_but_rejected": [],
  "cancelled_due_to_mediocrity": [],
  "total_monthly_cost_usd": 0,
  "monthly_budget_cap_usd": 500,
  "last_updated": null
}
```

### File 3: `project_3_metadata.json`

```json
{
  "project": "Project 3",
  "project_phase": "Phase 1 - Data Acquisition",
  "current_stage": "1.1 - Storage Architecture",
  "started_date": null,
  "data_lake_root": "/home/harveybc/Documents/GitHub/financial-data",
  "owner": "harveybc",
  "machine_local": "Omega",
  "periodicities_supported": ["5m", "15m", "1h", "4h", "daily", "monthly", "quarterly"],
  "periodicities_used_for_simulation": ["5m", "15m", "1h", "4h"],
  "held_out_boundary": "2025-01-01",
  "in_sample_end": "2024-12-31",
  "held_out_end": "2025-12-31"
}
```

### File 4: `redundancy_analysis.json`

```json
{
  "purpose": "Track potential data redundancy across sources to avoid double-acquisition",
  "redundancy_rules": [
    {
      "data_type": "FX OHLCV",
      "primary_source": "HistData",
      "validation_sources": [],
      "rule": "HistData is sole primary FX source. OANDA/TrueFX/Dukascopy NOT acquired unless HistData has gaps."
    },
    {
      "data_type": "BTC/ETH OHLCV",
      "primary_source": "Binance public",
      "validation_sources": [],
      "rule": "Binance is sole primary crypto source. No paid crypto OHLCV needed."
    },
    {
      "data_type": "Equity OHLCV daily",
      "primary_source": "yfinance",
      "validation_sources": [],
      "rule": "yfinance free for daily. Polygon paid only for intraday (5m, 15m, 1h, 4h)."
    },
    {
      "data_type": "Macro indicators",
      "primary_source": "FRED",
      "validation_sources": [],
      "rule": "FRED comprehensive. OECD/IMF/World Bank only for series not available in FRED."
    },
    {
      "data_type": "BTC on-chain",
      "primary_source": "CoinMetrics Community (free) for basic; Glassnode for advanced",
      "validation_sources": [],
      "rule": "Community for free metrics, Glassnode subscription only for metrics NOT in Community tier."
    },
    {
      "data_type": "Economic calendar",
      "primary_source": "TradingEconomics free / FXStreet",
      "validation_sources": [],
      "rule": "Free sources sufficient. No paid economic calendar."
    }
  ]
}
```

---

## 6. Validation

After creating all folders and templates, agent runs:

```bash
cd /home/harveybc/Documents/GitHub/financial-data
find . -type d | wc -l  # should be ~62 folders
find _templates -type f | wc -l  # should be 3 files
ls -la README.md  # must exist
ls -la _metadata/*.{csv,json}  # all 4 files exist
```

Document outputs in deliverable.

---

## 7. Stage 1.1 Deliverable

File: `STAGE_1.1_DELIVERABLE.md`

Content:

```markdown
# Stage 1.1 Deliverable — Storage Architecture

## Date: YYYY-MM-DD

## Folder Structure

Total folders created: [N]
Tree structure:
[paste output of `tree -L 3 /home/harveybc/Documents/GitHub/financial-data/`]

## Templates Created

- /home/harveybc/Documents/GitHub/financial-data/_templates/README_template.md ✓
- /home/harveybc/Documents/GitHub/financial-data/_templates/data_dictionary_template.md ✓
- /home/harveybc/Documents/GitHub/financial-data/_templates/provenance_template.json ✓

## Metadata Files Created

- /home/harveybc/Documents/GitHub/financial-data/_metadata/acquisition_log.csv ✓
- /home/harveybc/Documents/GitHub/financial-data/_metadata/subscriptions.json ✓
- /home/harveybc/Documents/GitHub/financial-data/_metadata/project_3_metadata.json ✓
- /home/harveybc/Documents/GitHub/financial-data/_metadata/redundancy_analysis.json ✓

## Top-level README

Created at /home/harveybc/Documents/GitHub/financial-data/README.md ✓

## Verification

- [x] All ~62 folders exist
- [x] All 3 templates present
- [x] All 4 metadata files present
- [x] Top-level README exists

## User Gate

Awaiting user approval to proceed to Stage 1.2 (Data Catalog).
```

---

## 8. Agent Infrastructure Bootstrap

In addition to the data lake folders, Stage 1.1 bootstraps the agent infrastructure per `01_AGENT_INFRASTRUCTURE.md` §13. Bootstrap steps:

### 8.1 SSH config

User updates `~/.ssh/config` on Omega with current Dragon and Gamma IPs:

```
Host dragon
    HostName  <DRAGON_IP_HERE>
    User      harveybc
    IdentityFile ~/.ssh/id_ed25519

Host gamma
    HostName  <GAMMA_IP_HERE>
    User      harveybc
    IdentityFile ~/.ssh/id_ed25519
```

Verification (run from Omega):

```bash
ssh dragon "hostname"
ssh gamma "hostname"
```

Both must succeed before continuing. If either fails, halt bootstrap, log to escalation queue tagged `infra:ssh_config`, wait for user.

### 8.2 Hermes + Ollama verification

Hermes is assumed already installed on Dragon and Gamma. Verify:

```bash
ssh dragon "hermes --version && ollama list | grep -i gemma"
ssh gamma  "hermes --version && ollama list | grep -i gemma"
```

If Hermes is missing on either machine, halt bootstrap and escalate to user. (Hermes installation predates Project 3 and is out of scope for this plan.)

If the Gemma model is missing on either machine, the agent attempts:

```bash
ssh dragon "ollama pull gemma4:31b"
ssh gamma  "ollama pull gemma4:31b"
```

This is large (~17 GB per machine for Q4 quantization) but is a one-time operation.

### 8.3 GPU lockfile helper

Copy `_scripts/lib/gpu_lock.py` to all three machines:

```bash
mkdir -p /home/harveybc/Documents/GitHub/financial-data/_scripts/lib
cat > /home/harveybc/Documents/GitHub/financial-data/_scripts/lib/gpu_lock.py << 'PYEOF'
import json, os, atexit
from datetime import datetime, timezone

LOCKFILE = "/tmp/gpu_busy.lock"

def acquire_gpu_lock(command, expected_duration_minutes, stage):
    if os.path.exists(LOCKFILE):
        with open(LOCKFILE) as f:
            existing = json.load(f)
        raise RuntimeError(f"GPU lock held by PID {existing['owner_pid']} ({existing['owner_command']})")
    payload = {
        "owner_pid": os.getpid(),
        "owner_command": command,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "expected_duration_minutes": expected_duration_minutes,
        "stage": stage,
    }
    with open(LOCKFILE, "w") as f:
        json.dump(payload, f)
    atexit.register(release_gpu_lock)

def release_gpu_lock():
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)
PYEOF

# Copy to Dragon and Gamma
scp /home/harveybc/Documents/GitHub/financial-data/_scripts/lib/gpu_lock.py dragon:/home/harveybc/Documents/GitHub/financial-data/_scripts/lib/
scp /home/harveybc/Documents/GitHub/financial-data/_scripts/lib/gpu_lock.py gamma:/home/harveybc/Documents/GitHub/financial-data/_scripts/lib/
```

### 8.4 Cron entries

Cron jobs are version-controlled in `_scripts/cron/`. The bootstrap creates and installs them:

```bash
mkdir -p /home/harveybc/Documents/GitHub/financial-data/_scripts/cron

# Tier 1 supervisor cron template (deployed to Dragon and Gamma)
cat > /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/tier1_supervisor.cron << 'EOF'
# Project 3 Tier 1 supervisor — phase-dependent cadence
# Phase 1 (acquisition): every 5 min. Update for Phase 2 (15 min) and Phase 3 (30 min).
*/5 * * * * harveybc /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/run_tier1_supervisor.sh
EOF

cat > /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/run_tier1_supervisor.sh << 'EOF'
#!/usr/bin/env bash
# Tier 1 supervisor wrapper. Checks GPU lock before invoking Hermes.
set -e
LOCKFILE=/tmp/gpu_busy.lock
LOG_DIR=/home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports
mkdir -p "$LOG_DIR"
MACHINE=$(hostname)

if [ -f "$LOCKFILE" ]; then
    # GPU is busy — log skip and exit
    echo "{\"machine\": \"$MACHINE\", \"timestamp\": \"$(date -u -Iseconds)\", \"status\": \"skipped_gpu_busy\"}" \
        >> "$LOG_DIR/${MACHINE}_supervisor_ticks.jsonl"
    exit 0
fi

# Acquire lock and run Hermes
python3 -c "from gpu_lock import acquire_gpu_lock; acquire_gpu_lock('hermes_supervisor', 5, 'tier1')" || exit 1
hermes --skill watch_logs --output "$LOG_DIR/${MACHINE}_status.json"
EOF
chmod +x /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/run_tier1_supervisor.sh

# Tier 2 orchestrator cron (Omega only)
cat > /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/tier2_orchestrator.cron << 'EOF'
# Project 3 Tier 2 meta-supervisor (OpenCode Go) — every 12 min
*/12 * * * * harveybc /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/run_tier2_orchestrator.sh
EOF

cat > /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/run_tier2_orchestrator.sh << 'EOF'
#!/usr/bin/env bash
set -e
cd /home/harveybc/Documents/GitHub/financial-data
opencode-go run --skill orchestrate \
    --inputs _logs/supervisor_reports/dragon_status.json,_logs/supervisor_reports/gamma_status.json \
    --output _logs/supervisor_reports/global_status.md \
    --queue _logs/supervisor_reports/escalation_queue.json
EOF
chmod +x /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/run_tier2_orchestrator.sh
```

(The `hermes --skill watch_logs` and `opencode-go run --skill orchestrate` invocations assume the user has the appropriate skills configured in their Hermes / OpenCode Go installations. If the skill names differ in the user's setup, adjust accordingly.)

Install cron entries:

```bash
# On Omega
sudo cp /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/tier2_orchestrator.cron /etc/cron.d/project3_orchestrator
# On Dragon and Gamma
ssh dragon "sudo cp /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/tier1_supervisor.cron /etc/cron.d/project3_supervisor"
ssh gamma  "sudo cp /home/harveybc/Documents/GitHub/financial-data/_scripts/cron/tier1_supervisor.cron /etc/cron.d/project3_supervisor"
```

### 8.5 Initialize escalation queue and supervisor report folder

```bash
mkdir -p /home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports
echo '{"queue": []}' > /home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports/escalation_queue.json
echo '# Global Status (initialized — Tier 2 will overwrite)' > /home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports/global_status.md
```

### 8.6 Tier 4 handoff folder

Tier 3 stages structured handoff documents here when an escalation needs the human:

```bash
mkdir -p /home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports/tier4_handoffs
cat > /home/harveybc/Documents/GitHub/financial-data/_logs/supervisor_reports/tier4_handoffs/README.md << 'EOF'
# Tier 4 Handoffs

When local Tier 3 (Hermes + Gemma 31B) cannot resolve an escalation within its
ceilings (3 attempts, 2 files per attempt, 30 min wall-clock), it stages a
structured handoff document here for the user to review.

Each handoff has filename: `<escalation_id>.md` (e.g., `esc-2026-04-30-001.md`)

Contents per handoff:
- The escalation summary
- What Tier 3 tried (each attempt with confidence score and unverified assumptions)
- Why Tier 3 gave up
- Relevant code paths and log excerpts
- A clear question for the human

User workflow: read handoff → paste relevant context into ChatGPT 5.5 Pro
(via Codex) or Copilot Opus 4.7 → review the response → apply fix → update
escalation queue entry to `resolved`.
EOF
```

### 8.7 .gitignore for credentials and private docs

Create `/home/harveybc/Documents/GitHub/financial-data/.gitignore` with the security-critical patterns:

```bash
cat > /home/harveybc/Documents/GitHub/financial-data/.gitignore << 'EOF'
# Credentials and secrets — NEVER commit
_metadata/.env
_metadata/credential_validation.json
_metadata/ai_subscriptions.json
*.env
.env

# Private companion docs containing actual key values
STAGE_1_3_API_KEYS_PRIVATE.md
*_PRIVATE.md

# Tier 4 handoff docs (may contain log excerpts with sensitive paths)
_logs/supervisor_reports/tier4_handoffs/*.md
!_logs/supervisor_reports/tier4_handoffs/README.md

# Large data files (optional - depends on whether user wants to commit data lake)
*.parquet
*.csv

# Python and OS noise
__pycache__/
*.pyc
.DS_Store
EOF
```

Verification:

```bash
# Confirm critical entries present
grep -E '^_metadata/\.env$|^\*\.env$|^STAGE_1_3_API_KEYS_PRIVATE\.md$' \
  /home/harveybc/Documents/GitHub/financial-data/.gitignore
```

If the grep does not return all three lines, halt bootstrap and escalate `infra:gitignore_misconfigured` (blocker severity).

### 8.8 Credentials .env file (data-source API keys, NOT AI keys)

This `.env` holds your free-tier data API keys. There are NO AI API keys here in v2 — the v2 architecture has no automated frontier API access. If `_metadata/.env` already exists from your earlier Stage 1.3 prep, this step verifies its contents; otherwise create it.

```bash
# Create or update _metadata/.env with data-source API keys
cat > /home/harveybc/Documents/GitHub/financial-data/_metadata/.env << 'EOF'
# Project 3 data-source credentials — DO NOT COMMIT
# Auto-loaded by all acquisition scripts via python-dotenv

# Free APIs (already registered, see STAGE_1.3_MANUAL_TASKS_FOR_USER.md)
export FRED_API_KEY="<filled-from-stage-1.3>"
export ETHERSCAN_API_KEY="<filled-from-stage-1.3>"
export COINMARKETCAP_API_KEY="<filled-from-stage-1.3>"  # optional
export ALPHA_VANTAGE_API_KEY="<filled-from-stage-1.3>"  # optional

# Paid subscriptions (filled later at Stage 1.4 if approved)
export GLASSNODE_API_KEY=""
export CRYPTOQUANT_API_KEY=""
export POLYGON_API_KEY=""
export FMP_API_KEY=""
EOF
chmod 600 /home/harveybc/Documents/GitHub/financial-data/_metadata/.env
```

Actual key values for the free APIs are pasted in by the user (not stored in version-controlled docs). The companion document `STAGE_1.3_API_KEYS_PRIVATE.md` (NOT version controlled) holds the actual values for personal reference; see Stage 1.3 manual tasks for the secure pattern.

### 8.9 AI subscription tracker

```bash
cat > /home/harveybc/Documents/GitHub/financial-data/_metadata/ai_subscriptions.json << 'EOF'
{
  "active": [
    {
      "service": "ChatGPT Pro Plus",
      "purpose": "Tier 4 human tool: Codex in VS Code with GPT-5.5 Pro",
      "monthly_cost_usd": 200,
      "billing_type": "flat_subscription",
      "notes": "Used by user manually on Tier 3 handoffs and plan decisions"
    },
    {
      "service": "VS Code Copilot Opus 4.7",
      "purpose": "Tier 4 alternative / second opinion",
      "monthly_cost_usd": null,
      "billing_type": "quota_based_15x",
      "notes": "Existing subscription, depletes fast — use sparingly"
    },
    {
      "service": "OpenCode Go",
      "purpose": "Tier 2 orchestrator on Omega",
      "monthly_cost_usd": null,
      "billing_type": "subscription_or_per_call",
      "notes": "Capped to one invocation per 12 min cron tick"
    }
  ],
  "explicitly_not_used": [
    "OpenAI API (avoid metered token billing in agent loops)",
    "Anthropic API (same reason)"
  ],
  "billing_model": "predictable subscriptions only — no metered API",
  "last_updated": null
}
EOF
```

### 8.10 Bootstrap verification

If any of steps 8.1–8.9 fail, the bootstrap halts with a clear error and an escalation queue entry tagged `infra:bootstrap_failed`. No data acquisition begins until bootstrap is fully green.

---

## 9. User Gate

User reviews deliverable, confirms folder structure AND agent infrastructure bootstrap, approves Stage 1.2 start.
