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

Already provided in Project 2: [REDACTED_COMPROMISED_KEY]

Verify still valid by:
- Visiting https://fred.stlouisfed.org/docs/api/api_key.html
- Confirming key still listed in your account

Reply: "FRED key still valid: yes/no [if regenerated, new key]"

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

Reply each item as completed. Agent stores all in /home/harveybc/Documents/financial_data/_metadata/.env (NOT committed to git).
```

---

## 3. Credential Storage

Agent creates `~/Documents/financial_data/_metadata/.env`:

```bash
# Project 3 credentials — DO NOT COMMIT
# Auto-loaded by all acquisition scripts via python-dotenv

# Free APIs
export FRED_API_KEY="[REDACTED_COMPROMISED_KEY]"
export ETHERSCAN_API_KEY=""
export COINMARKETCAP_API_KEY=""  # optional

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

`.gitignore` includes `.env` at top of `~/Documents/financial_data/.gitignore`.

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

Per credential, agent records to `~/Documents/financial_data/_metadata/credential_validation.json`:

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

Update `~/Documents/financial_data/_metadata/subscriptions.json`:

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

All credentials stored at: `/home/harveybc/Documents/financial_data/_metadata/.env`
Permissions: 600
Listed in .gitignore: YES

## User Gate

When all approved credentials received and validated, user approves Stage 1.5 (Paid Data Acquisition).
```

---

## 8. User Gate

User confirms credentials provided OR explicitly opts out of any. Agent confirms validation. User approves Stage 1.5.
