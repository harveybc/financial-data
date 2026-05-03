# Project 3 — Master Plan

**Project name:** Comprehensive Data Acquisition + Feature Engineering + Systematic RL Evaluation
**Predecessor:** Project 2 (closed with marginal RL results on BTC 1h technical features)
**Core hypothesis:** Project 2's null/marginal results were caused by insufficient data diversity, not by RL algorithms being unsuitable. By systematically acquiring ALL plausibly relevant data and engineering ALL state-of-the-art feature representations, we will identify which data combinations and feature representations produce best policies for RL trading agents.

---

## 1. Project Philosophy

This project is **data-centric, perfectionist, and exhaustive**. Three operational principles override everything else:

1. **Data first.** Models are not the bottleneck. Data is. We acquire EVERYTHING plausibly relevant before fitting any new model.
2. **Comprehensive over selective.** When in doubt, include the data source. Filtering happens during experiments (Phase 3), not during acquisition (Phase 1).
3. **Documented and organized.** Every folder has a README. Every dataset has a data dictionary. Future-Harvey or future-agent must be able to understand any folder without context.

---

## 2. Critical Conceptual Distinction (READ CAREFULLY)

This project distinguishes between two fundamentally different concepts that previous projects conflated:

### 2.1 The trading asset and its simulation timeframe

A specific RL experiment trades **ONE asset** at **ONE simulation timeframe**.

- "Trading asset" = the asset whose price is being traded (e.g., BTC/USDT, EUR/USD, SPY)
- "Simulation timeframe" = the bar interval at which the environment steps and the agent acts (e.g., 1h, 4h)
- The trading asset's price series at the simulation timeframe is what the env uses for step() mechanics, P&L, episode termination, etc.

### 2.2 The feature inputs to the agent's observation space

The feature inputs are **multiple, varied, and may have different periodicities than the simulation timeframe.**

- Feature inputs come from many sources: technical features of trading asset, macro indicators, on-chain metrics, sentiment, cross-asset prices, etc.
- Feature inputs may be at simulation timeframe (e.g., 1h technical features when sim is 1h) OR at higher/lower periodicities
- Lower-frequency features (e.g., daily macro, weekly COT reports) are forward-filled to simulation timeframe
- Higher-frequency features (e.g., 5m intra-bar volatility when sim is 1h) are aggregated to simulation timeframe
- The observation space combines all of these as a flat vector (or structured Dict if using attention/transformer policies)

### 2.3 Implications for this project

- Phase 1 acquires data for both purposes (trading asset prices AND feature input sources)
- Phase 2 engineers features at multiple periodicities for use as inputs
- Phase 3 experiments systematically vary:
  - Trading asset (BTC, ETH, EUR/USD, etc.)
  - Simulation timeframe (5m, 15m, 1h, 4h)
  - Feature input sets (which sources included)
  - Feature input periodicities (which periodicities aligned to sim timeframe)

---

## 3. Periodicities Used (DO NOT EXTEND BEYOND THESE)

This project uses ONLY these periodicities:

- **5m** — High-frequency intra-day microstructure level
- **15m** — Intra-day with reduced noise
- **1h** — Standard intra-day, used by Project 2 best results
- **4h** — Multi-bar swing trading scale

**EXPLICITLY EXCLUDED:**
- 1m — Too noisy, microstructure-dominated, requires HFT-grade infrastructure unavailable to retail
- Daily — Sample count too low for RL training; reserved for forward-fill of macro inputs only
- Weekly — Same reason as daily

When forward-filling lower-frequency features (e.g., daily macro, weekly COT) into the simulation timeframe, the lower-frequency data exists but is NOT itself a simulation timeframe.

When data sources only provide daily or weekly granularity (e.g., FRED macro, Glassnode some metrics), those datasets are acquired at native frequency for forward-fill purposes ONLY. They are not used as primary simulation data.

---

## 4. Core Phase Structure

| Phase | Focus | Output |
|-------|-------|--------|
| **Phase 1: Data Acquisition** | Acquire ALL plausibly relevant data sources | Organized data lake with READMEs |
| **Phase 2: Feature Engineering** | Convert raw data into varied feature representations at all periodicities | Standardized feature library |
| **Phase 3: Systematic Experiments** | Use Project 2's best RL agents to evaluate which (asset, sim timeframe, feature set, feature periodicity) combinations produce best policies | Evidence-based ranking |

Phases are sequential. Phase 2 cannot start until Phase 1 produces validated organized data. Phase 3 cannot start until Phase 2 produces feature library.

