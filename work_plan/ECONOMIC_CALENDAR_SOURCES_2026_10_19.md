# Economic calendar: existing datasets and automatable sources (2026-10-19)

Purpose: a causal event study (volatility impact and dissipation per event family, later
surprise = actual − pre-release consensus) and a LIVE agent that consumes the calendar with
exact timestamps, no human in the loop. Point-in-time contract: `M5PHET/docs/ECONOMIC_CALENDAR.md`
(CAL01–CAL12). Everything below is read-only profiling plus primary-source research retrieved
2026-10-19; no acquisition, no credential use, no admission.

## 1. Existing dataset A: `feature-eng/tests/data/economic_calendar_2011_2021.csv`

sha256 `5172b322bfaf7bb568a0bb37cc2f806e8bd18ed51c5703c1098c8609a6249383`, 121,658 rows, no
header, 2011-01-01..2021-04-26 (last git touch "updated datasets" `bac5b59`; referenced only as a
commented default in `feature-eng/app/config.py`).

### Column mapping (verified)

| # | column | evidence |
|---|---|---|
| 1 | date `YYYY/MM/DD` | |
| 2 | time `H:MM:SS`, file-local clock (see §1.2) | NFP rows carry 8:30/7:30/9:30 |
| 3 | country (padded) | `United States` 36,930 rows, `Euro Zone` 7,530, `Germany` 5,422 |
| 4 | impact: `High/Moderate/Low Volatility Expected` | 10,084 / 41,835 / 69,739 |
| 5 | event name (padded) | |
| 6 | actual_text: `Better/Worse Than Expected`, `In Line with Expectation`, blank | blank 67,467 |
| 7 | unit: `%`, `K`, `M`, `B`, `T`, blank | |
| 8 | actual (numeric text, 93.7% non-empty) | NFP 2011-01-07 = `103` |
| 9 | forecast (44.6% non-empty; 78% for USD/EUR high impact) | NFP 2011-01-07 = `150.00` |
| 10 | previous, with the revision note embedded: raw bytes are `"vised From 39K>71 "` i.e. the exporter wrote `<Revised From 39K>71` and the CSV quoting cut `<Re`; 21,743 rows carry it | NFP 2011-01-07 previous `71`, originally published `39K` |

The lane-D guess (unit/actual shifted by one) is wrong; the mapping above reproduces NFP
2011-01-07 (actual 103K, forecast 150K) and ADP 2011-01-05 (297K vs 100K).

### 1.2 Timezone verdict (anchor method)

For 1,571 rows of events with a fixed official release time (NFP, US CPI, ISM 10:00, EIA crude
10:30 Wed, FOMC 14:00 ET; ECB decision 13:45 Frankfurt; BoE 12:00 London; UK CPI 09:30) the
implied offset `file_time − true_UTC` is:

- 2011-01..2018-01: **fixed UTC−5, no DST** (975/1,076 anchors; summer NFP shows 7:30, winter 8:30).
- 2018-02..2021-04: **UTC−4 from early Feb/Mar to late Aug/Oct, UTC−5 otherwise**
  (observed switches 2018-02-28→−4, 2018-09-12→−5; 2019-02-01→−4, 2019-11-01→−5;
  2020-02-03→−4, 2020-09-01→−5; 2021-02-03→−4). This matches no legal DST rule (US DST
  is second Sunday of March to first Sunday of November). It is an exporter artifact.

Consequence: minute-level UTC cannot be recovered from the `time` column alone after 2018-01
without an anchor-derived offset table per period; 2011–2017 convert with a constant +5 h.
The residual anchors (−4.5, −6.5, −7.5 h) are events whose true time differs from the assumed
anchor (e.g. EIA holiday shifts), not evidence of a third clock. Verdict: `CLOCK_RECONSTRUCTED_
FROM_ANCHORS_NOT_PROVIDER_DECLARED`; unusable for sub-hour event studies before reconstruction.

### 1.3 Point-in-time status of each field

| field | status | reason |
|---|---|---|
| date/time, country, event family, impact | schedule-like but **not** a dated schedule vintage; impact ratings are the exporter's at export time | single export, no versions |
| forecast | **unknown vintage**: Investing.com shows the consensus on the release row; whether it is the last pre-release snapshot or a later update cannot be proven from the file (CAL03 not satisfiable) | `actual_text` agrees with sign(actual−forecast) only 90%: the label uses an event-specific "good/bad" direction, not pure sign |
| actual | the value shown at export, i.e. possibly **revised**; first-print not separable except where the row's own `Revised From` refers to the previous period | retrospective |
| previous | **revised previous** with the original print embedded in `Revised From X>Y` (21,743 rows): both vintages recoverable for those rows only | partially PIT |
| duplicates | 10,686 rows share (date,time,country,event): same-name series at different units/periods (e.g. CPI MoM/YoY) — a key problem, not conflicting quotes | |

