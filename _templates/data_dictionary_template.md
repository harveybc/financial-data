# Data Dictionary: [Dataset Name]

## Source

- **Provider:** [e.g., FRED, Binance, Polygon.io]
- **URL:** [base URL]
- **License:** [e.g., Public Domain, CC-BY, Proprietary - Subscription]
- **Acquisition method:** [API, bulk download, manual download]

## Coverage

- **Date range:** [YYYY-MM-DD to YYYY-MM-DD]
- **Frequency:** [tick, 1m, 5m, 1h, 1d, weekly, monthly]
- **Total observations:** [number]
- **Coverage gaps:** [any known gaps in data]

## Schema

| Column | Type | Description | Units | Example | Notes |
|--------|------|-------------|-------|---------|-------|
| timestamp | datetime | UTC timestamp of observation | ISO 8601 | 2024-01-01T00:00:00Z | |
| ... | | | | | |

## Known Issues

- [Any quirks, errors, or anomalies]

## Validation Status

- [ ] Bar count realistic
- [ ] Schema matches specification
- [ ] No duplicate timestamps
- [ ] No future timestamps
- [ ] Statistical validation (Stage II-0b 6 tests)

## Provenance

See `provenance.json` in same folder.
