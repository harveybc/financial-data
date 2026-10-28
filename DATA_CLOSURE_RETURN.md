# Data closure return, lane D (SATOSHI_DATA_AND_RL_ORDER_2026_10_18 section D)

Branch `satoshi/data-closure-20261018`, base `codex/data-curation-20261018 @dd14510cf`.
Commits: `9f7b518b3` (scripts, tests, evidence) and the commit carrying this return.
Status words that apply: DIAGNOSTIC, CANDIDATE, OBSERVED, UNRESOLVED. Nothing here is
data admitted, a lake replaced or a selection completed. No service, controller, config,
DOIN, lake or warehouse resource was modified; no GPU, no training, no labels read.

Evidence files (hashes and aggregates only, no provider rows, no private paths), all under
`deliverables/data_closure_20261018/`:

| File | sha256 | Content |
|---|---|---|
| `D1_READ_ONCE_EVIDENCE.json` | `bc8b2cbd…c2b233` | report digests, monthly counts, clock table, weekly source-file outcomes |
| `CLOCK_WITNESS_BY_DATE.json` | `59fe1a87…e4fc5` | per-date, per-hypothesis, per-side differences (172 pair-dates) |
| `SESSION_SCHEDULE.json` | `6ed87e2a…95ac6` | observed weekly open/close per week, typed missing-run classes |
| `REQUIRED_VARIABLE_INVENTORY.candidate.json` | `58077e32…a91109` | 394 records, three groups, missing files in the denominator |

Generated reports read ONCE (D1), by digest: `QUALITY.eurusd.json 429ea0f26d3d…`,
`QUALITY.gbpusd.json 434b944681dd…`, `CLOCK_COMPARISON.json dc2d50eb1a6e…`,
`GAP_RECOVERY_PLAN.json a979b50bd635…`, `GAP_RECOVERY_STATUS.json bae7d9e7a6b0…`,
`PUBLICATION_STATUS.json f09ffa6a53de…`, `STATUS.json b9b6200e77b3…`. Their locations were
resolved by path from the deployed user units' arguments and are not published.

## D1. Generated native quality, gap and clock reports (read once)

Primary native feed: FXCM H1, BID view with ASK retained, 12 year-files (6 per pair), hashes in
`D1_READ_ONCE_EVIDENCE.json`. Required range 2020-01-01..2026-01-01, 72 months per pair,
37,584 assumed open hours per pair (NY 17:00 Sunday to 17:00 Friday, no holiday certificate).

| Pair | observed rows | missing expected open hours | months with a gap | crossed bid/ask endpoints | rows outside assumed schedule | TRAIN return flags (MAD) |
|---|---:|---:|---:|---:|---:|---:|
| EURUSD | 36,553 | 1,103 | 14 of 72 | 904 | 72 | 1,277 flagged, 0 removed |
| GBPUSD | 36,481 | 1,108 | 15 of 72 | 410 | 5 | 1,117 flagged, 0 removed |

Gap recovery (Forexite daily archives): plan identity `108843ad…`, 110 requested dates in 8
batches, state `PARTIAL_CANDIDATES_CLOCK_NOT_ADMITTED`, 8 unavailable batches; the last child
run reports 10/12 acquired, failures 2025-07-26 and 2025-12-27 `NO_REQUIRED_PAIRS` (both
Saturdays by label). 86 candidate archives are retained as parquet. Publication state
`QUALITY_PUBLISHED_NOT_ADMITTED` (7 warehouse rows, 2 second-machine copies). Controller
state `RECOVERY_AWAITING_CLOCK_CALENDAR_AND_GAP_ACCEPTANCE`.

CLOCK_COMPARISON overall (paired complete hours, bid close, 4 dp):

| Pair | hypothesis | paired h | median abs | p95 abs | max abs |
|---|---|---:|---:|---:|---:|
| EURUSD | fixed UTC+1 | 679 | 0.00014 | 0.00063 | 0.00440 |
| EURUSD | fixed UTC+2 | 676 | 0.00041 | 0.00195 | 0.00738 |
| EURUSD | Europe/Berlin | 679 | 0.00014 | 0.00023 | 0.00143 |
| GBPUSD | fixed UTC+1 | 676 | 0.00018 | 0.00127 | 0.00544 |
| GBPUSD | fixed UTC+2 | 672 | 0.00053 | 0.00268 | 0.01180 |
| GBPUSD | Europe/Berlin | 675 | 0.00018 | 0.00041 | 0.00193 |