Coverage of USD+EUR(+DE) high-impact rows per year: 2011 483, 2012 470, 2013 461, 2014 467,
2015 474, 2016 482, 2017 508, 2018 475, 2019 537, 2020 592, 2021 (to April) 197. Top families:
EIA crude 538, Euro-area CPI 248, German manufacturing PMI 245, ECB president speaks 209, and
124 each for NFP, unemployment, CPI/core CPI, PPI, retail/core retail, ISM mfg/non-mfg, durable
goods, housing, JOLTS; speeches are 14.6% of high-impact rows.

Provenance: the vocabulary (`High Volatility Expected`, `Better Than Expected`, `Revised From`)
and the HTML-title artifact match an Investing.com economic-calendar export. Investing.com's
terms (fetched 2026-10-19, `https://www.investing.com/about-us/terms-and-conditions`):
"It is prohibited to use, store, reproduce, display, modify, transmit or distribute the data".
This file is therefore research-only legacy material: no redistribution, no live feed, and no
claim of a point-in-time consensus. Keep it out of any published lake resource.

## 2. Existing dataset B: fxmacrodata (financial-data)

- `economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet` (sha `8a50bf16…`),
  896 rows, 2026-02-05..2027-07-14, columns `currency, release, announcement_datetime (epoch s),
  announcement_datetime_local (ISO with offset), announcement_datetime_utc`. USD 218 / EUR 97 rows,
  ~5–11 future dates per release family. Future schedule only.
