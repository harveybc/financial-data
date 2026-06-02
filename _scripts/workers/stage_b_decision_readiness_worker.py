#!/usr/bin/env python3
"""Project 3 Stage B decision-readiness dashboard.

This worker is intentionally read-only with respect to training. It consolidates
the Stage B statistical evaluator, approval packet, and cluster live-status into
one fail-closed readiness artifact. Its main purpose is to prevent ambiguous
"what next?" orchestration: if Stage C is blocked, the report names the exact
hard blockers and the next implementation/evidence actions.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HARDENING_DIR = ROOT / "experiments" / "stage_b_validation" / "hardening"
OUT_JSON = HARDENING_DIR / "stage_b_decision_readiness.json"
OUT_MD = HARDENING_DIR / "stage_b_decision_readiness.md"

STAGEB_STAT_REPORT = HARDENING_DIR / "stageb_dsr_pbo_report.json"
APPROVAL_PACKET = ROOT / "experiments" / "stage_a_screening" / "stage_b_approval" / "stage_b_approval_packet.json"
CLUSTER_STATUS = ROOT / "experiments" / "stage_b_validation" / "run_plan" / "stage_b_cluster_live_status.json"
RUN_PLAN_STATUS = ROOT / "experiments" / "stage_b_validation" / "run_plan" / "stage_b_run_plan_status.json"
HANDOFF_SPEC = ROOT / "work_plan" / "PROJECT3_AGENT_HANDOFF_SPEC_KIT_2026_05_12.md"

HELDOUT_START = "2025-01-01"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def blocker_counts_from_approval(approval: dict[str, Any]) -> Counter:
    counts: Counter = Counter()
    for row in approval.get("all_candidates", []):
        for blocker in row.get("blockers", []):
            code = blocker.get("blocker_code") if isinstance(blocker, dict) else None
            if code:
                counts[str(code)] += 1
    return counts


def blocker_counts_from_stat(stat: dict[str, Any]) -> Counter:
    counts: Counter = Counter()
    for gate in stat.get("candidate_gates", {}).values():
        for reason in gate.get("blocking_reasons", []):
            counts[str(reason)] += 1
    return counts


def top_blocked_candidates(approval: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    rows = approval.get("top_blocked_by_return") or []
    out: list[dict[str, Any]] = []
    for row in rows[:limit]:
        out.append({
            "run_slug": row.get("run_slug", ""),
            "stage_b_status": row.get("stage_b_status", ""),
            "total_return": row.get("total_return"),
            "sharpe_ratio": row.get("sharpe_ratio"),
            "blocker_codes": [
                str(blocker.get("blocker_code"))
                for blocker in row.get("blockers", [])
                if isinstance(blocker, dict) and blocker.get("blocker_code")
            ],
        })
    return out


def action_for_blocker(code: str) -> str:
    mapping = {
        "DSR_RIGOROUS_FAIL": (
            "Review per-bar net-return traces, N_raw/N_eff policy, skew/kurtosis, "
            "and autocorrelation adjustment; candidate cannot advance until rigorous DSR clears."
        ),
        "PBO_DEFERRED_OR_FAIL": (
            "Implement or run purged/embargoed CSCV/PBO evidence; current PBO-lite gate is blocking."
        ),
        "FAMILY_REALITY_CHECK_FAIL": (
            "Review matched baseline/family bootstrap tests; raw return is not enough if family-level data-snooping test fails."
        ),
        "SEED_UNCERTAINTY_BLOCKED": (
            "Provide paired seed evidence, minimum five seeds per candidate/cost scenario, or keep blocked."
        ),
        "MISSING_COST_SCENARIO": (
            "Generate both base and pessimistic cost-scenario evidence for the same candidate identity."
        ),
        "STAGEB_STAT_EVIDENCE_MISSING": (
            "Produce agent-multi evidence.json and return traces, then re-run the Stage B evaluator."
        ),
        "EVIDENCE_INVALID_OR_MISSING": (
            "Repair missing/bad evidence, trace hashes, metadata sidecars, or schema/version mismatches."
        ),
        "FINAL_NO_TRADES": (
            "Reject or repair no-trade configuration before rerun; do not count no-trade output as useful evidence."
        ),
        "FINAL_EXCESSIVE_TRADES_HARD": (
            "Reject or constrain pathological overtrading; hard trade-rate gate exceeded."
        ),
        "FINAL_ALWAYS_IN_MARKET_LOSING": (
            "Reject or diagnose always-in-market losing policy; exposure gate is hard blocking."
        ),
        "BASELINE_FAIL": (
            "Candidate must beat matched simple baselines under required cost scenarios."
        ),
        "ABLATION_FAIL": (
            "Feature/source family must show marginal value versus matched ablation."
        ),
        "NON_POSITIVE_RETURN": (
            "Killed by hardening. Do not rerun blindly; only create a new counted trial if a documented parameter/data defect is found."
        ),
        "NO_TRADES": (
            "Killed by hardening. Diagnose action deadband/hold-collapse from trace logs before any remediation rerun; no-trade output is not evidence."
        ),
        "NEGATIVE_SHARPE": (
            "Killed by hardening. Do not promote; investigate only if needed for failure analysis or a new counted trial design."
        ),
    }
    return mapping.get(code, f"Inspect blocker `{code}` and produce the missing hard-gate evidence.")


def build_readiness(
    stat: dict[str, Any],
    approval: dict[str, Any],
    cluster: dict[str, Any],
    run_plan: dict[str, Any],
) -> dict[str, Any]:
    stat_summary = stat.get("summary", {}) if isinstance(stat, dict) else {}
    approval_summary = approval.get("summary", {}) if isinstance(approval, dict) else {}
    cluster_counts = cluster.get("counts", {}) if isinstance(cluster, dict) else {}

    stat_stage_c_allowed = bool(stat_summary.get("stage_c_allowed"))
    approval_ready = int(approval_summary.get("n_stage_b_ready") or 0)
    can_enter_stage_c = stat_stage_c_allowed and approval_ready > 0

    stat_blockers = blocker_counts_from_stat(stat)
    approval_blockers = blocker_counts_from_approval(approval)
    combined = Counter()
    combined.update(stat_blockers)
    combined.update(approval_blockers)

    hard_reasons: list[str] = []
    if not stat:
        hard_reasons.append("STAGEB_STAT_REPORT_MISSING")
    if not approval:
        hard_reasons.append("STAGEB_APPROVAL_PACKET_MISSING")
    if not stat_stage_c_allowed:
        hard_reasons.append(str(stat_summary.get("stage_c_blocked_reason") or "STAGEB_STATISTICAL_GATES_NOT_CLEARED"))
    if approval_ready <= 0:
        hard_reasons.append("NO_PASS_STAGE_B_READY_CANDIDATE")
    if int(cluster_counts.get("running") or 0) > 0:
        hard_reasons.append("STAGE_B_RUNS_STILL_ACTIVE")

    next_actions = [
        {
            "blocker_code": code,
            "count": count,
            "action": action_for_blocker(code),
        }
        for code, count in combined.most_common(12)
    ]
    if not next_actions and hard_reasons:
        next_actions = [
            {
                "blocker_code": reason,
                "count": 1,
                "action": action_for_blocker(reason),
            }
            for reason in hard_reasons
        ]

    machine_counts = {}
    for row in run_plan.get("rows", []):
        machine = str(row.get("machine_hint") or "unknown")
        status = str(row.get("run_status") or "unknown")
        machine_counts.setdefault(machine, Counter())[status] += 1

    return {
        "schema_version": "project3_stage_b_decision_readiness_v1",
        "generated_at_utc": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_locked": not can_enter_stage_c,
        "stage_c_allowed": can_enter_stage_c,
        "stage_c_decision": "ALLOW_STAGE_C" if can_enter_stage_c else "BLOCK_STAGE_C",
        "hard_stop_reasons": sorted(set(hard_reasons)),
        "statistical_summary": stat_summary,
        "approval_summary": approval_summary,
        "cluster_summary": {
            "generated_at_utc": cluster.get("generated_at_utc"),
            "next_expected_poll_utc": cluster.get("next_expected_poll_utc"),
            "poll_interval_seconds": cluster.get("poll_interval_seconds"),
            "all_queries_ok": cluster.get("all_queries_ok"),
            "counts": cluster_counts,
            "query_errors": cluster.get("query_errors", {}),
        },
        "machine_run_plan_counts": {
            machine: dict(sorted(counter.items()))
            for machine, counter in sorted(machine_counts.items())
        },
        "top_stage_b_blockers": [
            {"blocker_code": code, "count": count}
            for code, count in combined.most_common(20)
        ],
        "next_actions": next_actions,
        "top_blocked_candidates": top_blocked_candidates(approval),
        "source_files": {
            "stageb_stat_report": str(STAGEB_STAT_REPORT),
            "approval_packet": str(APPROVAL_PACKET),
            "cluster_status": str(CLUSTER_STATUS),
            "run_plan_status": str(RUN_PLAN_STATUS),
            "handoff_spec": str(HANDOFF_SPEC),
        },
    }


def write_markdown(payload: dict[str, Any]) -> None:
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Project 3 Stage B Decision Readiness",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Heldout boundary: `{payload['heldout_start']}`",
        f"Stage C decision: `{payload['stage_c_decision']}`",
        f"Stage C locked: `{payload['stage_c_locked']}`",
        "",
        "## Hard Stop Reasons",
        "",
    ]
    for reason in payload["hard_stop_reasons"]:
        lines.append(f"- `{reason}`")

    stat = payload["statistical_summary"]
    approval = payload["approval_summary"]
    cluster = payload["cluster_summary"]
    lines += [
        "",
        "## Current Counts",
        "",
        f"- Stage B evidence pass/fail: `{stat.get('evidence_pass', 0)}` / `{stat.get('evidence_fail', 0)}`",
        f"- Statistical candidate gates pass/fail: `{stat.get('candidate_gate_pass', 0)}` / `{stat.get('candidate_gate_fail', 0)}`",
        f"- DSR pass/fail: `{stat.get('dsr_pass_n_raw', 0)}` / `{stat.get('dsr_fail_n_raw', 0)}`",
        f"- Stage B ready candidates: `{approval.get('n_stage_b_ready', 0)}`",
        f"- Cluster counts: `{cluster.get('counts', {})}`",
        f"- Next status poll UTC: `{cluster.get('next_expected_poll_utc')}`",
        "",
        "## Machine Run-Plan Counts",
        "",
        "| Machine | Status Counts |",
        "| --- | --- |",
    ]
    for machine, counts in payload["machine_run_plan_counts"].items():
        lines.append(f"| {machine} | `{counts}` |")

    lines += [
        "",
        "## Top Blockers",
        "",
        "| Blocker | Count |",
        "| --- | ---: |",
    ]
    for row in payload["top_stage_b_blockers"]:
        lines.append(f"| `{row['blocker_code']}` | {row['count']} |")

    lines += [
        "",
        "## Next Actions",
        "",
        "| Blocker | Count | Required Action |",
        "| --- | ---: | --- |",
    ]
    for row in payload["next_actions"]:
        lines.append(f"| `{row['blocker_code']}` | {row['count']} | {row['action']} |")

    lines += [
        "",
        "## Top Blocked Candidates",
        "",
        "| Candidate | Status | Return | Blockers |",
        "| --- | --- | ---: | --- |",
    ]
    for row in payload["top_blocked_candidates"]:
        lines.append(
            f"| `{row['run_slug']}` | `{row['stage_b_status']}` | "
            f"{row['total_return']} | `{';'.join(row['blocker_codes'])}` |"
        )

    lines += [
        "",
        "## Source Files",
        "",
    ]
    for key, value in payload["source_files"].items():
        lines.append(f"- `{key}`: `{value}`")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    stat = load_json(STAGEB_STAT_REPORT, {})
    approval = load_json(APPROVAL_PACKET, {})
    cluster = load_json(CLUSTER_STATUS, {})
    run_plan = load_json(RUN_PLAN_STATUS, {})
    payload = build_readiness(stat, approval, cluster, run_plan)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write_markdown(payload)
    print(json.dumps({
        "stage_c_decision": payload["stage_c_decision"],
        "hard_stop_reasons": payload["hard_stop_reasons"],
        "top_blockers": payload["top_stage_b_blockers"][:8],
        "next_expected_poll_utc": payload["cluster_summary"].get("next_expected_poll_utc"),
        "json": str(OUT_JSON),
        "markdown": str(OUT_MD),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
