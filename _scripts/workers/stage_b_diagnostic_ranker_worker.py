#!/usr/bin/env python3
"""Rank blocked Stage B candidates for research follow-up.

This worker deliberately does not approve Stage C. It creates a diagnostic
"least bad" ranking from the already generated Stage B statistical report so
the next research branch can be chosen without pretending that a hard gate
passed.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HARDENING = ROOT / "experiments" / "stage_b_validation" / "hardening"
STAT_REPORT = HARDENING / "stageb_dsr_pbo_report.json"
OUT_JSON = HARDENING / "stage_b_diagnostic_candidate_ranking.json"
OUT_CSV = HARDENING / "stage_b_diagnostic_candidate_ranking.csv"
OUT_MD = HARDENING / "stage_b_diagnostic_candidate_ranking.md"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cost_family_statuses(records: list[dict[str, Any]], family_tests: dict[str, Any]) -> list[str]:
    statuses: list[str] = []
    seen: set[str] = set()
    for rec in records:
        key = "|".join(
            str(rec.get(name, ""))
            for name in ("asset", "timeframe", "algo", "cost_scenario")
        )
        if key in seen:
            continue
        seen.add(key)
        status = str((family_tests.get(key) or {}).get("status", "MISSING"))
        statuses.append(status)
    return statuses


def pbo_status(records: list[dict[str, Any]], pbo_groups: dict[str, Any]) -> tuple[str, float | None]:
    if not records:
        return "MISSING", None
    rec = records[0]
    key = "|".join(str(rec.get(name, "")) for name in ("asset", "timeframe", "algo"))
    pbo = pbo_groups.get(key) or {}
    if "pbo" not in pbo:
        return str(pbo.get("status", "MISSING")), None
    value = safe_float(pbo.get("pbo"))
    return "PASS" if value <= 0.20 else "FAIL", value


def seed_statuses(slug: str, costs: set[str], seed_uncertainty: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for cost in sorted(costs):
        item = seed_uncertainty.get(f"{slug}|{cost}") or {}
        out.append(str(item.get("status", "MISSING")))
    return out


def diagnostic_score(row: dict[str, Any]) -> float:
    """Weighted research score, not a promotion score.

    The score rewards economics and evidence completeness, but heavily penalizes
    the hard failure modes that made Stage C unavailable.
    """
    score = 0.0
    score += 30.0 * row["mean_return"]
    score += 20.0 * row["min_return"]
    score += 10.0 * row["mean_sharpe"]
    score += 4.0 * row["cost_count"]
    score += 3.0 * row["seed_pass_count"]
    score += 2.0 * row["trade_pass_count"]
    if row["pbo_status"] == "PASS":
        score += 5.0
    if row["family_pass_count"] > 0:
        score += 4.0 * row["family_pass_count"]
    score -= 6.0 * row["blocking_reason_count"]
    score -= 4.0 * row["trade_blocker_count"]
    score -= 3.0 * row["missing_cost_count"]
    score -= 3.0 * row["seed_blocked_count"]
    score -= 3.0 * row["family_fail_count"]
    return score


def build_rows(stat: dict[str, Any]) -> list[dict[str, Any]]:
    records_by_slug: dict[str, list[dict[str, Any]]] = {}
    for rec in stat.get("records", []):
        if rec.get("evidence_status") != "PASS":
            continue
        if rec.get("is_baseline"):
            continue
        slug = str(rec.get("candidate_slug") or "")
        if not slug:
            continue
        records_by_slug.setdefault(slug, []).append(rec)

    candidate_gates = stat.get("candidate_gates", {})
    family_tests = stat.get("family_tests", {})
    pbo_groups = stat.get("pbo_groups", {})
    seed_uncertainty = stat.get("seed_uncertainty", {})
    rows: list[dict[str, Any]] = []

    for slug, records in sorted(records_by_slug.items()):
        costs = {str(r.get("cost_scenario", "")) for r in records if r.get("cost_scenario")}
        returns = [safe_float((r.get("trade_gate") or {}).get("total_return_from_trace")) for r in records]
        sharpes = [safe_float(r.get("sr_period")) for r in records]
        dsr_p_values = [
            safe_float((r.get("dsr_n_raw") or {}).get("dsr_p_value"), 1.0)
            for r in records
        ]
        trade_statuses = [str((r.get("trade_gate") or {}).get("status", "MISSING")) for r in records]
        trade_blockers = sorted({
            str(blocker)
            for r in records
            for blocker in ((r.get("trade_gate") or {}).get("blockers") or [])
        })
        gate = candidate_gates.get(slug) or {}
        blocking = sorted(str(x) for x in gate.get("blocking_reasons", []))
        missing_costs = sorted(str(x) for x in gate.get("missing_required_cost_scenarios", []))
        family_status = cost_family_statuses(records, family_tests)
        seed_status = seed_statuses(slug, costs, seed_uncertainty)
        pbo_state, pbo_value = pbo_status(records, pbo_groups)
        # Trade-cleanliness lock-out: any FINAL_NO_TRADES /
        # FINAL_EXCESSIVE_TRADES_HARD / FINAL_ALWAYS_IN_MARKET_LOSING signal at
        # the per-record OR candidate-gate level forces this slug below the
        # trade-clean cohort in the diagnostic sort. The score alone cannot
        # promote a baseline that did not trade above a candidate that did.
        record_trade_blockers = {
            str(blocker)
            for r in records
            for blocker in ((r.get("trade_gate") or {}).get("blockers") or [])
        }
        gate_trade_blockers = {
            str(b) for b in blocking
            if b in {"FINAL_NO_TRADES", "FINAL_EXCESSIVE_TRADES_HARD", "FINAL_ALWAYS_IN_MARKET_LOSING"}
        }
        trade_clean = not (record_trade_blockers | gate_trade_blockers)
        row = {
            "candidate_slug": slug,
            "asset": str(records[0].get("asset", "")),
            "timeframe": str(records[0].get("timeframe", "")),
            "algo": str(records[0].get("algo", "")),
            "preset": str(records[0].get("preset", "")),
            "record_count": len(records),
            "cost_count": len(costs),
            "costs": ";".join(sorted(costs)),
            "mean_return": mean(returns) if returns else 0.0,
            "min_return": min(returns) if returns else 0.0,
            "max_return": max(returns) if returns else 0.0,
            "mean_sharpe": mean(sharpes) if sharpes else 0.0,
            "best_dsr_p_value": min(dsr_p_values) if dsr_p_values else 1.0,
            "trade_pass_count": sum(1 for s in trade_statuses if s == "PASS"),
            "trade_blocker_count": len(trade_blockers),
            "trade_blockers": ";".join(trade_blockers),
            "seed_pass_count": sum(1 for s in seed_status if s == "PASS"),
            "seed_blocked_count": sum(1 for s in seed_status if s != "PASS"),
            "seed_statuses": ";".join(seed_status),
            "family_pass_count": sum(1 for s in family_status if s == "PASS"),
            "family_fail_count": sum(1 for s in family_status if s != "PASS"),
            "family_statuses": ";".join(family_status),
            "pbo_status": pbo_state,
            "pbo": "" if pbo_value is None else pbo_value,
            "missing_cost_count": len(missing_costs),
            "missing_costs": ";".join(missing_costs),
            "blocking_reason_count": len(blocking),
            "blocking_reasons": ";".join(blocking),
            "promotion_allowed": bool(gate.get("promotion_allowed")),
            "trade_clean": trade_clean,
        }
        row["diagnostic_score"] = diagnostic_score(row)
        rows.append(row)

    # Trade-clean candidates always sort above trade-blocked candidates even if
    # the score formula would otherwise reverse the order. A no-trade slug with
    # a fortuitously large held-position return must not outrank a slug that
    # actually traded cleanly.
    rows.sort(
        key=lambda r: (r["promotion_allowed"], r["trade_clean"], r["diagnostic_score"]),
        reverse=True,
    )
    for idx, row in enumerate(rows, start=1):
        row["diagnostic_rank"] = idx
    return rows


def write_outputs(rows: list[dict[str, Any]], stat: dict[str, Any]) -> None:
    HARDENING.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "project3_stage_b_diagnostic_candidate_ranking_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Research triage only. Not a Stage C promotion artifact.",
        "stage_c_allowed": False,
        "promotion_allowed_count": sum(1 for row in rows if row["promotion_allowed"]),
        "candidate_count": len(rows),
        "statistical_report_summary": stat.get("summary", {}),
        "ranking_method": {
            "score": (
                "30*mean_return + 20*min_return + 10*mean_sharpe + "
                "4*cost_count + 3*seed_pass_count + 2*trade_pass_count + "
                "5*pbo_pass + 4*family_pass_count - 6*blockers - "
                "4*trade_blockers - 3*missing_costs - 3*seed_blocked - "
                "3*family_fail"
            ),
            "warning": "The score orders failed candidates for diagnosis; it cannot override hard gates.",
        },
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    fields = list(rows[0].keys()) if rows else [
        "diagnostic_rank",
        "candidate_slug",
        "diagnostic_score",
    ]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Stage B Diagnostic Candidate Ranking",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "This is a research-triage ranking only. It does not approve Stage C.",
        "",
        f"- Candidate rows ranked: `{len(rows)}`",
        f"- Promotion-allowed rows: `{payload['promotion_allowed_count']}`",
        f"- Stage C allowed by this artifact: `{payload['stage_c_allowed']}`",
        "",
        "## Top 20 Least-Bad Candidates",
        "",
        "| Rank | Candidate | Score | Mean Return | Min Return | Mean SR | Costs | Seed Pass | Trade Blockers | Main Blockers |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows[:20]:
        lines.append(
            f"| {row['diagnostic_rank']} | `{row['candidate_slug']}` | "
            f"{row['diagnostic_score']:.4f} | {row['mean_return']:.6f} | "
            f"{row['min_return']:.6f} | {row['mean_sharpe']:.6f} | "
            f"{row['cost_count']} | {row['seed_pass_count']} | "
            f"`{row['trade_blockers']}` | `{row['blocking_reasons']}` |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Use this ranking to decide what to diagnose or redesign next.",
        "- Do not use this ranking to promote a candidate.",
        "- Any new experiment selected from this ranking is a new counted trial.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    stat = load_json(STAT_REPORT)
    rows = build_rows(stat)
    write_outputs(rows, stat)
    print(json.dumps({
        "candidate_count": len(rows),
        "promotion_allowed_count": sum(1 for row in rows if row["promotion_allowed"]),
        "json": str(OUT_JSON),
        "csv": str(OUT_CSV),
        "markdown": str(OUT_MD),
        "top_candidate": rows[0]["candidate_slug"] if rows else "",
        "top_score": rows[0]["diagnostic_score"] if rows else None,
        "stage_c_allowed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