Europe/Berlin has the lowest p95/max. **That is an overlap score, not a verified timezone
and not a verified quote side.** Only 34 pair-dates have overlap, concentrated in December,
January, late March, June and July; no October DST-end date is paired; rounded-4 dp agreement
is 43–46 of 679 hours, i.e. the candidate is a different venue/side from the FXCM bid.

## D2. Forexite archive semantics

Primary documentation, retrieved 2026-10-18:

- `https://www.forexite.com/free_forex_quotes/forex_history_arhiv.html` (sha256 of the
  fetched bytes `7892d51cf5d38491dd4ec6147367d63ca7994279cd905ebf2c50c8b81f9258dc`, declared
  charset windows-1251). The archive table header reads «Период, GMT+1» and lists three file
  families per day: «ProSuite Bid» (`DDMMYY.xpo`), «ProSuite Trade» (`DDMMYYtr.xpo`) and
  «MetaStock» (`DDMMYY.zip`). The files this project retrieves are the `.zip` (MetaStock)
  family. The page does not define the MetaStock price (bid or trade), does not mention
  daylight saving, and does not say whether a minute stamp is the bar start or end.
  From 23.06.2024 the `.xpo` links show «0 Kb»; only `.zip` keeps a size.
- `https://www.forexite.com/free_forex_quotes/` returned an empty body; the home page shows a
  maintenance notice. The `<TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>` layout is
  documented nowhere on the pages read; it is what the retained archives contain (parser
  `_scripts/recover_forexite_observations.py`, UNSTATED by the provider).

Declared vs observed clock (command below; `CLOCK_WITNESS_BY_DATE.json`):

| Season (dates with pairs) | fixed UTC+1 p95 | fixed UTC+2 p95 | Europe/Berlin p95 |
|---|---:|---:|---:|
| Winter, 58 pair-dates (Dec/Jan 2020–2025) | identical to Berlin on 58/58 | 0.0008–0.0045 | 0.0002–0.0009 |
| 2020-03-30 EURUSD / GBPUSD (24 h each) | 0.00367 / 0.00490 | 0.00022 / 0.00027 | 0.00022 / 0.00027 |
| 2023-06-30 EURUSD / GBPUSD (22 h) | 0.00181 / 0.00238 | 0.00022 / 0.00025 | 0.00022 / 0.00025 |
| 2023-07-10 EURUSD / GBPUSD (24 h) | 0.00161 / 0.00264 | 0.00022 / 0.00027 | 0.00022 / 0.00027 |

Both statements are retained: the provider declares «GMT+1»; the observed summer quotes
contradict a fixed GMT+1 reading (one-hour offset against the FXCM feed on every summer date
with overlap) and agree with a clock that follows European summer time. Reproducible
counterexample: archive `300320.zip`, EURUSD, 24 complete hours: fixed UTC+1 p95 0.00367 /
max 0.00437 against Berlin p95 0.00022 / max 0.00025. No shift was applied, no offset fitted,
no price merged. UNRESOLVED: no October (DST end) date has overlap; the summer evidence is
three dates (one of them the day after the EU change); the minute-end convention is the
parser's declared assumption, not a provider statement.

Quote side: bid/ask/mid differences are within 0.00004 of each other on every hypothesis
(e.g. EURUSD Berlin median 0.00022 bid, 0.00026 ask, 0.00023 mid). The witness cannot
discriminate the candidate's side; it stays `UNVERIFIED_TRADE_ARCHIVE_NOT_ASSUMED_BID`.

Command (CPU, 2 GiB, 120 s): `python _scripts/clock_witness_by_date.py --primary-root <PRIMARY_RAW_ROOT> --candidate-root <ALTERNATIVE_RAW_ROOT> --histdata-1h <lake>/market_data/forex/g10/eurusd/1h.parquet --output <out>/CLOCK_WITNESS_BY_DATE.json`

## D3. Primary native H1 session and holiday schedule

