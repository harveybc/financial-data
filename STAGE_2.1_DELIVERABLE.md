# Stage 2.1 Deliverable - Downsampling and Resampling

Generated: 2026-05-02T00:48:03.101943+00:00

## Trading Assets Processed

- Total trading assets: 50
- Assets with all target timeframes: 50

| Asset | 5m | 15m | 1h | 4h |
| --- | --- | --- | --- | --- |
| adausdt | ok | ok | ok | ok |
| adausdt_perp | ok | ok | ok | ok |
| asterusdt | ok | ok | ok | ok |
| audusd | ok | ok | ok | ok |
| avaxusdt | ok | ok | ok | ok |
| avaxusdt_perp | ok | ok | ok | ok |
| bchusdt | ok | ok | ok | ok |
| bnbusdt | ok | ok | ok | ok |
| bnbusdt_perp | ok | ok | ok | ok |
| btcusdt | ok | ok | ok | ok |
| btcusdt_perp | ok | ok | ok | ok |
| dogeusdt | ok | ok | ok | ok |
| dogeusdt_perp | ok | ok | ok | ok |
| dotusdt | ok | ok | ok | ok |
| ethusdt | ok | ok | ok | ok |
| ethusdt_perp | ok | ok | ok | ok |
| eurgbp | ok | ok | ok | ok |
| eurjpy | ok | ok | ok | ok |
| eurusd | ok | ok | ok | ok |
| gbpjpy | ok | ok | ok | ok |
| gbpusd | ok | ok | ok | ok |
| hbarusdt | ok | ok | ok | ok |
| linkusdt | ok | ok | ok | ok |
| linkusdt_perp | ok | ok | ok | ok |
| ltcusdt | ok | ok | ok | ok |
| nearusdt | ok | ok | ok | ok |
| nzdusd | ok | ok | ok | ok |
| paxgusdt | ok | ok | ok | ok |
| pepeusdt | ok | ok | ok | ok |
| shibusdt | ok | ok | ok | ok |
| skyusdt | ok | ok | ok | ok |
| solusdt | ok | ok | ok | ok |
| solusdt_perp | ok | ok | ok | ok |
| suiusdt | ok | ok | ok | ok |
| taousdt | ok | ok | ok | ok |
| tonusdt | ok | ok | ok | ok |
| trxusdt | ok | ok | ok | ok |
| trxusdt_perp | ok | ok | ok | ok |
| uniusdt | ok | ok | ok | ok |
| usd1usdt | ok | ok | ok | ok |
| usdcad | ok | ok | ok | ok |
| usdchf | ok | ok | ok | ok |
| usdcusdt | ok | ok | ok | ok |
| usdeusdt | ok | ok | ok | ok |
| usdjpy | ok | ok | ok | ok |
| wlfiusdt | ok | ok | ok | ok |
| xlmusdt | ok | ok | ok | ok |
| xrpusdt | ok | ok | ok | ok |
| xrpusdt_perp | ok | ok | ok | ok |
| zecusdt | ok | ok | ok | ok |

## Cross-Source Features Forward-Filled

- 5m files: 370
- 15m files: 370
- 1h files: 370
- 4h files: 370

## Manifest

- `features/MANIFEST.json`

## Validation

- Trading asset OHLC integrity and timestamp ordering were checked per worker.
- Cross-source alignment uses point-in-time backward/as-of merge, so no future value is used.
- No interpolation is used.

## User Gate

Stage 2.1 is ready for review once all machine reports are synced and this deliverable is current.
