#!/usr/bin/env python3
"""Generate pragmatic Stage B root-cause and economic diagnostics.

This worker converts the strict Stage B evaluator/approval artifacts into
action-oriented reports requested by
``PROJECT3_PRAGMATIC_NEXT_DECISION_SPEC_FOR_ORCHESTRATOR.md``.

It does not launch training and does not touch Stage C. It only reads generated
Stage B evidence summaries and writes derived diagnostic artifacts.
"""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
STAGE_B_ROOT = ROOT / "experiments" / "stage_b_validation"
HARDENING = STAGE_B_ROOT / "hardening"
STAGE_A_APPROVAL = ROOT / "experiments" / "stage_a_screening" / "stage_b_approval" / "stage_b_approval_packet.json"
STAT_REPORT = HARDENING / "stageb_dsr_pbo_report.json"
DECISION_READINESS = HARDENING / "stage_b_decision_readiness.json"
RUN_PLAN_STATUS = ROOT / "experiments" / "stage_b_validation" / "run_plan" / "stage_b_run_plan_status.json"

OUT_STAGE_B_SUMMARY = STAGE_B_ROOT / "stage_b_summary.md"
OUT_TRADE_CSV = HARDENING / "trade_behavior_report.csv"
OUT_TRADE_MD = HARDENING / "trade_behavior_report.md"
OUT_COST_CSV = HARDENING / "cost_fragility_report.csv"
OUT_COST_MD = HARDENING / "cost_fragility_report.md"
OUT_ROOT_CAUSE = HARDENING / "stageb_no_pass_root_cause.md"
OUT_PROMOTION_DECISION = HARDENING / "promotion_decision.json"

HELDOUT_START = "2025-01-01"
LEGACY_REQUIRED_COSTS = ("base", "pessimistic")
PRAGMATIC_REQUIRED_COSTS = ("base", "plus_50pct", "plus_100pct")
ACCEPTED_COST_CONTRACTS = (PRAGMATIC_REQUIRED_COSTS, LEGACY_REQUIRED_COSTS)
ADVERSE_COSTS = ("pessimistic", "plus_100pct")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out


def blocker_class(code: str) -> str:
    if code in {"STAGEB_STAT_EVIDENCE_MISSING", "EVIDENCE_INVALID_OR_MISSING", "MISSING_COST_SCENARIO"}:
        return "infrastructure_missing"
    if code in {"SEED_UNCERTAINTY_BLOCKED"}:
        return "insufficient_repetitions"
    if code in {"DSR_RIGOROUS_FAIL", "PBO_DEFERRED_OR_FAIL", "FAMILY_REALITY_CHECK_FAIL"}:
        return "statistical_non_significance"
    if code in {"NON_POSITIVE_RETURN", "NEGATIVE_SHARPE", "BASELINE_FAIL", "NON_POSITIVE_BASE_RETURN"}:
        return "economic_failure"
    if code in {"NO_TRADES", "FINAL_NO_TRADES", "FINAL_EXCESSIVE_TRADES_HARD", "FINAL_ALWAYS_IN_MARKET_LOSING"}:
        return "trade_behavior_failure"
    if code in {"ABLATION_FAIL", "ABLATION_NO_MATCH"}:
        return "feature_family_failure"
    if "SOURCE" in code:
        return "source_family_failure"
    if "COST" in code:
        return "cost_model_failure"
    return "metric_computation_issue"


def action_for_class(name: str) -> str:
    return {
        "infrastructure_missing": "Repair missing evidence/cost scenarios/baseline artifacts before any promotion discussion.",
        "insufficient_repetitions": "Run paired seeds or keep blocked; one-off seeds cannot promote.",
        "statistical_non_significance": "Keep Stage C blocked; use as exploration signal only, not proof.",
        "economic_failure": "Do not rerun blindly; only create a new counted trial if a documented data/parameter defect exists.",
        "trade_behavior_failure": "Diagnose action mapping, exposure, costs, and reward before any rerun.",
        "feature_family_failure": "Redesign or split feature family; require matched ablation evidence.",
        "source_family_failure": "Audit source availability/provenance and compare matched source ablations.",
        "cost_model_failure": "Generate missing cost scenarios and compute after-cost metrics only.",
        "metric_computation_issue": "Inspect evaluator evidence and add a test before relying on this blocker.",
    }.get(name, "Inspect and classify before launching more compute.")


