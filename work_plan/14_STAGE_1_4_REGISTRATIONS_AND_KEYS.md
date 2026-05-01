# Stage 1.4 — Registrations and Keys

**Stage goal:** User performs manual subscription registrations and provides API keys / credentials for the SUBSET approved at Stage 1.3 user gate (informed by inventory).

**Inputs:** Stage 1.3 complete with `STAGE_1.3_INVENTORY.md` reviewed by user. User has selected specific subscriptions to acquire.

**Outputs:**
- All approved subscriptions active
- All API keys provided to agent via secure mechanism
- All credentials validated working
- `STAGE_1.4_DELIVERABLE.md` confirming readiness for Stage 1.5

**Machine:** None for user tasks. Omega for credential validation.

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

## 1. Stage 1.4 Procedure

This stage is mostly USER MANUAL WORK. Agent's job:
1. Generate REQUEST_USER document for ONLY the user-approved subscriptions and free key registrations
2. Wait for user to complete and provide credentials
3. Validate each credential works
4. Document credential storage in `.env` file
5. Confirm Stage 1.5 can begin

**Key change from original plan:** Agent only requests subscriptions that user approved at Stage 1.3 gate. Does NOT push for all subscriptions in catalog.

---

## 2. REQUEST_USER document (dynamic, based on user's Stage 1.3 decisions)

Agent produces `REQUEST_USER_subscriptions_and_keys.md` containing ONLY the items user approved.

Template:

```markdown
# REQUEST_USER: Subscriptions and API Keys for Project 3

User approved at Stage 1.3 gate the following subscriptions:
[list user-approved subscriptions]

Plus these free API key registrations are needed:
[list free keys needed for Stage 1.3 tasks like Etherscan]

Reply to chat with credentials as each is completed.

---

## A. [If user approved Glassnode] Glassnode Standard Subscription ($30/mo)

1. Visit https://glassnode.com/pricing
2. Subscribe to Standard tier
3. Generate API key in account settings
4. Reply: "Glassnode key: <key>"

## B. [If user approved CryptoQuant] CryptoQuant Standard Subscription ($39/mo)

1. Visit https://cryptoquant.com/products/data
2. Subscribe to Standard
3. Generate API key
4. Reply: "CryptoQuant key: <key>"

## C. [If user approved Polygon] Polygon.io Developer ($79/mo)

1. Visit https://polygon.io/pricing
2. Subscribe to Developer tier
3. Get API key from dashboard
4. Reply: "Polygon key: <key>"

## D. [If user approved FMP] FMP Starter ($14/mo)

1. Visit https://site.financialmodelingprep.com/developer/docs
2. Subscribe to Starter
3. Get API key
4. Reply: "FMP key: <key>"

---

## Free registrations (always required):

## E. Etherscan API key (free)

1. Visit https://etherscan.io/myapikey
2. Register account (free), generate free API key (5 calls/sec)
3. Reply: "Etherscan key: <key>"

## F. CoinMarketCap (free tier, optional)

1. Visit https://pro.coinmarketcap.com/account
2. Free tier: 333 calls/day
3. Reply: "CoinMarketCap key: <key>" (or "skip CMC")

---

## Already have (verify):

## G. FRED API key

The FRED API key from Project 2 has already been verified valid at Stage 1.3 (see `STAGE_1_3_MANUAL_TASKS_FOR_USER.md` task M2). The actual value is stored in `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` as `FRED_API_KEY`, with a personal-reference copy in `STAGE_1_3_API_KEYS_PRIVATE.md` (gitignored).

If a regeneration is ever needed:
- Visit https://fred.stlouisfed.org/docs/api/api_key.html
- Generate new key
- Update `_metadata/.env` and `STAGE_1_3_API_KEYS_PRIVATE.md`

---

## Subscriptions DEFERRED (user opted not to acquire at Stage 1.3 gate):

[list any subscriptions user explicitly skipped]

These can be added later if Phase 3 experiments demonstrate value.

---

## Subscriptions REJECTED upfront (Project 3 standing exclusions):

- Twitter/X API (sentiment data excluded per Rule P1.7)
- NewsAPI / Polygon News (news data excluded per Rule P1.7)
- Bloomberg Terminal / Refinitiv (cost prohibitive)

## Status: WAITING

Reply each item as completed. Agent stores all in /home/harveybc/Documents/GitHub/financial-data/_metadata/.env (NOT committed to git).
```

---

## 3. Credential Storage

Agent creates `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env` (template — values come from `STAGE_1_3_API_KEYS_PRIVATE.md` and any newly approved paid subscriptions):

