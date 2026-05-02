# TradingAgents Integration Assessment

Updated: 2026-05-02

## Decision

Adopt TradingAgents as a later Project 3 experimental lane, not as a replacement for the pre-registered RL experiment framework.

Recommended placement: **Phase 3.3 / Phase 4 LLM Strategy Committee** after Stage 3.1 has produced baseline RL evidence.

## Why It Is Interesting

TradingAgents matches a real gap in Project 3: explainable strategy review around signals. The paper proposes a trading-firm-style multi-agent workflow with fundamental, sentiment, news, and technical analysts; bull and bear researchers; a trader; risk managers; and a portfolio manager. The repo now supports structured-output decision agents, checkpoint resume, persistent decision logs, Docker, Ollama, DeepSeek, Qwen, GLM, Azure, and other providers.

For Project 3, the best use is not asking it to rediscover all our features. The best use is to give it curated Project 3 evidence packs:

- RL model signals and confidence.
- Stage 2 technical/statistical/decomposition/learned feature summaries.
- Macro calendar and release-context summaries.
- On-chain/funding/microstructure summaries for crypto.
- Backtest diagnostics: Sharpe, Sortino, drawdown, turnover, regime sensitivity, failure cases.

Then TradingAgents can produce an auditable committee decision: buy/hold/sell or rating, rationale, risk critique, and whether the RL signal should be trusted, reduced, vetoed, or escalated.

## Current Code Fit

The current upstream repo is stock-centric by default:

- Core data routes through yfinance or Alpha Vantage.
- `TradingAgentsGraph.propagate(ticker, trade_date)` expects ticker/date style runs.
- Market tools expose OHLCV and selected technical indicators.
- The framework supports `llm_provider = deepseek` and model IDs such as `deepseek-v4-flash` and `deepseek-v4-pro`.
- Structured outputs exist for Research Manager, Trader, and Portfolio Manager.
- It logs full state and maintains a memory/reflection log.

So Project 3 needs an adapter rather than direct use of the default data tools.

## Recommended Architecture

1. **Do not run it inside Stage A screening initially.** Stage A must remain deterministic enough to rank feature sets and RL algorithms.
2. **Create a Project 3 evidence-pack exporter** that writes compact markdown/JSON per asset/timeframe/date/window.
3. **Add a TradingAgents Project 3 data adapter** that maps `btcusdt`, `ethusdt`, `btcusdt_perp`, `eurusd`, and `usdjpy` to our local parquet features instead of yfinance.
4. **Use DeepSeek V4 Flash for analyst/debate passes** because it is cheaper and fast enough for broad committee review.
5. **Use DeepSeek V4 Pro only for escalations**: contradictory agent reports, high-impact final candidates, or post-Stage B synthesis.
6. **Evaluate it as an overlay**, not a standalone claim: compare RL-only vs RL + TradingAgents veto/position-scaling on validation data, then only after promotion run a single held-out 2025 evaluation.

## Mini Experiment Design

Initial offline test:

- Assets: `btcusdt`, `ethusdt`, `eurusd`, `usdjpy`.
- Timeframes: `1h`, `4h` first.
- Inputs: top 10-20 Stage A RL candidate signals plus evidence packs.
- Models: DeepSeek V4 Flash for quick/deep roles initially, with Pro only for a small adjudication subset.
- Output: structured rating plus action: buy/hold/sell, position-sizing suggestion, risk-veto flag, and rationale.

Metrics:

- RL-only validation Sharpe/drawdown/turnover.
- RL + LLM veto validation Sharpe/drawdown/turnover.
- Directional accuracy around high-confidence signals.
- False veto rate: good RL trades blocked by LLM.
- Bad-trade avoidance: losing/high-drawdown RL trades blocked or reduced.
- Token cost per evaluated decision.

Kill criteria:

- If LLM overlay reduces validation Sharpe or increases drawdown after transaction costs, do not promote.
- If decisions are unstable across repeated runs at fixed temperature, do not promote.
- If rationale cites unavailable or future data, treat as leakage and block from Stage C.
- If cost per useful decision is high relative to lift, keep it only as a report-generation tool.

## Integration Tasks

1. Build `experiments/tradingagents_adapter/README.md` with schema and run contract.
2. Export Project 3 evidence packs from Stage 2/3 artifacts.
3. Patch or wrap TradingAgents data tools so they read local parquet summaries.
4. Add a deterministic evaluation harness that replays historical decision dates and records the exact prompt/evidence/model/decision.
5. Run a 20-decision smoke test using DeepSeek V4 Flash.
6. If promising, run a Stage B overlay ablation on promoted RL configs.

## Risks

- LLM nondeterminism can pollute strict model-selection if used too early.
- Default TradingAgents data tools can fetch live/yfinance data, which may leak or mismatch our Project 3 corpus.
- News/sentiment/fundamental roles are equity-oriented; for crypto/FX we should replace them with macro, on-chain, funding, and RL-diagnostic analysts.
- Strong prose can look persuasive even when the action is not profitable; every claim must be scored by backtest metrics.

## Recommendation

Proceed, but as a controlled overlay experiment after Stage 3.1 baselines. This is a high-upside idea for explainability, risk-vetoes, and final strategy review. It should not delay Stage 3.1, and it should not touch held-out 2025 until it has passed validation gates.