### 4.1 Deferred Optional Phase 4

| Phase | Focus | Output |
|-------|-------|--------|
| **Phase 4: Synthetic Data Augmentation And Robustness Testing** | Use the best real-data candidates from Phase 3 to test whether train-only synthetic OHLCV augmentation, pretraining, or stress scenarios improve real validation performance | Matched real-only vs synthetic-augmented utility reports |

Phase 4 is optional and deferred. It must not dilute Phase 3's evidence standard. Synthetic data can be used only after candidate configurations are chosen from real-data evidence, and it may not replace real validation or the locked 2025 heldout firewall. See `40_PHASE_4_SYNTHETIC_DATA_AUGMENTATION.md`.

---

## 4.5 Agent Infrastructure (summary — see `01_AGENT_INFRASTRUCTURE.md` for canonical detail)

Project 3 is executed by a multi-tier agent system, not by the user running commands directly. The four tiers are:

1. **Tier 1 — Local Hermes + Gemma 3 31B supervisors** on Dragon and Gamma. Cron-invoked, GPU-lockfile-aware. Watch worker logs, summarize, detect anomalies. Omega does not run a local supervisor (its 8 GB VRAM is insufficient for the 31B model); Omega's logs are watched directly by Tier 2.
2. **Tier 2 — OpenCode Go meta-supervisor** on Omega. Cron-capped to one tick every 10–15 min. Aggregates Tier 1 reports, maintains the escalation queue, dispatches tasks across machines, owns the git repo.
3. **Tier 3 — Bounded local automated coding.** Hermes + Gemma 31B running on Dragon or Gamma (whichever has lighter load), with strict ceilings: max 3 attempts per escalation, max 2 files per attempt, 30 min wall-clock per attempt. If confidence falls below 0.7 or attempts exhaust, escalation hands off to Tier 4. **No automated frontier API calls** — that was deliberately removed in v2 of the architecture to avoid runaway-loop costs and confidently-wrong frontier-model commits.
4. **Tier 4 — Human-in-the-loop with frontier tools.** User reads structured handoff documents from Tier 3 and applies fixes using their preferred frontier tool. Recommended primary: **ChatGPT Pro Plus + Codex in VS Code (GPT-5.5 Pro)**, ~$200/month flat. Alternative: **VS Code Copilot Opus 4.7** (existing 15× quota subscription). Plus Claude Pro/Max chat for planning conversations and second opinions. **All frontier model use is human-driven; no automated API calls anywhere in the loop.**

Critical rules from this architecture:

- **GPU lockfile (`/tmp/gpu_busy.lock`)** is mandatory for all heavy GPU jobs to prevent contention with local Hermes supervisors. See infrastructure doc §4.
- **Auto-validation is the default.** When the user confirms a manual prerequisite (e.g., "HistData downloads complete"), agents proceed automatically. Only blockers ping the user.
- **The user does not run validation commands.** Stage docs do not instruct file counting, coverage checks, or schema verification by the user. Those are agent responsibilities.
- **Deliverable validation is work-plan-backed.** Agents must read the exact task spec, inspect produced artifacts/provenance/logs, and route uncertainty to Tier 4/Codex instead of guessing.
- **Cloud supervisors are allowed if they reduce GPU contention.** The canonical infrastructure doc tracks the optional Ollama Cloud Pro path for Tier 1/Tier 3 supervisor inference. Dragon/Gamma use `deepseek-v4-flash:cloud` as the recurring Tier 1 model with `gemma4:31b-cloud` fallback, while Omega Tier 2 keeps using the existing OpenCode DeepSeek V4 Pro supervisor path. DeepSeek Pro is reserved for Omega/OpenCode and hard escalations because it is slower and less predictable for 5-minute heartbeats. This is not a frontier API path; it is a fixed-price open-model subscription option and must be recorded in `_metadata/ai_subscriptions.json` if enabled.

For machine roles, model details, escalation queue schema, GPU lockfile protocol, cron frequencies, and bootstrap procedure: read `01_AGENT_INFRASTRUCTURE.md`.

---

## 5. Document Index

This project is organized as multiple short documents (idiot-proof for inferior agent models). Read only the document for the stage being executed.

### Master
- `00_PROJECT_3_MASTER_PLAN.md` — This document
- `01_AGENT_INFRASTRUCTURE.md` — **Canonical reference** for the multi-tier agent infrastructure (machines, models, GPU lockfile, escalation queue). Every stage doc assumes familiarity with this file.