```bash
# Project 3 credentials — DO NOT COMMIT
# Auto-loaded by all acquisition scripts via python-dotenv

# Free APIs (populated from Stage 1.3 — see STAGE_1_3_API_KEYS_PRIVATE.md)
export FRED_API_KEY="<from-stage-1.3>"
export ETHERSCAN_API_KEY="<from-stage-1.3>"
export COINMARKETCAP_API_KEY="<from-stage-1.3>"  # optional
export ALPHA_VANTAGE_API_KEY="<from-stage-1.3>"  # optional

# User-approved paid subscriptions (only filled if approved at 1.3 gate)
export GLASSNODE_API_KEY=""
export CRYPTOQUANT_API_KEY=""
export POLYGON_API_KEY=""
export FMP_API_KEY=""

# Excluded (per Rule P1.7) — these stay empty:
# TWITTER_BEARER_TOKEN  -- not used
# NEWS_API_KEY          -- not used
```

`.env` permissions: `chmod 600`

`.gitignore` includes `.env` at top of `/home/harveybc/Documents/GitHub/financial-data/.gitignore`.

---

## 4. Credential Validation Procedures

After user provides each credential, agent validates by making a test API call.

For each credential, agent runs validation script. Examples:

**Glassnode:**

```python
import requests, os
key = os.environ['GLASSNODE_API_KEY']
r = requests.get("https://api.glassnode.com/v1/metrics/market/price_usd_close",
                 params={"a": "BTC", "api_key": key, "i": "24h", "s": 1577836800})
assert r.status_code == 200
```

**CryptoQuant, Polygon, FMP, Etherscan, FRED:** similar simple test calls per their API docs.

---

## 5. Validation Results Documentation

Per credential, agent records to `/home/harveybc/Documents/GitHub/financial-data/_metadata/credential_validation.json`:

```json
{
  "service": "Glassnode",
  "credential_type": "API key",
  "validation_date": "YYYY-MM-DD",
  "test_call": "GET /v1/metrics/market/price_usd_close",
  "result": "PASS",
  "tier_confirmed": "Standard",
  "notes": ""
}
```

---

## 6. Subscription Tracking

Update `/home/harveybc/Documents/GitHub/financial-data/_metadata/subscriptions.json`:

```json
{
  "active_subscriptions": [
    {
      "service": "Glassnode",
      "tier": "Standard",
      "monthly_cost_usd": 30,
      "started_date": "2026-04-22",
      "billing_cycle": "monthly",
      "auto_renew": true,
      "purpose": "Crypto on-chain advanced metrics",
      "credentials_path": "_metadata/.env"
    }
  ],
  "evaluated_but_rejected": [
    {
      "service": "Polygon.io Developer",
      "evaluated_date": "2026-04-22",
      "reason_rejected": "User decided no equity intraday experiments planned"
    }
  ],
  "cancelled_due_to_mediocrity": [],
  "total_monthly_cost_usd": 30,
  "monthly_budget_cap_usd": 500,
  "budget_remaining_usd": 470,
  "last_updated": "2026-04-22"
}
```

---

## 7. Stage 1.4 Deliverable

`STAGE_1.4_DELIVERABLE.md`:

```markdown
# Stage 1.4 Deliverable — Registrations and Keys

## User-approved subscriptions

[List from Stage 1.3 user gate]

## Per-credential status

| Service | Type | Approved | Received | Validated | Notes |
|---------|------|----------|----------|-----------|-------|
| FRED | Free API | Always | YES (existing) | PASS | |
| Etherscan | Free | Always | YES/PENDING | PASS/FAIL | |
| Glassnode | Paid | YES/NO | YES/NO/N/A | PASS/FAIL | |
| CryptoQuant | Paid | YES/NO | YES/NO/N/A | PASS/FAIL | |
| Polygon | Paid | YES/NO | YES/NO/N/A | PASS/FAIL | |
| FMP | Paid | YES/NO | YES/NO/N/A | PASS/FAIL | |

## Total monthly subscription cost

$[X]/month (out of $500/month cap)

## Storage

All credentials stored at: `/home/harveybc/Documents/GitHub/financial-data/_metadata/.env`
Permissions: 600
Listed in .gitignore: YES

## User Gate

When all approved credentials received and validated, user approves Stage 1.5 (Paid Data Acquisition).
```

---

## 8. User Gate

User confirms credentials provided OR explicitly opts out of any. Agent confirms validation. User approves Stage 1.5.
