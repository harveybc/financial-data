# Project 3 Regulatory / Broker-Constraint Memo

## FINRA PDT Replacement, OANDA U.S. Constraints, and Project 3 Trade-Frequency Policy

**Prepared for:** Project 3 Orchestrator Agent  
**Role:** external regulatory/research reviewer  
**Scope:** research and project policy guidance only  
**Date:** 2026-05-15  
**Stage C policy:** Stage C remains locked. Nothing in this memo authorizes Stage C tuning, Stage C inspection, or repeated held-out evaluation.

---

## 0. Executive Decision

The FINRA/SEC Pattern Day Trader replacement does **not** justify increasing Project 3 trade frequency.

The PDT replacement is relevant to **U.S. securities margin accounts**, mainly U.S. equities and listed options held in margin accounts. It does **not** apply to OANDA U.S. spot FX, OANDA U.S. spot crypto, general retail forex, or spot crypto trading through Paxos/OANDA.

For Project 3, the binding practical problem is not PDT. The binding problem is:

```text
spread
slippage
rollover / financing
margin closeout risk
broker execution constraints
FIFO / no-hedging constraints
shorting constraints
high crypto spot fee drag
daily and weekly market closures
pathological RL trade behavior
```

The attached Project 3 reports already show that trade behavior is a live problem:

```text
Stage B Trade Behavior Report:
  rows: 1310
  no-trade flags: 635
  excessive-trade hard flags: 190
  always-in-market losing flags: 4
```

Project 3 should therefore **not** loosen overtrading gates because PDT is changing. It should implement broker-profile-aware trade-frequency limits and execution constraints.

Recommended policy:

```text
FX 4h:
  primary target: 3 trades/week
  secondary acceptable band: 3–6 trades/week
  hard research max: 12 trades/week

FX 1h:
  primary target: 6 trades/week
  secondary acceptable band: 6–12 trades/week
  hard research max: 24 trades/week

OANDA spot crypto 4h:
  primary target: 1–3 trades/week
  secondary acceptable band: 3–6 trades/week
  hard research max: 12 trades/week

OANDA spot crypto 1h:
  primary target: 3–6 trades/week
  secondary acceptable band: 6–12 trades/week
  hard research max: 24 trades/week
```

The bands `3`, `6`, `12`, and `24` trades/week should be treated as **Project 3 risk-control objective bands**, not legal thresholds.

---

## 1. FINRA / SEC Pattern Day Trader Replacement

### 1.1 What the SEC Approved

On **April 14, 2026**, the SEC approved FINRA rule filing **SR-FINRA-2025-017**, as modified by Amendment No. 1.

The approved rule change amends FINRA Rule 4210 by replacing the older day-trading margin provisions with new intraday margin standards.

The rule change eliminates provisions related to:

```text
pattern day trader designation;
day-trading buying power;
the $25,000 minimum equity requirement for pattern day traders;
trade-count-based PDT classification.
```

It replaces those provisions with a risk-based intraday margin framework.

Primary sources:

- SEC approval order: https://www.sec.gov/files/rules/sro/finra/2026/34-105226.pdf
- Federal Register notice: https://www.federalregister.gov/documents/2026/04/17/2026-07485/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of
- FINRA Regulatory Notice 26-10: https://www.finra.org/rules-guidance/notices/26-10

### 1.2 Effective Date and Broker Transition Period

FINRA states that the effective date is:

```text
2026-06-04
```

FINRA also states that firms needing more time may phase in implementation over an **18-month transition period**, ending:

```text
2027-10-20
```

During the transition period, a broker may continue using the old PDT/day-trading margin requirements or migrate earlier to the new intraday margin framework.

Project 3 implication:

```yaml
broker_profile.pdt_model:
  old_pdt_until_broker_confirms_new_intraday_margin: true
  new_intraday_margin_after_broker_confirms_migration: true
```

Do not assume that all brokers migrate on the same day.

Primary sources:

- FINRA Regulatory Notice 26-10: https://www.finra.org/rules-guidance/notices/26-10
- Investor.gov PDT page: https://www.investor.gov/introduction-investing/investing-basics/glossary/pattern-day-trader

