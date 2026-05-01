# Stage 1.3 Consensus/Surprise Gap

FRED release actuals and a historical release-date proxy are present under `economic_calendar/release_actuals/` and `economic_calendar/scheduled_events/fred_release_date_proxy/`.

Current source evidence:

- Trading Economics documents calendar actuals, survey consensus, forecast fields, and point-in-time calendar support, but the former `guest:guest` API access now returns HTTP 410 with a subscription message.
- FXStreet documents event occurrences with actual/consensus-style values, but its Economic Calendar API endpoints require OAuth2 authentication.

Decision: keep the FRED actuals and release-date proxy as the free Stage 1.3 deliverable. Treat true scheduled events with consensus/surprise as a Stage 1.4 subscription/credential decision unless a stable free endpoint is approved.

Recommended user action if this feature is required: obtain Trading Economics API credentials or FXStreet API OAuth access. Otherwise defer consensus/surprise features and avoid fragile scraping.