def approval_blocker_counts(approval: dict[str, Any]) -> Counter:
    counts: Counter = Counter()
    for row in approval.get("all_candidates", []):
        for blocker in row.get("blockers", []):
            if isinstance(blocker, dict) and blocker.get("blocker_code"):
                counts[str(blocker["blocker_code"])] += 1
    return counts


def stat_blocker_counts(stat: dict[str, Any]) -> Counter:
    counts: Counter = Counter()
    for gate in stat.get("candidate_gates", {}).values():
        for reason in gate.get("blocking_reasons", []):
            counts[str(reason)] += 1
    return counts


def build_trade_rows(stat: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for record in stat.get("records", []):
        gate = record.get("trade_gate", {}) or {}
        rows.append({
            "run_id": record.get("run_id", ""),
            "candidate_slug": record.get("candidate_slug", ""),
            "asset": record.get("asset", ""),
            "timeframe": record.get("timeframe", ""),
            "algo": record.get("algo", ""),
            "preset": record.get("preset", ""),
            "seed": record.get("seed", ""),
            "cost_scenario": record.get("cost_scenario", ""),
            "evidence_status": record.get("evidence_status", ""),
            "n_returns": record.get("n_returns", 0),
            "trades_total": gate.get("trades_total", 0),
            "years": gate.get("years", 0.0),
            "trades_per_year": gate.get("trades_per_year", 0.0),
            "exposure_fraction": gate.get("exposure_fraction", 0.0),
            "total_return_from_trace": gate.get("total_return_from_trace", 0.0),
            "no_trade_flag": "FINAL_NO_TRADES" in gate.get("blockers", []),
            "excessive_trade_flag": "FINAL_EXCESSIVE_TRADES_HARD" in gate.get("blockers", []),
            "always_in_market_losing_flag": "FINAL_ALWAYS_IN_MARKET_LOSING" in gate.get("blockers", []),
            "trade_gate_status": gate.get("status", ""),
            "trade_blockers": ";".join(gate.get("blockers", [])),
            "trade_warnings": ";".join(gate.get("warnings", [])),
        })
    return rows


def build_cost_rows(stat: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in stat.get("records", []):
        if not record.get("is_baseline"):
            grouped[str(record.get("candidate_slug", ""))].append(record)

    rows = []
    for slug, records in sorted(grouped.items()):
        by_cost = {str(r.get("cost_scenario")): r for r in records}
        returns = {
            cost: safe_float((by_cost.get(cost, {}).get("trade_gate") or {}).get("total_return_from_trace"))
            for cost in set(LEGACY_REQUIRED_COSTS) | set(PRAGMATIC_REQUIRED_COSTS) | set(by_cost)
        }
        base = returns.get("base", 0.0)
        contract_status = "PASS" if any(set(contract).issubset(by_cost) for contract in ACCEPTED_COST_CONTRACTS) else "MISSING"
        if contract_status == "PASS":
            missing_accepted: list[str] = []
        elif any(cost in by_cost for cost in ("plus_50pct", "plus_100pct")):
            missing_accepted = [cost for cost in PRAGMATIC_REQUIRED_COSTS if cost not in by_cost]
        elif "pessimistic" in by_cost:
            missing_accepted = [cost for cost in LEGACY_REQUIRED_COSTS if cost not in by_cost]
        else:
            missing_accepted = [cost for cost in PRAGMATIC_REQUIRED_COSTS if cost not in by_cost]
        adverse_returns = [returns[cost] for cost in ADVERSE_COSTS if cost in by_cost]
        worst_adverse = min(adverse_returns) if adverse_returns else 0.0
        adverse_label = ";".join(cost for cost in ADVERSE_COSTS if cost in by_cost)
        fragility = bool(
            missing_accepted
            or (base > 0 and worst_adverse <= 0)
            or (base > 0 and worst_adverse < 0.5 * base)
        )
        rows.append({
            "candidate_slug": slug,
            "cost_scenarios_present": ";".join(sorted(by_cost)),
            "accepted_cost_contract_status": contract_status,
            "missing_accepted_costs": ";".join(missing_accepted),
            "missing_legacy_required_costs": ";".join(cost for cost in LEGACY_REQUIRED_COSTS if cost not in by_cost),
            "missing_pragmatic_required_costs": ";".join(cost for cost in PRAGMATIC_REQUIRED_COSTS if cost not in by_cost),
            "base_return": base,
            "worst_adverse_costs_present": adverse_label,
            "worst_adverse_return": worst_adverse,
            "worst_adverse_minus_base": worst_adverse - base,
            "cost_fragility_flag": fragility,
            "base_trace_file": ";".join(t.get("trace_file", "") for t in by_cost.get("base", {}).get("trace_entries", [])),
            "pessimistic_trace_file": ";".join(t.get("trace_file", "") for t in by_cost.get("pessimistic", {}).get("trace_entries", [])),
            "plus_100pct_trace_file": ";".join(t.get("trace_file", "") for t in by_cost.get("plus_100pct", {}).get("trace_entries", [])),
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_trade_md(rows: list[dict[str, Any]]) -> None:
    counts = Counter()
    for row in rows:
        if row["no_trade_flag"]:
            counts["no_trade"] += 1
        if row["excessive_trade_flag"]:
            counts["excessive_trade"] += 1
        if row["always_in_market_losing_flag"]:
            counts["always_in_market_losing"] += 1
    worst = sorted(
        rows,
        key=lambda r: (safe_float(r.get("trades_per_year")), safe_float(r.get("exposure_fraction"))),
        reverse=True,
    )[:10]
    lines = [
        "# Stage B Trade Behavior Report",
        "",
        f"Generated UTC: `{utc_now()}`",
        "",
        "## Summary",
        "",
        f"- Rows: `{len(rows)}`",
        f"- No-trade flags: `{counts['no_trade']}`",
        f"- Excessive-trade hard flags: `{counts['excessive_trade']}`",
        f"- Always-in-market losing flags: `{counts['always_in_market_losing']}`",
        "",
        "## Highest Trade-Rate Rows",
        "",
        "| run_id | cost | trades/year | exposure | return | blockers |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in worst:
        lines.append(
            f"| `{row['run_id']}` | `{row['cost_scenario']}` | {row['trades_per_year']} | "
            f"{row['exposure_fraction']} | {row['total_return_from_trace']} | `{row['trade_blockers']}` |"
        )
    OUT_TRADE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_cost_md(rows: list[dict[str, Any]]) -> None:
    flagged = [row for row in rows if row.get("cost_fragility_flag")]
    lines = [
        "# Stage B Cost Fragility Report",
        "",
        f"Generated UTC: `{utc_now()}`",
        "",
        "## Summary",
        "",
        f"- Candidate groups: `{len(rows)}`",
        f"- Cost-fragility or missing-cost flags: `{len(flagged)}`",
        f"- Accepted cost contracts: `{ACCEPTED_COST_CONTRACTS}`",
        f"- Adverse costs considered for fragility: `{ADVERSE_COSTS}`",
        "",
        "## Flagged Candidates",
        "",
        "| candidate | present | missing accepted | base | worst adverse | delta |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in flagged[:30]:
        lines.append(
            f"| `{row['candidate_slug']}` | `{row['cost_scenarios_present']}` | "
            f"`{row['missing_accepted_costs']}` | "
            f"{row['base_return']} | {row['worst_adverse_return']} | {row['worst_adverse_minus_base']} |"
        )
    OUT_COST_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_root_cause(stat: dict[str, Any], approval: dict[str, Any], trade_rows: list[dict[str, Any]], cost_rows: list[dict[str, Any]]) -> dict[str, Any]:
    combined = Counter()
    combined.update(approval_blocker_counts(approval))
    combined.update(stat_blocker_counts(stat))
    class_counts: Counter = Counter()
    for code, count in combined.items():
        class_counts[blocker_class(code)] += count

    questions = {
        "lose_money_net_of_costs": combined["NON_POSITIVE_RETURN"] + combined["NEGATIVE_SHARPE"] + combined["BASELINE_FAIL"],
        "overtrade": combined["FINAL_EXCESSIVE_TRADES_HARD"],
        "always_exposed_losing": combined["FINAL_ALWAYS_IN_MARKET_LOSING"],
        "cost_scenarios_missing": combined["MISSING_COST_SCENARIO"],
        "seed_count_insufficient": combined["SEED_UNCERTAINTY_BLOCKED"],
        "dsr_raw_blocks": combined["DSR_RIGOROUS_FAIL"],
        "baseline_or_family_incomplete": combined["STAGEB_STAT_EVIDENCE_MISSING"] + combined["ABLATION_NO_MATCH"],
        "pbo_rank_degradation_or_deferred": combined["PBO_DEFERRED_OR_FAIL"],
        "tech_stat_too_broad_or_noisy": combined["FAMILY_REALITY_CHECK_FAIL"] + combined["ABLATION_FAIL"],
    }
    top_trade_flags = Counter()
    for row in trade_rows:
        if row["no_trade_flag"]:
            top_trade_flags["no_trade"] += 1
        if row["excessive_trade_flag"]:
            top_trade_flags["excessive_trade"] += 1
        if row["always_in_market_losing_flag"]:
            top_trade_flags["always_in_market_losing"] += 1
    fragile_count = sum(1 for row in cost_rows if row.get("cost_fragility_flag"))

    lines = [
        "# Stage B No-Pass Root Cause Report",
        "",
        f"Generated UTC: `{utc_now()}`",
        f"Heldout boundary: `{HELDOUT_START}`",
        "",
        "## Decision",
        "",
        "- `stage_c_promotion_allowed`: `false`",
        "- `research_continuation_allowed`: `true`",
        "- `next_action_class`: `diagnose_and_iterate`",
        "",
        "## Why No Candidate Passed",
        "",
        "| Class | Count | Action |",
        "| --- | ---: | --- |",
    ]
    for cls, count in class_counts.most_common():
        lines.append(f"| `{cls}` | {count} | {action_for_class(cls)} |")
    lines += [
        "",
        "## Required Questions",
        "",
        "| Question | Count Signal | Interpretation |",
        "| --- | ---: | --- |",
    ]
    interpretations = {
        "lose_money_net_of_costs": "Many candidates are killed before advanced statistics; do not promote or rerun blindly.",
        "overtrade": "Execution economics are a hard blocker for affected traces.",
        "always_exposed_losing": "Policy behavior can collapse into static exposure; diagnose reward/action mapping.",
        "cost_scenarios_missing": "Operational evidence gap; generate matched costs before promotion.",
        "seed_count_insufficient": "RL reliability gap; paired seed matrix required.",
        "dsr_raw_blocks": "Promotion blocked by multiple-testing/statistical filter; exploration may continue.",
        "baseline_or_family_incomplete": "Matched baseline/evidence coverage is incomplete for some candidates.",
        "pbo_rank_degradation_or_deferred": "Temporal selection stability is not proven.",
        "tech_stat_too_broad_or_noisy": "Feature family likely needs split/reduction/regime variants.",
    }
    for key, value in questions.items():
        lines.append(f"| `{key}` | {value} | {interpretations[key]} |")
    lines += [
        "",
        "## Top Raw Blockers",
        "",
        "| Blocker | Class | Count |",
        "| --- | --- | ---: |",
    ]
    for code, count in combined.most_common(25):
        lines.append(f"| `{code}` | `{blocker_class(code)}` | {count} |")
    lines += [
        "",
        "## Trade Behavior Summary",
        "",
        f"- No-trade trace flags: `{top_trade_flags['no_trade']}`",
        f"- Excessive-trade trace flags: `{top_trade_flags['excessive_trade']}`",
        f"- Always-in-market losing trace flags: `{top_trade_flags['always_in_market_losing']}`",
        "",
        "## Cost Fragility Summary",
        "",
        f"- Candidate cost groups: `{len(cost_rows)}`",
        f"- Missing/fragile current cost evidence groups: `{fragile_count}`",
        "",
        "## Recommended Immediate Next Work",
        "",
        "1. Do not unlock Stage C.",
        "2. Treat current 0/22 as a Stage C blocker, not a project-kill signal.",
        "3. Implement/emit plus_50pct and plus_100pct cost scenarios for the next targeted matrix.",
        "4. Generate the ETHUSDT 4h SAC pragmatic diagnostic manifest before launching any broad new matrix.",
        "5. Split/reduce `tech_stat` into interpretable subfamilies and regime/OOD variants.",
        "6. Keep every new diagnostic run counted in the multiple-testing ledger.",
    ]
    OUT_ROOT_CAUSE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "stage_c_promotion_allowed": False,
        "research_continuation_allowed": True,
        "next_action_class": "diagnose_and_iterate",
        "class_counts": dict(class_counts),
        "blocker_counts": dict(combined),
        "question_signals": questions,
        "trade_flag_counts": dict(top_trade_flags),
        "cost_fragility_groups": fragile_count,
    }


def write_stage_b_summary(stat: dict[str, Any], approval: dict[str, Any], root_summary: dict[str, Any]) -> None:
    stat_summary = stat.get("summary", {})
    approval_summary = approval.get("summary", {})
    lines = [
        "# Project 3 Stage B Summary",
        "",
        f"Generated UTC: `{utc_now()}`",
        f"Heldout boundary: `{HELDOUT_START}`",
        "",
        "## Decision",
        "",
        "- Stage C promotion allowed: `false`",
        "- Research continuation allowed: `true`",
        "- Next action class: `diagnose_and_iterate`",
        "",
        "## Statistical Gate Summary",
        "",
        f"- Evidence pass/fail: `{stat_summary.get('evidence_pass', 0)}` / `{stat_summary.get('evidence_fail', 0)}`",
        f"- Candidate gates pass/fail: `{stat_summary.get('candidate_gate_pass', 0)}` / `{stat_summary.get('candidate_gate_fail', 0)}`",
        f"- DSR pass/fail: `{stat_summary.get('dsr_pass_n_raw', 0)}` / `{stat_summary.get('dsr_fail_n_raw', 0)}`",
        f"- Stage C blocked reason: `{stat_summary.get('stage_c_blocked_reason', '')}`",
        "",
        "## Approval Summary",
        "",
        f"- Total candidates: `{approval_summary.get('total_candidates', 0)}`",
        f"- Stage B ready: `{approval_summary.get('n_stage_b_ready', 0)}`",
        f"- Status counts: `{approval_summary.get('status_counts', {})}`",
        "",
        "## Root-Cause Classes",
        "",
        "| Class | Count |",
        "| --- | ---: |",
    ]
    for cls, count in Counter(root_summary.get("class_counts", {})).most_common():
        lines.append(f"| `{cls}` | {count} |")
    lines += [
        "",
        "## Output Artifacts",
        "",
        f"- `{OUT_TRADE_CSV}`",
        f"- `{OUT_TRADE_MD}`",
        f"- `{OUT_COST_CSV}`",
        f"- `{OUT_COST_MD}`",
        f"- `{OUT_ROOT_CAUSE}`",
        f"- `{OUT_PROMOTION_DECISION}`",
    ]
    OUT_STAGE_B_SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    HARDENING.mkdir(parents=True, exist_ok=True)
    stat = load_json(STAT_REPORT, {})
    approval = load_json(STAGE_A_APPROVAL, {})

    trade_rows = build_trade_rows(stat)
    cost_rows = build_cost_rows(stat)
    write_csv(OUT_TRADE_CSV, trade_rows)
    write_trade_md(trade_rows)
    write_csv(OUT_COST_CSV, cost_rows)
    write_cost_md(cost_rows)
    root_summary = write_root_cause(stat, approval, trade_rows, cost_rows)
    decision = {
        "schema_version": "project3_stage_b_promotion_decision_v1",
        "generated_at_utc": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_promotion_allowed": False,
        "research_continuation_allowed": True,
        "next_action_class": "diagnose_and_iterate",
        "decision_reason": "No candidate passed all Stage B statistical and approval gates.",
        "source_files": {
            "stat_report": str(STAT_REPORT),
            "approval_packet": str(STAGE_A_APPROVAL),
            "decision_readiness": str(DECISION_READINESS),
            "run_plan_status": str(RUN_PLAN_STATUS),
        },
        "root_cause_summary": root_summary,
    }
    OUT_PROMOTION_DECISION.write_text(json.dumps(decision, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    write_stage_b_summary(stat, approval, root_summary)
    print(json.dumps({
        "stage_c_promotion_allowed": False,
        "research_continuation_allowed": True,
        "next_action_class": "diagnose_and_iterate",
        "trade_rows": len(trade_rows),
        "cost_groups": len(cost_rows),
        "root_cause_classes": root_summary["class_counts"],
        "outputs": [
            str(OUT_STAGE_B_SUMMARY),
            str(OUT_TRADE_CSV),
            str(OUT_TRADE_MD),
            str(OUT_COST_CSV),
            str(OUT_COST_MD),
            str(OUT_ROOT_CAUSE),
            str(OUT_PROMOTION_DECISION),
        ],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