### Phase 1: Data Acquisition
- `10_PHASE_1_OVERVIEW.md` — Phase 1 goals and dependencies
- `11_STAGE_1.1_STORAGE_ARCHITECTURE.md` — Folder structure, naming conventions, README templates
- `12_STAGE_1.2_DATA_CATALOG.md` — Exhaustive list of every data source to acquire
- `13_STAGE_1.3_FREE_DATA_ACQUISITION.md` — Procedures for free data sources
- `14_STAGE_1.4_REGISTRATIONS_AND_KEYS.md` — Manual user actions
- `15_STAGE_1.5_PAID_DATA_ACQUISITION.md` — Procedures for subscription-based sources
- `16_STAGE_1.6_VALIDATION_AND_DOCUMENTATION.md` — Per-folder validation and READMEs

### Phase 2: Feature Engineering
- `20_PHASE_2_OVERVIEW.md` — Phase 2 goals
- `21_STAGE_2.1_DOWNSAMPLING_AND_RESAMPLING.md` — Multi-timeframe generation
- `22_STAGE_2.2_TECHNICAL_AND_STATISTICAL_FEATURES.md` — Standard + advanced features
- `23_STAGE_2.3_SIGNAL_DECOMPOSITION_FEATURES.md` — Wavelet, Hilbert, multitaper, EMD
- `24_STAGE_2.4_LEARNED_REPRESENTATIONS.md` — Autoencoders + embeddings

### Phase 3: Systematic Experiments
- `30_PHASE_3_OVERVIEW.md` — Phase 3 goals
- `31_STAGE_3.1_EXPERIMENT_FRAMEWORK.md` — How to test data subsets systematically
- `32_STAGE_3.2_RESULTS_SYNTHESIS.md` — How findings get aggregated

### Phase 4: Deferred Synthetic Data Augmentation
- `40_PHASE_4_SYNTHETIC_DATA_AUGMENTATION.md` — Optional post-Phase-3 synthetic OHLCV augmentation and robustness protocol
- `SYNTHETIC_DATAGEN_SPECKIT_COPILOT_PROMPT.md` — Spec Kit/Copilot prompt for a plugin-first synthetic OHLCV generator suite

Total: 17 canonical/project-adjacent documents (master + agent infrastructure + 13 Phase 1-3 docs + Phase 4 plan + synthetic generator prompt).

---

## 6. Standing Rules (Apply to ALL Stages)

### Rule M.1: Read only the relevant document

Agent reads master plan + `01_AGENT_INFRASTRUCTURE.md` + the specific stage document being executed. Does not attempt to read all documents at once. Does not skip ahead. The agent infrastructure doc is required reading for every stage because tier routing, GPU lockfile protocol, and the escalation queue all live there.

### Rule M.2: Each stage has a user gate

After completing a stage, agent produces stage deliverable, HALTS, and waits for user approval before next stage.

### Rule M.3: Held-out data discipline

Project 3 acquires data through end of 2025 (latest available). Held-out boundary set at:

```
HELD_OUT_BOUNDARY = "2025-01-01"
IN_SAMPLE_END     = "2024-12-31"
HELD_OUT_END      = "2025-12-31"
```

In Phase 3 experiments, data from 2025-01-01 onward is held-out and touched exactly once per final candidate.

(Note: Boundary differs from Project 2 because Project 3 has access to data through end of 2025, providing a full year of held-out post-IS-end. Pre-registered for transparency.)

### Rule M.4: Organization is non-negotiable

Every folder MUST have:
- `README.md` describing contents
- `data_dictionary.md` if folder contains datasets (column descriptions, units, source, date ranges)
- `provenance.json` (machine-readable: source URL, acquisition date, license, version)

Folders without these three files are considered incomplete and trigger ESCALATION.

### Rule M.5: Quality over speed

This project explicitly rejects "fast and mediocre." If a stage takes 3× longer to do correctly, do it correctly. Time budget non-binding (per user direction).

### Rule M.6: No invented techniques

For Phase 2 feature engineering, every technique used MUST cite published source (Jansen, Lopez de Prado, Chan, Tsay, or peer-reviewed paper). No "I think this might work" features. State of the art only.

### Rule M.7: Idiot-proof execution

Each stage document is written assuming agent has zero project context except master plan + stage document. Cross-references explicit. Procedures step-by-step. No assumptions about implicit knowledge.

### Rule M.8: SSH + conda activation pattern (READ CAREFULLY)

