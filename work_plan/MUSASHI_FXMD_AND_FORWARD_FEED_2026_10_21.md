# FXMacroData And Forward-Feed Handoff

Owner request: remove acquisition and read-only-feed dependencies without
changing the active native SAC experiment or exposing credentials.

## Evidence And Contract

Credential found in the existing private provider configuration. Its legacy
spacing was not a valid systemd assignment; a provider-only protected
EnvironmentFile was rendered, without printing or committing its value.
Stage16 probe:6/6 HTTP200,100 event groups;40 UNKNOWN labels exposed a real
parser defect, not missing credentials.

Corrected worker: official API host and header authentication, global bounded
request count including retries, announcement offset/version pagination and
prediction cursor pagination, nested forecast rows and generated_at, explicit
prediction class, atomic/no-overwrite run identity and incomplete exit3.
Raw responses and derived rows remain candidates, never automatically admitted.
Legacy PRE_RELEASE labels describe ordering only, not consensus or verified
intraday availability. Unknown timing stays unknown; nowcasts are not consensus.
The API's native-period official-forecast array is retained raw; truncation is
reported, not silently treated as complete event-specific coverage.

Live contract correction after the first full probe: announcements require
revisions=latest at an as_of cutoff; all was refused. MOM aliases use the
canonical inflation series with frequency=mom; confidence aliases use the
catalogue names. USD pmi/nmi are not served by this provider and are explicitly
excluded, not filled. Subsequent event-linked acquisition sets official_limit=0:
native-period quarterly/annual survey arrays are outside the requested monthly
event-consensus scope and cannot be labelled as those releases' consensus.
Their first500 rows remain in the initial raw receipts, not silently erased.

Primary contracts:
- https://fxmacrodata.com/documentation/point-in-time-backtesting
- https://fxmacrodata.com/documentation/predictions

The provider documents no historical event-specific US NFP market consensus
on any plan. Inspect actual class, series compatibility, publication precision
and availability before proposing surprise features. This is a coverage finding,
not a request for another subscription or for fabricated values.

## Read-Only EURUSD H1

Yahoo indicative EURUSD quote bars, explicitly not executable broker bid/ask.
No broker credentials and no order route. Completed UTC H1 only; partial and
non-hour-aligned live points are excluded. No interpolation or weekend padding.
Each snapshot retains72+ observed bars, raw response hash and true receipt time.
Availability and decision_as_of are the receipt, never backdated to bar close.
The initial history is context only, not historical forward-test predictions.
If a bar arrives late, the harness must select a still-future executable entry;
it cannot fill at an already-passed open. An entry at a past open invalidates it.
READY and freshness must be checked; fetch failures replace LATEST with an
UNAVAILABLE envelope. The old raw receipts remain unchanged.

No LLM trial is declared started here. Satoshi owns the preregistered harness;
this handoff supplies a read-only feed and governed calendar acquisition.

## Tests

PRE:5 intended history-contract failures. POST:13 unit tests across original,
pagination/classification and forward-feed suites. These are synthetic checks;
real acquisition/readback and initial feed snapshot are separate deployment
evidence to record below. Private locations belong only in the private handoff.

## Deployment Return

History runtimef212e9332:56/56 planned requests HTTP200, zero failures/cursor
errors.354 announcement rows with confirmed publication markers:66 in2020,
72 each2021-2024, zero outside requested publication years. Zero historical
calendar rows and zero event-linked forecasts under the fixed2025-01-01 cutoff.
This closes the credential/execution dependency, NOT delivery of a complete
2020-2024 event-consensus calendar. Query completion and data coverage differ.
Initial unfiltered probe contains Cleveland Fed model nowcasts, explicitly not
human consensus; those must not be relabelled or substituted into monthly-event
surprises without series and availability checks.

Read-only feed runtime2ed83c5f9: READY,102 completed H1 bars; timer120s enabled.
Initial history is context only. Native SAC was independently verified running
window7/stride2 at35000/100000 transitions; its queue was not stopped for this
work.15 final synthetic tests pass. No LLM inference or trading orders were
started. The machine-readable private handoff gives source paths and the
EnvironmentFile path, never the credential value.