### 1.3 What Is Eliminated

The approved change eliminates the old PDT framework components:

```text
1. the pattern day trader designation based on day-trade counting;
2. the old four-or-more-day-trades-in-five-business-days PDT logic;
3. the old day-trading buying-power construct;
4. the $25,000 PDT minimum equity requirement;
5. associated FINRA Rule 4210 provisions tied to day-trading margin requirements.
```

### 1.4 What Replaces PDT

The replacement is a risk-based **intraday margin** framework.

Instead of classifying accounts based on trade count, firms must monitor whether accounts maintain sufficient equity relative to intraday positions. FINRA gives member firms flexibility to implement monitoring through:

```text
real-time checks;
pre-trade blocking;
end-of-day computation;
hybrid approaches.
```

If customers repeatedly fail to satisfy intraday margin deficits, firms may restrict the account for up to **90 days**.

Primary source:

- FINRA intraday margin explainer: https://www.finra.org/investors/insights/intraday-margin-requirements

### 1.5 What Still Constrains Traders After the Change

The PDT label changes, but risk constraints remain.

After broker migration, traders are still constrained by:

```text
initial margin requirements;
maintenance margin requirements;
house margin requirements;
intraday margin deficits;
broker pre-trade risk controls;
broker liquidation / restriction policies;
the $2,000 minimum equity required to use margin;
options-specific margin requirements;
cash-account settlement and free-riding constraints.
```

FINRA states that the $2,000 minimum equity requirement remains for leveraged margin trading, and broker-dealers may impose higher house requirements.

Project 3 conclusion:

```text
The PDT replacement removes one old trade-count rule.
It does not make high-frequency trading economically or operationally safe.
It does not apply to OANDA FX or OANDA spot crypto.
It does not reduce the need for cost, slippage, margin, and trade-behavior gates.
```

---

## 2. Applicability by Market Type

| Market / Account Type | PDT Replacement Applies? | Practical Meaning for Project 3 |
|---|---:|---|
| U.S. equity margin accounts | Yes | Old PDT count/$25k framework replaced after broker migration by intraday margin. |
| U.S. listed options margin accounts | Yes | Applies to securities margin accounts, including listed options margin activity. |
| U.S. cash securities accounts | Not as PDT margin classification | Cash accounts remain constrained by settled cash and free-riding rules. |
| Spot FX / retail forex | No | Retail FX is not FINRA securities-margin PDT. It is governed by CFTC/NFA and broker rules. |
| Crypto spot generally | No | PDT is not the governing framework for spot crypto. |
| OANDA U.S. forex | No | Governed by OANDA, CFTC/NFA, FIFO/no-hedging, margin, and market-hours constraints. |
| OANDA U.S. spot crypto | No | OANDA spot crypto is via Paxos; no leverage, no short selling, platform-specific fees and limits. |

Primary sources:

- FINRA Rule 4210: https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210
- NFA Compliance Rule 2-43: https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=RULE+2-43&Section=4
- OANDA U.S. regulatory disclosures: https://www.oanda.com/us-en/legal/regulatory-public-disclosures/
- OANDA account types and leverage: https://help.oanda.com/us/en/faqs/account-types-and-leverage-us.htm
- OANDA spot crypto overview: https://help.oanda.com/us/en/faqs/spotcryptocurrency-overview.htm

---

## 3. OANDA U.S. Constraints

### 3.1 Maximum Trades per Day

I did **not** find an official OANDA U.S. document stating a universal simple maximum number of trades per day.

OANDA constraints are instead expressed through:

```text
API request limits;
API connection limits;
maximum open trades / orders rejection codes;
position and account exposure limits;
margin availability;
FIFO and no-hedging requirements;
market hours;
maintenance breaks;
instrument-specific limits.
```

Project 3 should not encode a fake legal OANDA “max trades/day.” It should encode:

```text
broker technical limits;
market-hours limits;
Project 3 risk-policy trade-rate bands;
hard overtrading gates.
```

### 3.2 API Request and Connection Limits

OANDA REST API best practices recommend:

```text
new connections: no more than 2 per second
persistent connection requests: no more than 100 per second
```

OANDA pricing streams provide at most:

