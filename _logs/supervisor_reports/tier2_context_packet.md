# Project 3 Tier 2 Context Packet

generated_at: 2026-05-01T17:24:01Z
project_root: /home/harveybc/Documents/GitHub/financial-data
active_stage: Stage 1.3 Free Data Acquisition
agent_role: Omega Tier 2 OpenCode/Hermes supervisor coordinating Omega, Dragon, and Gamma.
relevant_docs: work_plan/00_PROJECT_3_MASTER_PLAN.md; work_plan/01_AGENT_INFRASTRUCTURE.md; work_plan/13_STAGE_1_3_FREE_DATA_ACQUISITION.md; work_plan/16_STAGE_1_6_VALIDATION_AND_DOCUMENTATION.md
current_machine_tasks:
- Omega: yfinance, HistData from /home/harveybc/Downloads/histdata, CFTC, calendars, metadata aggregation.
- Dragon: Binance top 50 spot, top 10 perpetuals, funding rates.
- Gamma: FRED, CoinMetrics attempts, Blockchain.com, mempool.space, SEC metadata, DeFiLlama, BLS/Treasury, validation inventory.
expected_deliverables: market_data, macro_economic, alternative_data, reference_data, _metadata/acquisition_log.csv, provenance docs, validation inventory.
relevant_logs: _logs/supervisor_reports/global_status.md; _logs/supervisor_reports/autonomous_dispatch_report.md; _logs/omega; remote _logs/dragon; remote _logs/gamma.
constraints: use existing private repo runtime credentials; respect GPU locks; avoid destructive cleanup; sync remote outputs to Omega; escalate only real blockers.
honesty: report evidence, confidence, assumptions, and stale context corrections.
anomaly_detection: stale PIDs, silent logs, failed APIs, missing provenance, abnormal file counts, empty data files, duplicate timestamps, timezone/frequency drift, stale locks, VRAM not released.
improvement_suggestion: every tick should preserve one useful reusable-skill or validation-check suggestion when evidence supports it.
recursive_context_rule: every agent communication must include project_root, active_stage, current_task, expected_deliverable, relevant_docs, relevant_logs, constraints, evidence, anomalies, confidence, and context_to_pass_forward.