Primary documentation, retrieved 2026-10-18: `https://www.fxcm.com/markets/trading-hours/`
and `https://www.fxcm.com/uk/trading-hours/` state «For forex, trading opens on Sundays
between 5:00 PM ET and 5:15 PM ET and closes on Fridays around 4:55 PM ET». Holiday schedules
for 2020–2025: UNSTATED (dedicated holiday pages return 404). `https://github.com/fxcm/MarketData`
README: «Timestamps are in UTC»; bar open/close meaning and bid/ask columns: UNSTATED. The
retained parser (`tools/i6dmo/recover_fxcm_quotes.py` in the pinned predictor runtime) records
`clock='UTC bar START; available_at = bar end'` as its own convention.

Observed (`SESSION_SCHEDULE.json`, 306 weeks per pair): first bar Sunday 17:00 NY in 301 weeks
(EURUSD; 2 weeks Sunday 18:00, 1 Monday 01:00, 3 Saturday 17:00), last bar Friday 16:00 NY in
274 weeks (EURUSD) / 296 (GBPUSD). The NY-local alignment holds across both US DST changes,
which supports the source following New York time; this is observed, not certified.

Typed separation of the 1,103 (EURUSD) / 1,108 (GBPUSD) missing assumed-open hours:

| Class | EURUSD h | GBPUSD h | Basis |
|---|---:|---:|---|
| `SOURCE_FILE_ABSENT` | 975 | 946 | weekly source file failed: 404 for 2020-W01, 2024-W01, 2025-W01/02/29/30; empty body 2024-W35/51/52; `QUOTE_SCHEMA` 2023-W27 |
| `CALENDAR_RESOLUTION_CANDIDATE` | 126 | 160 | in-file absence on 24–26 Dec, 31 Dec–2 Jan; early closes observed (24/31 Dec 2020 Thursday 14:00 NY, 24 Dec 2021 Friday 14:00, GBPUSD 2023/2024 opens Tuesday 00:00 NY after 25 Dec / 1 Jan) |
| `MISSING_QUOTE_OPEN_SESSION` | 2 | 2 | isolated hours 2022-12-30 21:00Z, 2023-12-29 21:00Z (both), 2020-03-29 21:00Z (GBPUSD) |

Not closed, not filled: a Saturday without an archive is `NO_REQUIRED_PAIRS` in the provider
response, not a demonstrated outage and not a certified closure. 2021-W53 / 2022-W53 404s are
not data loss (those ISO weeks do not exist in those years; December 2021/2022 lose 3 and 2
hours, both holiday candidates). Also observed: EURUSD carries 72 rows outside the assumed
schedule in 2024–2025 (Saturday bars up to 16:00 NY), GBPUSD 5; these are source facts for the
calendar ruling, not errors to delete.

Command: `python _scripts/native_session_schedule.py --primary-root <PRIMARY_RAW_ROOT> --quality-dir <CURATION_ROOT> --output <out>/SESSION_SCHEDULE.json`

## D4. Independent quote source

No new acquisition was made: the existing Forexite candidate already covers the weekday dates
of every `SOURCE_FILE_ABSENT` week, the remaining 26 dates are Saturday/Sunday/holiday labels
with `NO_REQUIRED_PAIRS`, and the blocker is clock/side verification, not more bytes.
Reused an existing observation instead: the lake's HistData EURUSD 1h file
(`market_data/forex/g10/eurusd/1h.parquet`, sha256 `c6628375…8712d4e2e`, matches its
provenance). HistData documents «Eastern Standard Time (EST) time-zone WITHOUT Day Light
Savings adjustments» and bar prices «based on the tick Bid price»
(`https://www.histdata.com/f-a-q/`, `https://www.histdata.com/f-a-q/data-files-detailed-specification/`,
retrieved 2026-10-18). The lake file is labelled UTC. Against the FXCM bid close:

| Label hypothesis | paired h | median abs | p95 abs | 4 dp agreement |
|---|---:|---:|---:|---:|
| as labelled, UTC bar start | 34,346 | 0.00104 | 0.00468 | 986 |
| label is EST (fixed UTC-5) bar start | 35,477 | 0.00012 | 0.00171 | 15,106 bid / 13,488 ask |

Finding: the lake's UTC label is inconsistent with the provider's EST declaration and with the
overlap; under the EST reading it agrees with the FXCM bid better than with the ask. This is a
candidate witness for quote side and clock, not a verified replacement and not a lake change.

## D5. REQUIRED_VARIABLE_INVENTORY candidate

