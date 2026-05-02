# Stage 2.2 Deliverable

Generated: 2026-05-02T07:20:22.629740+00:00

## Status

- Trading technical/statistical features: complete.
- Cross-source statistical features: complete with nonnumeric metadata-like inputs skipped.
- Actionable failures: 0.

## Counts

- Trading jobs: 200/200 ok.
- Cross-source jobs: 1464/1480 ok.
- Cross-source skipped as no numeric columns: 16.
- Technical feature files: 200.
- Statistical feature files: 200.
- Cross-source statistical files: 1464.

## Output Roots

- `features/trading_asset_features/<asset>/<tf>/technical.parquet`
- `features/trading_asset_features/<asset>/<tf>/statistical.parquet`
- `features/cross_source_statistical/<tf>/*.parquet`

## Validation Note

The 16 skipped cross-source jobs are four nonnumeric sources across four timeframes. They do not block Phase 2 because they cannot produce numeric rolling statistics.