```text
4 prices per second per instrument
```

Primary sources:

- OANDA REST API best practices: https://developer.oanda.com/rest-live-v20/best-practices/
- OANDA pricing endpoint documentation: https://developer.oanda.com/rest-live-v20/pricing-ep/

Project 3 policy:

```yaml
oanda_api_policy:
  new_connections_per_second_max: 1
  persistent_requests_per_second_max: 10
  pricing_streams_per_account: minimal
  order_submission_burst_max: 1 per instrument per decision bar
```

A 4h or 1h RL policy should not need high-frequency API usage.

### 3.3 Open Trades, Pending Orders, and Position Limits

OANDA API transaction definitions include rejection reasons for:

```text
maximum open trades exceeded;
maximum pending orders exceeded;
maximum position size exceeded;
account position value exceeded;
insufficient margin;
FIFO violation;
instrument halted;
trading disabled;
order size too small or too large.
```

Primary source:

- OANDA transaction definitions: https://developer.oanda.com/rest-live-v20/transaction-df/

OANDA U.S. position/account limit documentation states that:

```text
position limits apply per instrument across sub-accounts;
client/trading account limits apply across all instruments and sub-accounts;
the USD account limit listed is 60,000,000.
```

Primary source:

- OANDA position and account limits: https://help.oanda.com/us/en/faqs/position-limits-or-client-and-trading-account-limits.htm

Required Project 3 artifact:

```text
oanda_instrument_limits_snapshot.json
```

Minimum fields:

```json
{
  "instrument": "EUR_USD",
  "min_order_size": null,
  "max_order_size": null,
  "max_position_size": null,
  "margin_rate": null,
  "trading_hours": null,
  "price_precision": null,
  "pip_location": null,
  "financing_schedule": null,
  "snapshot_timestamp_utc": null,
  "source_url_or_api_endpoint": null
}
```

Without this artifact, live OANDA execution simulation is incomplete.

### 3.4 FIFO and Hedging Constraints

OANDA U.S. states that hedging is not available except for ECP accounts, and FIFO applies to forex trading accounts.

NFA Compliance Rule 2-43 requires FIFO offsetting and prohibits carrying offsetting forex positions in the same customer account.

Primary sources:

- OANDA account types and leverage: https://help.oanda.com/us/en/faqs/account-types-and-leverage-us.htm
- NFA Rule 2-43: https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=RULE+2-43&Section=4

Project 3 policy:

```yaml
oanda_us_fx:
  hedging_allowed: false
  fifo_required: true
  single_net_position_per_instrument: true
  partial_closes_must_be_fifo_compatible: true
```

The RL environment should represent OANDA FX exposure as one signed net position per instrument.

### 3.5 Market Hours, Friday Close, and Daily Break

OANDA U.S. states:

```text
forex weekly open: Sunday 17:05 New York time
forex weekly close: Friday 16:59 New York time
daily break: 16:59–17:05 New York time
```

OANDA also warns that spreads typically widen at approximately:

```text
Friday 16:00 New York time
```

This spread widening can trigger stop-loss orders or margin closeouts.

Primary sources:

- OANDA trading hours: https://www.oanda.com/us-en/trading/hours-of-operation/
- OANDA hours FAQ: https://help.oanda.com/us/en/faqs/hours-of-operation.htm

Project 3 policy:

```yaml
broker_profile: oanda_us_fx
timezone: America/New_York

daily_no_trade_window:
  start: "16:50 America/New_York"
  end: "17:10 America/New_York"

friday_new_position_cutoff:
  time: "Friday 14:00 America/New_York"

friday_risk_reduction_start:
  time: "Friday 15:00 America/New_York"

friday_force_flat_deadline:
  time: "Friday 15:45 America/New_York"

absolute_last_exit_safety_cutoff:
  time: "Friday 15:55 America/New_York"

broker_weekly_close:
  time: "Friday 16:59 America/New_York"
```

Important daylight-saving rule:

```text
Use IANA timezone America/New_York.
Do not hard-code the Friday close as a fixed UTC time.
```

During daylight time, 16:59 New York is normally 20:59 UTC. During standard time, it is normally 21:59 UTC. Project 3 must compute this dynamically.