Built from configuration, not from existing files: `features/cross_source_docs/*/provenance.json`
(370 catalog variables), `configs/native_fx_recovery.v1.json` (trading-required: EURUSD and
GBPUSD H1 BID, ASK retained, FX session calendar = 5 records) and the predictor availability
contract `9668898c…` (19 model candidates with raw-dependency class and declared availability
source). Denominator 394 records; 370/5/19 are counted, never hardcoded (`hardcoded_population_sizes: []`).

Coverage against the local lake (`--lake-root`, 4 chunks, 2 GiB/120 s each):

- Files: 337 present, **33 missing** (all `coinmetrics_community` on-chain series), kept in the denominator.
- Of the 337 present, **104 have zero rows anywhere in 2020-01..2025-12** (97 CryptoQuant files
  covering only 2026-01-22..2026-05-01, 3 FINRA 2025 daily short volume, 2 FRED, 1 onchain_eth,
  1 scheduled_events); 26 more miss 48 months, 4 miss 40, 15 miss between 1 and 67 months;
  192 have every month. Inferred cadence: 222 daily, 63 monthly, 24 quarterly, 9 weekly,
  10 eight-hourly (funding). An absent month in a quarterly series is a cadence fact, not a gap;
  the record keeps both the absent list and the inferred spacing.
- Panel files (FINRA, OECD, fxmacrodata) show duplicate timestamps across entities; these are
  key-resolution items, not conflicting quotes. Four files carry non-finite cells.
- Native FX: required 2020–2025 month by month, actual support per D1/D3; model candidates
  carry `availability_source` from the contract (DECLARED_CONSERVATIVE / UNVERIFIED / VERIFIED_EVIDENCE).

Command: `python _scripts/required_variable_inventory.py --repo-root . --native-config configs/native_fx_recovery.v1.json --model-manifest <19-feature list json> --availability-contract <feature_availability.v1.json> --lake-root <lake> --chunk i/4 --output <out>/INVENTORY.chunk<i>.json`

## D6. Tests (written before the scripts)

`tests/test_data_closure_checks.py`, 12 tests: missing month with 100% finite rows stays in
the denominator; missing file counted; DST shift detected under hypotheses, never fitted;
incomplete hour excluded and counted; conflicting duplicate fails, identical counted;
impossible OHLC fails while a 3% coherent crash is only flagged; zero scale is NOT_ESTIMABLE;
release after t not consumable; a 3 h open-session gap keeps its elapsed hours; missing runs
classified into the three D3 classes; weekly open/close observed; inventory denominator.

Command and result: `crispdm-run -q -m 2G -t 120s -- python -m pytest tests/test_data_closure_checks.py tests/test_compare_native_fx_sources.py tests/test_recover_native_fx_gaps.py tests/test_native_fx_recovery.py tests/test_recover_forexite_observations.py tests/test_native_recovery_status.py tests/test_publish_native_fx_quality.py -q` → **56 passed, 1 skipped** (the skip is pre-existing). Baseline before this lane on the same three recovery modules: 25 passed.

## Confirmed versus unresolved

Confirmed (by documents or retained bytes): Forexite declares GMT+1 and three archive families;
the retrieved family is MetaStock with an undeclared price type; FXCM states ET session bounds
and UTC timestamps; HistData states EST-no-DST and bid; the twelve weekly source-file failures
and their causes; the three typed classes above; the 33 missing catalog files and 104 catalog
files without 2020–2025 rows.

Unresolved: the candidate's timezone (score favours Europe/Berlin; no DST-end overlap), its
quote side, the minute start/end convention, the FXCM bar-open convention, the FXCM 2020–2025
holiday schedule, the lake HistData label, and every `SOURCE_FILE_ABSENT` week's replacement.

## Next required object and executable command

Missing object: a Forexite overlap day on both sides of an October DST end with primary hours
present (e.g. native dates 2023-10-27 and 2023-10-30, which are within already-acquired source
weeks and need no new primary request). Next deterministic command, bounded to two dates and
reusing the existing adapter and cooldown rules:

`python _scripts/recover_forexite_observations.py --output <ALTERNATIVE_DIAGNOSTIC_ROOT> --dates 2023-10-27 2023-10-30`

then rerun the D2 witness command. The calendar ruling (Saturday rows, holiday candidates) and
the HistData label question go to Musashi; this lane admits and deletes nothing.
