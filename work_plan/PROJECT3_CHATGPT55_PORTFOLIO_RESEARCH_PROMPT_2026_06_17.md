# Prompt For ChatGPT 5.5 Pro Research Agent

We need pragmatic research for Project 3, a weekly-retrained portfolio trading
system. This is not an academic publication project. The only useful outcome
is better repeated next-week profit/risk after realistic costs for a paid
trading/portfolio service.

Current business model:

- Every weekend, train/update per-asset trading agents using only data known
  before the decision cutoff.
- During live operation, clients do not hold just one asset. They hold a
  portfolio of active asset streams.
- A higher portfolio supervisor decides weekly:
  - which assets/model streams are active;
  - which streams receive no-trade flags;
  - capital/order-size weights per active stream;
  - max exposure and risk constraints.
- Per-asset SAC/RL agents still decide trading actions inside their assigned
  asset budget.
- The portfolio rebalance happens every weekend.

Current evaluation:

```text
per weekly anchor:
  train: N years before validation
  train_tail: final slice of train for early-stop score
  validation: next historical week
  test: following week only
```

Selection metric:

```text
composite = 0.5 * train_tail_total_return + 0.5 * validation_total_return
```

Test is recorded only after selection. No Stage C / final heldout rows may be
used.

Current implementation:

- SQLite weekly pool of per-asset SAC subjobs.
- Early stopping by train-tail + validation composite.
- Event-context engineered features.
- First train-only event-token embedding bridge.
- First portfolio supervisor simulator with:
  - equal weight;
  - score weighting;
  - score inverse volatility;
  - score inverse CVaR.

Research question:

What is the most practical next-step portfolio allocation method for weekly
retrained strategy streams, given that expected returns, covariance, and
downside risk must be estimated without knowing the future?

Please research and answer with citations to real sources. Focus on practical
implementability, not theoretical elegance.

Compare:

1. Modern Portfolio Theory / Markowitz mean-variance.
2. Post-modern portfolio theory / downside risk / semivariance / CVaR.
3. Black-Litterman or Bayesian shrinkage variants for unstable expected
   returns.
4. Hierarchical Risk Parity / risk parity for unstable covariance.
5. Kelly/fractional Kelly or volatility targeting for position sizing.
6. Online/rolling portfolio selection methods.
7. ML/meta-allocator approaches using market-state/context embeddings.

For each method, answer:

- What variables are required?
- Which variables can we estimate from our weekly walk-forward pool?
- What data leakage traps exist?
- How much historical lookback is usually needed?
- Does it handle changing regimes?
- Is it suitable for only weekly rebalance?
- How should no-trade flags be incorporated?
- How should transaction costs/spread be included?
- What simple baseline should we implement first?
- What more advanced method should wait until the baseline has evidence?

Important project philosophy:

- Do not recommend broad academic gates that block progress.
- Do not recommend a complex model unless it can be evaluated against a simple
  baseline in the weekly pool.
- Prefer small, testable experiments that can run on our current multi-machine
  pool.
- The final recommendation must become implementable code tasks.

Please provide:

1. Executive recommendation.
2. Ranked method list from most practical now to later.
3. Minimum viable portfolio simulator design.
4. Suggested features for an ML/meta-allocator.
5. Suggested no-trade and max-weight constraints.
6. References/citations.
7. Open questions we must answer with our own data.