### 3.6 Margin Closeout Behavior

OANDA defines Margin Closeout % approximately as:

```text
Margin Closeout % = (50% of Margin Used / NAV_mid) * 100
```

OANDA margin rules state that a margin closeout is triggered when margin closeout value declines to half or less than half of margin used. OANDA also checks margin requirement at approximately **3:45 p.m. ET**.

Primary sources:

- OANDA web guide: https://help.oanda.com/us/en/faqs/oanda-web-user-guide.htm
- OANDA margin rules PDF: https://www.oanda.com/assets/documents/468/OCAN_Margin_Rules_05.11.2020.pdf

Required environment state fields:

```text
margin_used
margin_available
margin_closeout_percent
nav_mid
unrealized_pnl
position_value
hours_to_margin_check_1545_et
hours_to_daily_break
hours_to_friday_close
```

This is directly relevant to Project 3 because prior project context found that the environment enforces a Friday/session close rule, but the inspected `tech_stat` input did not expose explicit `bars_to_force_close` or `hours_to_force_close` features to the policy.

### 3.7 OANDA Spot Crypto Constraints

OANDA U.S. spot crypto is structurally different from OANDA FX:

```text
spot crypto is available only for individual accounts;
there is no leverage;
short selling is not allowed;
trading is 24/7 except maintenance;
maximum order size and maximum position size are instrument-specific;
OANDA states a 0.25% fee applies to executed orders, subject to a $0.01 minimum;
transactions occur through Paxos;
Paxos is not an NFA member.
```

Primary sources:

- OANDA spot crypto overview: https://help.oanda.com/us/en/faqs/spotcryptocurrency-overview.htm
- OANDA regulatory disclosures: https://www.oanda.com/us-en/legal/regulatory-public-disclosures/

Project 3 policy:

```yaml
oanda_us_spot_crypto:
  leverage_allowed: false
  short_selling_allowed: false
  position_modes_allowed:
    - long
    - flat
  default_fee_per_executed_order: 0.0025
  round_trip_fee_drag_before_spread: 0.005
```

OANDA spot crypto should use lower trade-frequency targets than crypto perpetuals or low-fee exchange venues.

---

## 4. Rule / Constraint Table by Market Type

| Constraint Category | U.S. Equity Margin | U.S. Options Margin | U.S. Cash Securities | OANDA U.S. FX | OANDA U.S. Spot Crypto |
|---|---|---|---|---|---|
| PDT replacement relevant | Yes | Yes | Mostly no | No | No |
| Old PDT trade-count rule | Eliminated after broker migration | Eliminated after broker migration | Not main framework | Not applicable | Not applicable |
| $25,000 PDT minimum | Eliminated after broker migration | Eliminated after broker migration | Not applicable | Not applicable | Not applicable |
| Replacement | Intraday margin standards | Intraday margin standards | Settled cash / free-riding | CFTC/NFA + OANDA margin/FIFO/no-hedging | Paxos/OANDA spot crypto rules |
| Leverage | Margin account dependent | Margin account dependent | No margin borrowing | OANDA U.S. leverage profile | No leverage |
| Short selling | Broker/security dependent | Strategy/account dependent | Limited by cash rules | Net short FX exposure possible | No short selling |
| Hedging | Broker/account dependent | Strategy/account dependent | N/A | No hedging except ECP; FIFO applies | Not applicable |
| Trading hours | Exchange hours | Exchange hours | Exchange hours | Sun 17:05–Fri 16:59 NY; daily 16:59–17:05 break | 24/7 except maintenance |
| Main Project 3 risk | Intraday margin deficit | Intraday/options margin risk | settlement/free-riding | spread widening, FIFO, margin closeout, rollover | fee drag, no shorting, no leverage |

---

## 5. Recommended Project 3 Trade-Frequency Policy

### 5.1 Define Trade Counts Correctly

Project 3 must separate these metrics:

```text
fill_count:
  every broker or simulated fill

position_change_count:
  every non-trivial change in signed exposure

round_turn_equivalent:
  total absolute turnover / (2 * target_position_notional)

strategy_trade_count:
  entry-to-exit round trips or net exposure regime changes
```

