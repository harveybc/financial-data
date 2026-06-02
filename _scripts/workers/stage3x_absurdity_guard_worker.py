#!/usr/bin/env python3
"""Fail-closed guard against wasteful Project 3 GPU/search work.

This worker consolidates the lessons from the no-promotion Stage B cycle into
machine-readable launch blockers. It does not launch or stop training; it emits
the conditions that must be satisfied before broad GPU work is justified.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HARDENING = ROOT / "experiments" / "stage_b_validation" / "hardening"
STAGE3X = ROOT / "experiments" / "stage3x_input_preprocessing_optimization"
OUT_ROOT = ROOT / "experiments" / "stage3x_absurdity_guard"
OUT_JSON = OUT_ROOT / "stage3x_absurdity_guard_report.json"
OUT_MD = OUT_ROOT / "stage3x_absurdity_guard_report.md"

STAT_REPORT = HARDENING / "stageb_dsr_pbo_report.json"
ACTION_AUDIT = HARDENING / "stage_b_feature_action_audit.json"
DECISION_READINESS = HARDENING / "stage_b_decision_readiness.json"
INPUT_PLAN = STAGE3X / "stage3x_input_preprocessing_optimization_plan.json"
PARAMETRIC_SCHEMA = (
    ROOT
    / "experiments"
    / "stage3x_parametric_data_space"
    / "project3_data_preprocessing_search_space.schema.json"
)
SELECTED_CONTRACTS = (
    ROOT
    / "experiments"
    / "stage3x_target_relation_screen"
    / "selected_feature_contracts.json"
)
SMOKE_SYNTHESIS = (
    ROOT
    / "experiments"
    / "stage3x_sac_smoke_results"
    / "stage3x_sac_smoke_result_synthesis.json"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def add_issue(
    issues: list[dict[str, Any]],
    code: str,
    severity: str,
    message: str,
    action: str,
    evidence: Any = None,
) -> None:
    issues.append(
        {
            "code": code,
            "severity": severity,
            "message": message,
            "required_action": action,
            "evidence": evidence,
        }
    )


def build_report() -> dict[str, Any]:
    stat = load_json(STAT_REPORT)
    audit = load_json(ACTION_AUDIT)
    readiness = load_json(DECISION_READINESS)
    input_plan = load_json(INPUT_PLAN)
    schema = load_json(PARAMETRIC_SCHEMA)
    selected_contracts = load_json(SELECTED_CONTRACTS)

    stat_summary = stat.get("summary", {})
    issues: list[dict[str, Any]] = []

    if bool(stat_summary.get("stage_c_allowed")):
        add_issue(
            issues,
            "FATAL_STAGE_C_ALLOWED_BEFORE_PROMOTION",
            "fatal",
            "Stage C is marked allowed before a Stage B candidate cleared all hard gates.",
            "Re-lock Stage C and inspect evaluator/approval gate wiring.",
            stat_summary,
        )

    if int(stat_summary.get("candidate_gate_pass") or 0) == 0:
        add_issue(
            issues,
            "NO_STAGE_B_PROMOTION",
            "block_broad_gpu",
            "No candidate cleared Stage B; broad reruns of the same contract are not justified.",
            "Run data/preprocessing target-relation screening before any new broad GPU batch.",
            {
                "candidate_gate_fail": stat_summary.get("candidate_gate_fail"),
                "dsr_fail_n_raw": stat_summary.get("dsr_fail_n_raw"),
            },
        )

    missing_hash = int(audit.get("feature_list_hash_missing_candidates") or 0)
    if missing_hash:
        add_issue(
            issues,
            "MISSING_FEATURE_HASHES",
            "block_broad_gpu",
            "One or more audited candidates lack deterministic feature_list_hash evidence.",
            "Require non-null feature_list_hash and observation_state_hash for future traces.",
            {"feature_list_hash_missing_candidates": missing_hash},
        )

    largest_identical = int(audit.get("largest_identical_performance_group") or 0)
    if largest_identical >= 5:
        add_issue(
            issues,
            "FEATURE_INSENSITIVE_POLICY_SIGNATURE",
            "block_broad_gpu",
            "Many distinct data hashes produced identical action/trade/performance signatures.",
            "Do not rerun the same feature contract; diagnose observation/preprocessing and run CPU feature screens.",
            {"largest_identical_performance_group": largest_identical},
        )

    if not input_plan:
        add_issue(
            issues,
            "MISSING_INPUT_PREPROCESSING_PLAN",
            "block_gpu",
            "No active Stage 3X input/preprocessing optimization plan exists.",
            "Generate stage3x_input_preprocessing_optimization_plan_worker output before GPU work.",
            str(INPUT_PLAN),
        )

    if not schema:
        add_issue(
            issues,
            "MISSING_PARAMETRIC_DATA_SCHEMA",
            "block_gpu",
            "No parametric data/preprocessing search-space schema exists.",
            "Run stage3x_parametric_data_space_worker.py before DEAP/NSGA search.",
            str(PARAMETRIC_SCHEMA),
        )

    selected_count = len(selected_contracts.get("contracts", [])) if selected_contracts else 0
    if selected_count <= 0:
        add_issue(
            issues,
            "MISSING_SELECTED_FEATURE_CONTRACTS",
            "block_smoke_gpu",
            "No CPU-screened selected feature contracts exist for SAC smoke testing.",
            "Run stage3x_target_relation_screen_worker.py before any SAC smoke plan.",
            str(SELECTED_CONTRACTS),
        )

    readiness_counts = readiness.get("cluster_summary", {}).get("counts", {})
    if int(readiness_counts.get("running") or 0) > 0:
        add_issue(
            issues,
            "RUNS_STILL_ACTIVE",
            "wait",
            "One or more Stage B jobs are still active.",
            "Wait for completion before interpreting aggregate evidence.",
            readiness_counts,
        )

    # FINRA/OANDA broker-profile + trade-frequency policy layer
    # (PROJECT3_FINRA_OANDA_TRADE_FREQUENCY_POLICY_MEMO). Any time a smoke
    # contract is missing its broker profile, has policy fields stamped UNKNOWN,
    # or trips the per-week hard max, broad GPU launch must remain blocked.
    smoke = load_json(SMOKE_SYNTHESIS)
    contract_summary = smoke.get("contract_summary") or []
    contracts_missing_broker = [
        c["contract_id"]
        for c in contract_summary
        if "BROKER_PROFILE_MISSING_OR_UNCONFIRMED" in (c.get("blockers") or [])
    ]
    contracts_over_hard_max = [
        c["contract_id"]
        for c in contract_summary
        if "TRADE_FREQUENCY_HARD_MAX_EXCEEDED" in (c.get("blockers") or [])
    ]
    contracts_with_oanda_fx_violation = [
        c["contract_id"]
        for c in contract_summary
        if (
            "OANDA_FX_FRIDAY_FORCE_FLAT_VIOLATION" in (c.get("blockers") or [])
            or "OANDA_FX_DAILY_BREAK_TRADE_ATTEMPT" in (c.get("blockers") or [])
        )
    ]
    contracts_with_no_policy_band = [
        c["contract_id"]
        for c in contract_summary
        if "TRADE_FREQUENCY_POLICY_UNKNOWN_FOR_TIMEFRAME" in (c.get("warnings") or [])
    ]
    if contracts_missing_broker:
        add_issue(
            issues,
            "BROKER_PROFILE_MISSING_OR_UNCONFIRMED",
            "block_broad_gpu",
            "One or more smoke contracts have an unconfirmed broker/venue profile.",
            "Confirm OANDA vs exchange venue for every spot-crypto contract before broad GPU launch.",
            {"contracts": sorted(contracts_missing_broker)[:10], "count": len(contracts_missing_broker)},
        )
    if contracts_over_hard_max:
        add_issue(
            issues,
            "TRADE_FREQUENCY_HARD_MAX_EXCEEDED",
            "block_broad_gpu",
            "One or more smoke contracts exceeded the broker/timeframe trade-rate hard cap.",
            "Reduce trade frequency, adjust cost model, or reclassify the broker profile before relaunching.",
            {"contracts": sorted(contracts_over_hard_max)[:10], "count": len(contracts_over_hard_max)},
        )
    if contracts_with_oanda_fx_violation:
        add_issue(
            issues,
            "OANDA_FX_CALENDAR_VIOLATION",
            "block_broad_gpu",
            "OANDA FX smoke trace shows Friday force-flat or daily-break trade attempts.",
            "Add the calendar/force-close observation fields and verify policy respects 15:45 NY flat / 16:59-17:05 NY break.",
            {"contracts": sorted(contracts_with_oanda_fx_violation)[:10], "count": len(contracts_with_oanda_fx_violation)},
        )
    if contracts_with_no_policy_band and smoke:
        add_issue(
            issues,
            "TRADE_FREQUENCY_POLICY_BAND_MISSING",
            "block_smoke_gpu",
            "Smoke contracts exist for timeframes not covered by the trade-frequency policy table.",
            "Extend TRADE_FREQUENCY_POLICY in stage3x_sac_smoke_result_synthesis_worker.py for the new timeframe before further smoke runs.",
            {"contracts": sorted(contracts_with_no_policy_band)[:10], "count": len(contracts_with_no_policy_band)},
        )

    fatal = any(row["severity"] == "fatal" for row in issues)
    block_gpu = any(row["severity"] in {"fatal", "block_gpu", "block_broad_gpu"} for row in issues)
    block_smoke = any(row["severity"] in {"fatal", "block_gpu", "block_smoke_gpu"} for row in issues)
    return {
        "schema_version": "project3_stage3x_absurdity_guard_v2_finra_oanda",
        "generated_at": utc_now(),
        "training_launched": False,
        "stage_c_access": "DENIED",
        "fatal_issue_present": fatal,
        "broad_gpu_launch_allowed": not block_gpu,
        "small_sac_smoke_allowed": not block_smoke,
        "small_cpu_or_dry_run_allowed": True,
        "selected_feature_contract_count": selected_count,
        "smoke_contract_count": len(contract_summary),
        "smoke_contracts_missing_broker_profile": contracts_missing_broker,
        "smoke_contracts_over_trade_frequency_hard_max": contracts_over_hard_max,
        "smoke_contracts_with_oanda_fx_calendar_violation": contracts_with_oanda_fx_violation,
        "smoke_contracts_with_unknown_policy_band": contracts_with_no_policy_band,
        "issue_count": len(issues),
        "issues": issues,
        "source_files": {
            "stat_report": str(STAT_REPORT),
            "action_audit": str(ACTION_AUDIT),
            "decision_readiness": str(DECISION_READINESS),
            "input_plan": str(INPUT_PLAN),
            "parametric_schema": str(PARAMETRIC_SCHEMA),
            "selected_contracts": str(SELECTED_CONTRACTS),
            "smoke_synthesis": str(SMOKE_SYNTHESIS),
        },
    }


def write_report(payload: dict[str, Any]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Stage 3X Absurdity Guard",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched by this worker: `{payload['training_launched']}`",
        f"- Broad GPU launch allowed: `{payload['broad_gpu_launch_allowed']}`",
        f"- Small SAC smoke allowed: `{payload['small_sac_smoke_allowed']}`",
        f"- Selected feature contracts: `{payload['selected_feature_contract_count']}`",
        f"- Smoke contracts summarized: `{payload.get('smoke_contract_count', 0)}`",
        f"- Smoke contracts missing broker profile: `{len(payload.get('smoke_contracts_missing_broker_profile', []))}`",
        f"- Smoke contracts over trade-frequency hard max: `{len(payload.get('smoke_contracts_over_trade_frequency_hard_max', []))}`",
        f"- Smoke contracts with OANDA FX calendar violation: `{len(payload.get('smoke_contracts_with_oanda_fx_calendar_violation', []))}`",
        f"- Small CPU/dry-run work allowed: `{payload['small_cpu_or_dry_run_allowed']}`",
        f"- Issues: `{payload['issue_count']}`",
        "",
        "## Issues",
        "",
        "| severity | code | required action |",
        "| --- | --- | --- |",
    ]
    for issue in payload["issues"]:
        lines.append(
            f"| `{issue['severity']}` | `{issue['code']}` | {issue['required_action']} |"
        )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    payload = build_report()
    write_report(payload)
    print(
        json.dumps(
            {
                "ok": True,
                "broad_gpu_launch_allowed": payload["broad_gpu_launch_allowed"],
                "issue_count": payload["issue_count"],
                "report_json": str(OUT_JSON),
                "report_md": str(OUT_MD),
                "training_launched": False,
                "stage_c_access": "DENIED",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