- `economic_calendar/release_actuals/fxmacrodata/announcements.parquet`, 18,147 rows, reference
  dates 2025-01-31..2026-04-30, announcement UTC 2024-12-12..2026-05-01; USD 48 indicators,
  EUR 29; fields `val, previous_value`-derived changes, no consensus column (README: "Consensus/
  forecast fields are not present unless supplied by the provider payload"). 11% of USD rows
  have minute-level (non :00/:30) timestamps, 0.8% second-level: real receipt-like precision.
- Provider: FXMacroData, REST `https://fxmacrodata.com/api/v1/{data_catalogue,calendar,
  announcements,predictions}/{currency}[/{indicator}]`, existing worker
  `_scripts/workers/stage15_fxmacrodata_worker.py` (key from `FXMACRODATA_API_KEY`, never echoed).
  The worker fetches catalogue, calendar and announcements; it does **not** call `predictions`.
- Primary pages (2026-10-19): "Release calendar with exact official times for 22 currencies, and
  the history behind every print"; "Announcement rows preserve UTC release timestamps";
  "Point-in-time records show what was known at each date"; consensus via
  `/predictions/{currency}/{indicator}` ("Market consensus and survey predictions where
  published", paid plans); terms (updated 2026-10-07): internal use allowed, redistribution/API
  exposure prohibited, "automated polling is permitted" with sleep intervals, >1 RPS outside
  fair use for Individual plans; from USD 50/month; no-key USD endpoints 15-minute delay, 100
  req/day. Historical 2020–2024 depth per currency is advertised ("26y point-in-time history")
  but **not verified in our data** (announcements start 2024-12-12); must be confirmed by a
  bounded governed pull (acquisition request, §4).

## 3. Source inventory for automation (primary sources, retrieved 2026-10-19)

### 3.1 Schedule only, free, official

| source | schedule | time precision | 2020–2024 history | access | terms / cost | notes |
|---|---|---|---|---|---|---|
| BLS `bls.gov/schedule` (+ `bls.ics`, per-release pages e.g. `empsit.htm`) | yes, to Dec 2027 | HH:MM, "All times on calendar are Eastern Time" | archive index 2000–2025 (`/bls/archived_sched.htm`), year pages not opened | HTML, ICS; API v2 is series data, no calendar endpoint | free; robots "blocked if excessive"; cite access date | updated "usually at least a week before" |
| BEA `bea.gov/news/schedule` + `apps.bea.gov/API/signup/release_dates.json` | yes, to 2027 | ISO 8601 **with UTC offset** (`2026-10-29T12:30:00+00:00`) | JSON starts 2025-01-07; 2020–2024 only via HTML archive (unverified) | JSON, ICS, HTML | free; API ToS PDF not read | JSON has duplicate entries and a misspelled key |
| Federal Reserve FOMC calendar | 2021–2027 on one page | date only (statement 14:00 ET is convention, not on page) | 2021–2024 yes, 2020 absent | HTML only | free | "tentative until confirmed" |
| ECB Governing Council + weekly calendar | 2026–2028 dates; weekly page has "Time: 07:00 CET" style | date only / CET on weekly page | unverified | HTML only; Data Portal API returned 503 | free | |
| Eurostat release calendar | yes; "This calendar uses Europe/Luxembourg time zone (CET/CEST)" | entries not rendered in fetch | unverified | HTML (scripted), ICS, email | free | |
| ONS release calendar | 9,141 published / 411 upcoming / 322 cancelled | "9:30am", no tz stated | date filters exist, untested | HTML, RSS, ICS; API beta has no calendar endpoint | OGL v3 | |
| FRED `releases/dates`, `release/dates` | yes with `include_release_dates_with_no_data=true` | **date only**, no time/timezone | yes via `realtime_start` (documented example 1997–2013) | JSON/XML API key | free; attribution notice required | "release dates … do not necessarily represent when data will be available" |

None of these provide consensus or actual values on the calendar page; actuals come from the
agencies' own data APIs (BLS/BEA/FRED) at release time.

### 3.2 Schedule + consensus + actual (commercial)

| source | schedule | consensus | actual / revisions | time precision | 2020–2024 | access | automated-use terms | cost | latency / failure modes |
|---|---|---|---|---|---|---|---|---|---|
| **FXMacroData** (existing adapter) | yes, exact official times | yes (`predictions`, paid), stated point-in-time vintages | yes; terms cite first-release, revisions, vintages | UTC epoch seconds | advertised, unverified | REST/JSON, CSV, SSE/WebSocket/webhooks | internal use OK, polling ≤1 RPS, no redistribution | from USD 50/mo | 15-min delay only without key; throttling/suspension reserved |
| Trading Economics API | yes, "nearly real-time" | yes (`Forecast` = survey consensus; `TEForecast` is a model) | yes; `Revised` field; `/calendar/updates` | minute `Date`, `LastUpdate` ms; timezone UNSTATED | date-range endpoint, depth UNSTATED; a point-in-time page exists | REST JSON/CSV | UNSTATED on pages read | prices UNSTATED; trial 100 requests | rate-limit page not read |
| EODHD economic events | yes | `estimate` (source unstated) | actual, previous; no revision field | `YYYY-MM-DD HH:MM:SS`, **no timezone** | "available from 2020" (vendor claim) | REST JSON, 100k req/day | business use = professional licence; no redistribution | UNSTATED | |
| Econoday | yes | yes ("forecast, actual, and prior") | yes | UNSTATED | UNSTATED | "APIs and widgets" | enterprise licence | demo/quote | |
| Finnhub, Financial Modeling Prep | docs returned shells/403 | — | — | — | — | — | NOT VERIFIED | — | cannot be assessed today |
| Bloomberg / LSEG Refinitiv | enterprise terminals/feeds; not evaluated | | | | | | enterprise only | | |

### 3.3 Free but not automatable / ToS risk

| source | finding |
|---|---|
| Forex Factory | site returns 403 to fetches; the public weekly JSON `nfs.faireconomy.media/ff_calendar_thisweek.json` has title/country/date (offset-aware, minute)/impact/forecast/previous, **no actual, current week only**, no terms text; history and licence UNSTATED → not a 2020–2024 source and not an actuals source |
| Investing.com | no API; terms prohibit use/storage/reproduction of the data → **breach risk for any automated use**; dataset A derives from it |
| OANDA v20 / Alpaca | OANDA v20 docs 404 on fetch; Alpaca docs show only a market (trading-days) calendar; no economic calendar seen |

## 4. Recommendation

1. **Live automation, USD/EUR:** FXMacroData through the existing stage-15 adapter, extended to
   `predictions` (consensus) and to the per-indicator announcement endpoints already used, with
   the point-in-time contract (CAL01–CAL12) applied at receipt: store source `announcement_datetime`,
   our receipt time, and the consensus vintage separately. Polling ≤ 1 request/s with sleeps;
   no redistribution; data stays inside the governed lake.
2. **Independent schedule witness (free, official):** BEA JSON (explicit UTC), BLS ICS/HTML
   (Eastern), ECB weekly page (CET) and FRED `releases/dates` (date only) to cross-check that
   each scheduled instant in the commercial feed matches the agency's declared time and
   timezone, especially across DST transitions (dataset A shows what an unchecked export does).
3. **Dataset A** remains a legacy research file: usable only after anchor-based clock
   reconstruction, without consensus-vintage claims, and never published or redistributed.
4. **Dataset B** is prospective capture evidence (2024-12 onward) and already carries exact UTC;
   it is the template for the required schema.

Open before any event study: FXMacroData 2020–2024 depth per family (schedule times, consensus
vintages, first prints, revisions) must be verified by a bounded governed pull — see
`work_plan/ECONOMIC_CALENDAR_ACQUISITION_REQUEST_2026_10_19.md`.