Primary optimization metric should be:

```text
round_turn_equivalent_per_week
```

not raw fill count.

Raw fill count still matters for API and operational risk, but it can exaggerate frequency if the environment repeatedly scales in/out.

### 5.2 Recommended Bands

| Market / Timeframe | Primary Target | Secondary Band | Warning | Hard Research Max | Notes |
|---|---:|---:|---:|---:|---|
| FX 4h | 3/week | 3–6/week | >6/week | 12/week | Best OANDA FX default. |
| FX 1h | 6/week | 6–12/week | >12/week | 24/week | 24/week is upper exploratory. |
| OANDA crypto 4h | 1–3/week | 3–6/week | >6/week | 12/week | OANDA spot crypto fee drag is high. |
| OANDA crypto 1h | 3–6/week | 6–12/week | >12/week | 24/week | 24/week is hard upper cap. |
| Non-OANDA crypto/perp 4h | 3–6/week | 6–12/week | >12/week | 24/week | Only if venue supports low fees, shorts, and/or perps. |
| Non-OANDA crypto/perp 1h | 6–12/week | 12–24/week | >24/week | 36/week | Requires explicit cost/slippage/funding model. |

### 5.3 Which Objective Bands to Use

```text
3 trades/week:
  default for FX 4h and OANDA spot crypto 4h.

6 trades/week:
  primary for FX 1h and upper target for FX 4h / crypto 4h.

12 trades/week:
  upper realistic research band for FX 1h and crypto 1h;
  high for 4h.

24 trades/week:
  stress/upper exploratory band for 1h only;
  hard cap for OANDA spot crypto 1h and FX 1h.

more than 24 trades/week:
  do not use as a positive objective for OANDA FX/crypto.
  allow only as a negative diagnostic or non-OANDA low-fee venue experiment with explicit justification.
```

### 5.4 Hard Gates

```text
if broker_profile == "oanda_us_fx":
    hard_fail if hedging_required
    hard_fail if fifo_incompatible
    hard_fail if friday_flat_violation
    hard_fail if daily_break_trade_attempts > 0
    hard_fail if round_turn_equivalent_per_week > timeframe_hard_max
    hard_fail if cost_to_gross_edge_ratio >= 1.0
    hard_fail if margin_closeout_percent_max >= 80.0

if broker_profile == "oanda_us_spot_crypto":
    hard_fail if short_exposure < 0
    hard_fail if leverage_used
    hard_fail if 0.25% per-fill fee model not applied
    hard_fail if maintenance_window_order_handling missing
    hard_fail if round_turn_equivalent_per_week > timeframe_hard_max
```

### 5.5 Warning Gates

```text
warn if cost_to_gross_edge_ratio > 0.50
warn if FX 4h round_turn_equivalent_per_week > 6
warn if FX 1h round_turn_equivalent_per_week > 12
warn if OANDA crypto 4h round_turn_equivalent_per_week > 3
warn if OANDA crypto 1h round_turn_equivalent_per_week > 12
warn if average_holding_period < 2 bars
warn if exposure_ratio > 0.95 and net return is not clearly positive after costs
warn if Friday positions remain open after 15:45 New York time
```

---

## 6. Required Observation Features for OANDA FX

The policy cannot learn to avoid forced close if it cannot observe time-to-close.

Add:

```text
hours_to_fx_daily_break
bars_to_fx_daily_break
hours_to_friday_close
bars_to_friday_close
is_friday_risk_reduction_window
is_no_new_position_window
is_force_flat_window
is_broker_daily_break_near
broker_market_open
margin_closeout_percent
margin_available_norm
```

These must be included as explicit observation/environment-state features, not hidden only in environment termination logic.

---

## 7. Constraint Separation

### 7.1 Actual Legal / Regulatory Constraints

```text
FINRA PDT replacement applies to U.S. securities margin accounts.
It eliminates old PDT trade-count designation and $25,000 PDT minimum after broker migration.
It replaces them with intraday margin requirements.
OANDA U.S. forex is CFTC/NFA-regulated, not FINRA PDT-regulated.
NFA FIFO and no-offsetting-position rules apply to retail forex accounts.
```

