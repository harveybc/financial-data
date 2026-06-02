# Project 3 Trade-Frequency Regulatory Review Prompt

Date: 2026-05-15

Use this prompt with ChatGPT 5.5 Pro Web. This is a research memo task only;
it must not mutate code, launch training, or inspect Stage C data.

## Files To Attach

Attach these files from `financial-data`:

1. `work_plan/PROJECT3_SAC_NSGA_INPUT_OPTIMIZATION_PROTOCOL_2026_05_14.md`
2. `work_plan/PROJECT3_STAGE3X_CHATGPT55_PRO_RESEARCH_REVIEW.md`
3. `experiments/stage3x_sac_smoke_results/stage3x_sac_smoke_result_synthesis.md`
4. `experiments/stage_b_validation/hardening/trade_behavior_report.csv`
5. `experiments/stage_b_validation/hardening/stage_b_decision_readiness.md`

## Prompt

You are an external regulatory/research reviewer for Project 3. You do not
have repo access beyond the files I attach. Treat this as research and policy
guidance, not trading advice and not code mutation.

Project context:

- Project 3 is now focused on SAC-first input/data/preprocessing optimization.
- Stage C is a one-shot heldout firewall and must remain locked.
- We are evaluating whether trade-frequency objectives should change because
  U.S. FINRA pattern day trader rules are being replaced in 2026.
- We also need OANDA-specific constraints because the intended live execution
  path may use OANDA FX/crypto rather than U.S. stock/options brokers.
- We currently use trade-behavior gates for no-trade, excessive trades,
  always-in-market losing, Friday force-close exposure, and cost fragility.

Primary-source research task:

1. Verify the current status of the FINRA/SEC Pattern Day Trader rule change:
   - what SEC approved;
   - exact effective date;
   - phase-in / broker transition date;
   - what is eliminated;
   - what replaces it;
   - what still constrains traders after the change.
2. Explain whether this PDT change applies to:
   - U.S. equity margin accounts;
   - U.S. options margin accounts;
   - cash accounts;
   - spot FX / retail forex;
   - crypto spot;
   - OANDA U.S. forex/crypto.
3. Research OANDA U.S. constraints from official OANDA docs:
   - any max trades per day, if one exists;
   - max open trades/orders;
   - position/account exposure limits;
   - API request/connection limits;
   - FIFO or hedging constraints;
   - market hours, Friday close, daily maintenance breaks;
   - margin closeout behavior.
4. Translate the regulatory findings into Project 3 design guidance:
   - recommended target trade-rate bands per week for FX 4h, FX 1h, crypto
     4h, crypto 1h;
   - maximum trade-rate hard gates for research;
   - Friday force-close timing policy for OANDA FX, including New York time
     and daylight-saving implications;
   - whether 3 trades/week, 6 trades/week, 12 trades/week, 24 trades/week,
     or more should be used as objective bands.
5. Clearly separate:
   - actual legal/regulatory constraints;
   - broker/platform technical constraints;
   - project policy constraints designed to prevent overtrading;
   - speculative recommendations.

Important:

- Use primary sources where possible: FINRA, SEC, Federal Register, Investor.gov,
  OANDA official docs, CFTC/NFA if relevant.
- Do not rely on YouTube, Reddit, or blogs except as leads to primary sources.
- Do not suggest unlocking Stage C.
- Do not suggest increasing trade frequency merely because PDT is changing.
- Prefer a conservative policy that protects against spread, slippage, rollover,
  margin closeout, and operational risk.

Output:

- Markdown memo with links.
- A table of rules/constraints by market type.
- A recommended Project 3 trade-frequency policy.
- A final checklist suitable for converting into coding tasks.