The conda environment named `tensorflow` is auto-activated via `.bashrc` on all 3 machines (Omega, Dragon, Gamma). The `.bashrc` also configures CUDA paths required for GPU access.

**For SSH connections, behavior depends on shell type:**

- **Interactive SSH session** (`ssh user@host` then run commands at prompt): `.bashrc` IS sourced automatically. Conda env IS active. Do NOT manually activate again — double activation produces errors.

- **Non-interactive SSH command** (`ssh user@host "command"`): `.bashrc` is typically NOT sourced because non-interactive shells skip `.bashrc` early. Manual activation IS required.

**Decision rule for agent:**

When using `ssh host "command"` form (non-interactive, the standard automation pattern), prepend conda activation:

```bash
ssh host "source /home/harveybc/anaconda3/etc/profile.d/conda.sh && conda activate tensorflow && <command>"
```

When connecting via interactive session and pasting commands, do NOT activate (already active from .bashrc).

**Verification step:** Before any series of remote commands, agent runs verification:

```bash
ssh host "echo \$CONDA_DEFAULT_ENV"
```

If output is `tensorflow`, env active (don't re-activate).
If output is empty, env not active (activate before each command).

### Rule M.9: Storage assumed unlimited

User has confirmed sufficient disk space. Do not optimize for storage. Acquire everything that has plausible value.

### Rule M.10: Cost ceiling AND mediocrity rejection

Maximum subscription cost: **$500/month combined across all paid sources**.

**Mediocrity rule:** If a paid source turns out to be mediocre (incomplete data, frequent API failures, less coverage than promised, or simply not adding unique value over free alternatives), cancel the subscription immediately upon discovery. Document the cancellation in `_metadata/subscriptions.json` with reason. Do NOT keep paying for low-quality data out of inertia.

Triggers for cancellation evaluation:
- Coverage substantially less than catalog promised
- Data quality fails validation tests Stage II-0b style
- API returns 5XX errors >5% of requests for >1 week
- Equivalent or better data available free elsewhere
- After Phase 3 experiments, source's data shown to provide no improvement to RL agent performance

Reject in advance: Bloomberg Terminal ($24K/yr), Refinitiv ($22K/yr), institutional-only feeds (no clear advantage justifying cost). Use Polygon.io, Glassnode, CryptoQuant, FMP — all under $500/month combined.

### Rule M.11: Periodicities used are 5m, 15m, 1h, 4h ONLY

For trading asset price data and primary simulation timeframes, only these four periodicities are used. Daily and weekly data acquired ONLY when source provides natively at that frequency (e.g., FRED macro is daily-or-lower) and used for forward-fill into 5m/15m/1h/4h observation vectors.

1m data is NOT acquired (too noisy for our research scope).

### Rule M.12: This project does NOT predict signals

Project 3 supplies data to RL agents that learn trading policies. The agents do NOT predict future returns, classify direction, or forecast prices. The agents observe state (built from data) and choose actions (buy/sell/hold) to maximize cumulative reward.

When this plan or any document discusses "data value" or "useful data," the criterion is: "does including this data in the observation space help the RL agent learn a better policy?" — NOT "does this data predict future returns?"

This distinction matters because:
- IC analysis (Project 2 used) measures predictive value, not necessarily RL policy value
- Causal analysis (PCMCI+) detects predictive structure, but agent may exploit non-predictive aspects (regime indicators, position state)
- Some data with no predictive value may still help agent (e.g., volatility regime indicators stabilize policy)

Phase 3 experiment framework evaluates data by RL agent performance on held-out, NOT by predictive value of data.

### Rule M.13: Agent tier discipline

All work runs through the four-tier agent infrastructure defined in `01_AGENT_INFRASTRUCTURE.md` (architecture v2). Tier 1 (local Hermes/Gemma supervisors on Dragon and Gamma, cron-invoked) handles log watching. Tier 2 (OpenCode Go on Omega, cron-capped to 10–15 min) orchestrates and maintains the escalation queue. Tier 3 (bounded local Hermes + Gemma 31B, max 3 attempts per escalation, max 2 files per attempt) handles in-scope coding tasks. Tier 4 (user with ChatGPT 5.5 Pro via Codex / Copilot Opus 4.7 / Claude Max) handles plan decisions, synthesis, and any task outside Tier 3 ceilings.

Stages do not bypass tiers. A Python worker does not directly call a frontier model; it produces logs, Tier 1 watches, Tier 2 routes, Tier 3 acts within ceilings, Tier 4 (the human) is the only path to frontier models. This discipline keeps cost predictable and keeps the escalation queue accurate.

### Rule M.14: GPU lockfile is mandatory

Every heavy GPU job (RL training, autoencoder training, multitaper, EMD on long series, anything that allocates >2 GB VRAM) MUST acquire `/tmp/gpu_busy.lock` before starting and release it on exit. Tier 1 supervisors check this lockfile before loading the local Gemma model. Heavy jobs that skip the lockfile cause OOM crashes that take down both the job and the supervisor.

The standard helper is `_scripts/lib/gpu_lock.py` (defined in `01_AGENT_INFRASTRUCTURE.md` §4.3). All training and feature-engineering scripts MUST use it.

### Rule M.15: Auto-validation is the default

Per user direction, validation runs in **full auto mode**. When the user confirms a manual prerequisite is complete (HistData downloads, API keys, etc.), agents proceed through validation, deliverable generation, and downstream prep without further user intervention. Only blockers (per `01_AGENT_INFRASTRUCTURE.md` §9) ping the user.

Stage documents do NOT instruct the user to run validation commands like `ls | wc -l`. Those commands are the agents' responsibility. Stage documents that still contain such instructions are documentation bugs and should trigger an escalation tagged `plan_decision_proposal`.

Validation must compare the produced deliverable against the exact work-plan task that required it. A folder existing is not enough. A worker log saying "done" is not enough. Required evidence is: relevant work-plan section, deliverable path, README/data dictionary/provenance where applicable, acquisition/validation logs, and confidence. If confidence is below 0.8 or the task requirement is ambiguous, the supervisor writes a Codex/Tier 4 escalation instead of guessing.

---

## 7. Reference Books and Sources

The data catalog (Stage 1.2) and feature engineering (Phase 2) draw from:

| Reference | Focus |
|-----------|-------|
| Jansen, "Machine Learning for Algorithmic Trading" 2nd ed (2020) | Primary reference. Comprehensive data sources |
| Lopez de Prado, "Advances in Financial Machine Learning" (2018) | Microstructure, fractional differentiation, meta-labeling |
| Chan, "Machine Trading" (2017) + "Algorithmic Trading" (2013) | Practical strategy construction |
| Tsay, "Analysis of Financial Time Series" 3rd ed (2010) | Statistical methods, GARCH, regime models |

Plus selected papers per technique cited in stage documents.

---

## 8. Connection to Project 2 Outputs

Project 3 USES (does not redo):

- Project 2 RL infrastructure (gym-fx + agent-multi)
- Project 2 best-performing model configurations as starting points for Phase 3 experiments
- Project 2 evaluation framework (F-10 kill criteria, DSR with multiple-testing correction, IS/HO discipline)
- Project 2 lessons (no synthetic data, sanity checks mandatory, etc.)

Project 3 DOES NOT redo Project 2's algorithm research. Models from Project 2 are tools for testing data, not subjects of further investigation.

---

## 9. Project 3 Final Deliverable

After Phase 3 completes:

`PROJECT_3_FINAL_REPORT.md` answers:

1. Which combinations of (trading asset, simulation timeframe, feature input set) produced highest RL policy performance?
2. Which feature engineering techniques contributed most to policy quality?
3. Which feature input periodicities (forward-filled or aggregated) added value?
4. What is the realistic Sharpe achievable with optimal data + Project 2 best models?
5. Which data sources turned out to be non-contributory (and were cancelled if paid)?
6. What gaps remain (data not acquired, techniques not tested) for future projects?

This report becomes the foundation for any future Project 4.

---

## 10. Risk Acknowledgments

1. **Probability that Project 3 still produces marginal/null results: estimated 25-35%.** Even with comprehensive data, retail-accessible markets may not have systematic exploitable edge for RL at the scales we're working. Lower than Project 2 estimate due to broader data scope, but still real risk.

2. **Some data sources may not deliver promised value despite cost.** Phase 3 experiments will identify these; Phase 1 acquires defensively, Rule M.10 cancels mediocre subscriptions.

3. **Feature engineering complexity is large.** Phase 2 has 4 sub-stages with state-of-the-art techniques. Inferior agent may struggle with implementation; user manual work expected for advanced parts.

4. **Time investment is substantial.** Even with unlimited compute, manual user tasks (registrations, subscription decisions, feature engineering review) require user time.

---

## 11. Approval to Begin

User approves master plan. Agent begins by reading `10_PHASE_1_OVERVIEW.md`.