### 7.2 Broker / Platform Technical Constraints

```text
OANDA API recommends 2 new connections/sec and 100 requests/sec on persistent connections.
OANDA price streams publish at most 4 prices/sec per instrument.
OANDA can reject orders based on max trades, orders, position size, account exposure, FIFO, insufficient margin, or halted instruments.
OANDA FX has daily and weekend closures.
OANDA spot crypto has no leverage, no short selling, high per-order fee, and instrument-specific limits.
```

### 7.3 Project Policy Constraints

```text
3/6/12/24 trades/week are project risk-control objective bands, not legal limits.
Friday force-flat before OANDA close is project risk policy, not direct law.
Trade-frequency hard caps prevent simulator exploitation and cost-blind overtrading.
Stage C remains locked.
Synthetic data remains training-only.
```

### 7.4 Speculative Recommendations

```text
3 trades/week is likely the best FX 4h target.
6–12 trades/week is reasonable for FX 1h if costs are modeled.
24 trades/week is too aggressive for 4h and should only be exploratory for 1h.
OANDA spot crypto should be lower-frequency than crypto perps because fee drag and long-only/no-leverage constraints are material.
```

---

## 8. Coding-Task Checklist for Orchestrator

```text
Title:
  Project 3 — FINRA/OANDA Trade-Frequency and Broker-Constraint Policy

Scope:
  Implement regulatory/broker-aware trade-behavior policy for SAC-first Stage 3X.
  Do not unlock Stage C.
  Do not treat PDT change as a reason to increase trade frequency.

P0 — Broker profile registry:
  [ ] Add broker_profile enum:
      - us_equity_margin
      - us_options_margin
      - us_cash_securities
      - oanda_us_fx
      - oanda_us_spot_crypto
      - crypto_exchange_spot
      - crypto_exchange_perp
  [ ] Add regulatory_profile enum:
      - finra_intraday_margin
      - finra_old_pdt_transition
      - cftc_nfa_retail_forex
      - paxos_spot_crypto
      - none_or_external
  [ ] Add broker_migration_date field for FINRA PDT transition.
  [ ] Add broker_confirmed_intraday_margin_enabled flag.

P0 — OANDA calendar:
  [ ] Implement America/New_York timezone calendar.
  [ ] Encode FX weekly open: Sunday 17:05 New York.
  [ ] Encode FX weekly close: Friday 16:59 New York.
  [ ] Encode daily break: 16:59–17:05 New York.
  [ ] Encode project no-trade window: 16:50–17:10 New York.
  [ ] Encode Friday no-new-position cutoff: 14:00 New York.
  [ ] Encode Friday force-flat deadline: 15:45 New York.
  [ ] Use IANA timezone conversion; do not hard-code UTC.

P0 — OANDA FX constraints:
  [ ] Enforce no hedging for oanda_us_fx.
  [ ] Enforce FIFO-compatible position netting.
  [ ] Represent FX exposure as one signed net position per instrument.
  [ ] Add margin closeout percent simulation field.
  [ ] Add account exposure and instrument exposure checks.
  [ ] Add insufficient-margin rejection simulation.
  [ ] Add daily-break and Friday-close execution blocking.

P0 — OANDA spot crypto constraints:
  [ ] Enforce long-only or long/flat behavior.
  [ ] Enforce no leverage.
  [ ] Apply 0.25% fee per executed order unless broker fee snapshot overrides it.
  [ ] Add per-symbol min/max order size fields.
  [ ] Add per-symbol max position size fields.
  [ ] Add maintenance-window handling.
  [ ] Forbid short positions for OANDA spot crypto.

P0 — Trade-frequency metrics:
  [ ] Compute fill_count_per_week.
  [ ] Compute position_change_count_per_week.
  [ ] Compute round_turn_equivalent_per_week.
  [ ] Compute strategy_trade_count_per_week.
  [ ] Compute turnover_per_week.
  [ ] Compute average_holding_period_bars.
  [ ] Compute cost_to_gross_edge_ratio.
  [ ] Compute exposure_ratio.
  [ ] Compute Friday_flat_violation_count.
  [ ] Compute daily_break_trade_attempt_count.

P0 — Trade-frequency bands:
  [ ] FX 4h target: 3/week; secondary 3–6/week; hard max 12/week.
  [ ] FX 1h target: 6/week; secondary 6–12/week; hard max 24/week.
  [ ] OANDA crypto 4h target: 1–3/week; secondary 3–6/week; hard max 12/week.
  [ ] OANDA crypto 1h target: 3–6/week; secondary 6–12/week; hard max 24/week.
  [ ] Non-OANDA crypto/perp profile must use venue-specific cost/fee/funding assumptions.

P0 — Observation features:
  [ ] Add hours_to_fx_daily_break.
  [ ] Add bars_to_fx_daily_break.
  [ ] Add hours_to_friday_close.
  [ ] Add bars_to_friday_close.
  [ ] Add is_friday_risk_reduction_window.
  [ ] Add is_no_new_position_window.
  [ ] Add is_force_flat_window.
  [ ] Add is_broker_daily_break_near.
  [ ] Add broker_market_open flag.
  [ ] Add margin_closeout_percent / margin_available state features.

P0 — Hard gates:
  [ ] Hard fail if Stage C touched.
  [ ] Hard fail if required broker profile missing.
  [ ] Hard fail if required cost model missing.
  [ ] Hard fail if oanda_us_fx strategy requires hedging.
  [ ] Hard fail if oanda_us_fx FIFO-incompatible partial closes occur.
  [ ] Hard fail if oanda_us_spot_crypto strategy shorts or uses leverage.
  [ ] Hard fail if round_turn_equivalent_per_week exceeds broker/timeframe hard max.
  [ ] Hard fail if Friday force-flat violation occurs for oanda_us_fx.
  [ ] Hard fail if trades occur during OANDA daily FX break.
  [ ] Hard fail if cost_to_gross_edge_ratio >= 1.0.

P1 — API and limit artifacts:
  [ ] Create oanda_api_limits_policy.yaml.
  [ ] Create oanda_instrument_limits_snapshot.json.
  [ ] Store max_order_size, min_order_size, max_position_size, margin_rate, precision.
  [ ] Store acquisition timestamp and source.
  [ ] Add account_position_value_limit check.
  [ ] Add pending_orders_allowed and open_trades_allowed rejection handling.

P1 — Reporting:
  [ ] Add regulatory_constraint_report.md.
  [ ] Add oanda_broker_constraint_report.md.
  [ ] Add trade_frequency_policy_report.md.
  [ ] Add Friday_force_close_audit.md.
  [ ] Add broker_profile to every evidence file.
  [ ] Add market_type to every evidence file.
  [ ] Add trade_rate_band_id to every SAC/NSGA candidate.

Forbidden:
  [ ] Do not unlock Stage C.
  [ ] Do not increase trade-frequency targets because PDT is changing.
  [ ] Do not apply PDT logic to OANDA FX or OANDA spot crypto.
  [ ] Do not simulate OANDA spot crypto as shortable or leveraged.
  [ ] Do not hard-code New York close as fixed UTC.
  [ ] Do not ignore daily FX maintenance break.
  [ ] Do not treat raw fill count as the only trade-frequency metric.
  [ ] Do not allow high-frequency candidates to pass without cost/slippage survival.
```

---

## 9. Final Recommendation

For Project 3’s SAC-first input/preprocessing optimization, the practical decision is:

```text
keep Stage C locked;
do not loosen overtrading gates because PDT is changing;
separate securities-margin PDT logic from OANDA FX/crypto logic;
implement broker-profile-aware trade-frequency bands;
add OANDA FX calendar / FIFO / no-hedging / margin-closeout constraints;
add OANDA spot crypto long-only / no-leverage / high-fee constraints;
use 3, 6, 12, and 24 trades/week as research bands, not legal thresholds;
reject policies that are profitable only by ignoring broker/platform constraints.
```

The most pragmatic Project 3 target is **not maximum trade count**.

It is:

```text
positive net return after realistic costs;
non-degenerate trade behavior;
broker-valid execution;
no Stage C contamination;
paired-seed robustness;
cost-fragility survival.
```
