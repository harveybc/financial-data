#!/usr/bin/env python3
"""
stage31_family_ablation_worker.py

Computes Stage 3.1 B9 feature-family ablation evidence from existing Stage A
matched runs. This worker does not launch RL training. It inspects completed
screening results and compares each candidate against narrower presets with the
same asset, timeframe, algorithm, and seed.

Outputs:
  experiments/stage_a_screening/hardening/family_ablation_results.csv
  experiments/stage_a_screening/hardening/family_ablation_report.json
  experiments/stage_a_screening/hardening/family_ablation_report.md
  experiments/design/family_ablation_results.csv

Run:
  python _scripts/workers/stage31_family_ablation_worker.py
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import pathlib
import statistics
from collections import Counter, defaultdict


ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STAGE_A_ROOT = ROOT / "experiments" / "stage_a_screening"
HARDENING_OUT = STAGE_A_ROOT / "hardening"
DESIGN_OUT = ROOT / "experiments" / "design"
INDEX_CSV = STAGE_A_ROOT / "index.csv"
PROMOTION_CSV = HARDENING_OUT / "promotion_candidates.csv"
RESULTS_CSV = HARDENING_OUT / "family_ablation_results.csv"
REPORT_JSON = HARDENING_OUT / "family_ablation_report.json"
REPORT_MD = HARDENING_OUT / "family_ablation_report.md"
DESIGN_RESULTS_CSV = DESIGN_OUT / "family_ablation_results.csv"

BEST_RUN_SLUG = (
    "ethusdt_4h_sac_tech_stat_direct_atr_sltp_s0_"
    "20260502T051413Z_project3_stage31_firstwave"
)

# A comparison is valid only when both rows share asset, timeframe, algo, seed.
# The ablation preset must be narrower than the candidate preset.
COMPARISON_RULES: dict[str, list[dict[str, str]]] = {
    "tech_full": [
        {
            "ablation_preset": "baseline_12",
            "family_id": "technical",
            "comparison_id": "technical_vs_base",
            "required": "true",
        },
    ],
    "tech_stat": [
        {
            "ablation_preset": "tech_full",
            "family_id": "statistical",
            "comparison_id": "statistical_increment_vs_technical",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "technical_statistical",
            "comparison_id": "technical_statistical_vs_base",
            "required": "supporting",
        },
    ],
    "tech_stat_decomp": [
        {
            "ablation_preset": "tech_stat",
            "family_id": "decomposition",
            "comparison_id": "decomposition_vs_tech_stat",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "technical_statistical_decomposition",
            "comparison_id": "tech_stat_decomp_vs_base",
            "required": "supporting",
        },
    ],
    "crypto_full": [
        {
            "ablation_preset": "tech_full",
            "family_id": "crypto_structure",
            "comparison_id": "crypto_structure_vs_technical",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "crypto_full_stack",
            "comparison_id": "crypto_full_vs_base",
            "required": "supporting",
        },
    ],
    "fx_full": [
        {
            "ablation_preset": "tech_full",
            "family_id": "fx_macro_structure",
            "comparison_id": "fx_macro_structure_vs_technical",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "fx_full_stack",
            "comparison_id": "fx_full_vs_base",
            "required": "supporting",
        },
    ],
    "learned_lstm": [
        {
            "ablation_preset": "tech_stat",
            "family_id": "learned_embeddings_lstm",
            "comparison_id": "learned_lstm_vs_tech_stat",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "learned_lstm_stack",
            "comparison_id": "learned_lstm_vs_base",
            "required": "supporting",
        },
    ],
    "learned_cnn": [
        {
            "ablation_preset": "tech_stat",
            "family_id": "learned_embeddings_cnn",
            "comparison_id": "learned_cnn_vs_tech_stat",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "learned_cnn_stack",
            "comparison_id": "learned_cnn_vs_base",
            "required": "supporting",
        },
    ],
    "sota_low_cost": [
        {
            "ablation_preset": "tech_stat",
            "family_id": "sota_low_cost_additions",
            "comparison_id": "sota_low_cost_vs_tech_stat",
            "required": "true",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "sota_low_cost_stack",
            "comparison_id": "sota_low_cost_vs_base",
            "required": "supporting",
        },
    ],
    "kitchen_sink_guarded": [
        {
            "ablation_preset": "tech_stat_decomp",
            "family_id": "kitchen_sink_guarded_increment",
            "comparison_id": "kitchen_sink_guarded_vs_decomp",
            "required": "supporting",
        },
        {
            "ablation_preset": "tech_stat",
            "family_id": "kitchen_sink_guarded_increment",
            "comparison_id": "kitchen_sink_guarded_vs_tech_stat",
            "required": "supporting",
        },
        {
            "ablation_preset": "baseline_12",
            "family_id": "kitchen_sink_guarded_stack",
            "comparison_id": "kitchen_sink_guarded_vs_base",
            "required": "supporting",
        },
    ],
}

SCENARIOS = ("base", "pessimistic")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def safe_float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def fmt(value, digits: int = 6) -> str:
    number = safe_float(value)
    if number is None:
        return "NA"
    return f"{number:.{digits}f}"


def load_csv(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def row_key(row: dict) -> tuple[str, str, str, str, str]:
    return (
        str(row.get("asset", "")),
        str(row.get("timeframe", "")),
        str(row.get("algo", "")),
        str(row.get("seed", "")),
        str(row.get("preset", "")),
    )


def merge_metrics(index_rows: list[dict], promotion_rows: list[dict]) -> list[dict]:
    promotion_by_slug = {str(r.get("run_slug", "")): r for r in promotion_rows}
    merged: list[dict] = []
    for row in index_rows:
        slug = str(row.get("run_slug", ""))
        p = promotion_by_slug.get(slug, {})
        merged_row = dict(row)
        for field in (
            "classification",
            "cost_base",
            "cost_pessimistic",
            "cost_optimistic",
            "asset_class",
            "n_blockers",
            "blockers",
        ):
            if field in p:
                merged_row[field] = p.get(field)
        merged.append(merged_row)
    return merged


def metric(row: dict, field: str) -> float | None:
    if field == "base":
        return safe_float(row.get("cost_base")) or safe_float(row.get("total_return"))
    if field == "pessimistic":
        return (
            safe_float(row.get("cost_pessimistic"))
            or safe_float(row.get("pessimistic_cost_return"))
            or safe_float(row.get("total_return"))
        )
    return safe_float(row.get(field))


def make_comparison(candidate: dict, ablation: dict, rule: dict[str, str]) -> dict:
    base_delta = None
    pess_delta = None
    candidate_base = metric(candidate, "base")
    ablation_base = metric(ablation, "base")
    candidate_pess = metric(candidate, "pessimistic")
    ablation_pess = metric(ablation, "pessimistic")
    if candidate_base is not None and ablation_base is not None:
        base_delta = candidate_base - ablation_base
    if candidate_pess is not None and ablation_pess is not None:
        pess_delta = candidate_pess - ablation_pess

    sharpe_delta = None
    c_sharpe = safe_float(candidate.get("sharpe_ratio"))
    a_sharpe = safe_float(ablation.get("sharpe_ratio"))
    if c_sharpe is not None and a_sharpe is not None:
        sharpe_delta = c_sharpe - a_sharpe

    dd_delta = None
    c_dd = safe_float(candidate.get("max_drawdown_pct"))
    a_dd = safe_float(ablation.get("max_drawdown_pct"))
    if c_dd is not None and a_dd is not None:
        dd_delta = c_dd - a_dd

    trades_delta = None
    c_trades = safe_float(candidate.get("trades_total"))
    a_trades = safe_float(ablation.get("trades_total"))
    if c_trades is not None and a_trades is not None:
        trades_delta = c_trades - a_trades

    if base_delta is None:
        status = "INDETERMINATE"
        reason = "missing base-cost metrics"
    elif base_delta <= 0:
        status = "FAIL"
        reason = "candidate does not beat ablation baseline under base cost"
    elif pess_delta is None:
        status = "PARTIAL_PASS"
        reason = "candidate beats base cost; pessimistic comparison missing"
    elif pess_delta <= 0:
        status = "PARTIAL_PASS"
        reason = "candidate beats base cost but not pessimistic cost"
    else:
        status = "PASS"
        reason = "candidate beats matched ablation under base and pessimistic costs"

    return {
        "run_slug": str(candidate.get("run_slug", "")),
        "machine": str(candidate.get("machine", "")),
        "asset": str(candidate.get("asset", "")),
        "timeframe": str(candidate.get("timeframe", "")),
        "algo": str(candidate.get("algo", "")),
        "seed": str(candidate.get("seed", "")),
        "candidate_preset": str(candidate.get("preset", "")),
        "ablation_preset": str(ablation.get("preset", "")),
        "ablation_run_slug": str(ablation.get("run_slug", "")),
        "family_id": rule["family_id"],
        "comparison_id": rule["comparison_id"],
        "required": rule["required"],
        "status": status,
        "candidate_base_return": candidate_base,
        "ablation_base_return": ablation_base,
        "delta_base_return": base_delta,
        "candidate_pessimistic_return": candidate_pess,
        "ablation_pessimistic_return": ablation_pess,
        "delta_pessimistic_return": pess_delta,
        "candidate_sharpe": c_sharpe,
        "ablation_sharpe": a_sharpe,
        "delta_sharpe": sharpe_delta,
        "candidate_max_drawdown_pct": c_dd,
        "ablation_max_drawdown_pct": a_dd,
        "delta_max_drawdown_pct": dd_delta,
        "candidate_trades_total": c_trades,
        "ablation_trades_total": a_trades,
        "delta_trades_total": trades_delta,
        "reason": reason,
    }


def build_comparisons(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    by_key = {row_key(row): row for row in rows}
    comparison_rows: list[dict] = []
    missing_rows: list[dict] = []

    for candidate in rows:
        preset = str(candidate.get("preset", ""))
        slug = str(candidate.get("run_slug", ""))
        rules = COMPARISON_RULES.get(preset, [])
        if not rules:
            missing_rows.append({
                "run_slug": slug,
                "asset": str(candidate.get("asset", "")),
                "timeframe": str(candidate.get("timeframe", "")),
                "algo": str(candidate.get("algo", "")),
                "seed": str(candidate.get("seed", "")),
                "candidate_preset": preset,
                "ablation_preset": "",
                "family_id": "base",
                "comparison_id": "base_has_no_narrower_ablation",
                "required": "not_applicable",
                "status": "NOT_APPLICABLE",
                "reason": "baseline preset has no narrower family ablation",
            })
            continue
        for rule in rules:
            key = (
                str(candidate.get("asset", "")),
                str(candidate.get("timeframe", "")),
                str(candidate.get("algo", "")),
                str(candidate.get("seed", "")),
                rule["ablation_preset"],
            )
            ablation = by_key.get(key)
            if ablation is None:
                missing_rows.append({
                    "run_slug": slug,
                    "asset": str(candidate.get("asset", "")),
                    "timeframe": str(candidate.get("timeframe", "")),
                    "algo": str(candidate.get("algo", "")),
                    "seed": str(candidate.get("seed", "")),
                    "candidate_preset": preset,
                    "ablation_preset": rule["ablation_preset"],
                    "family_id": rule["family_id"],
                    "comparison_id": rule["comparison_id"],
                    "required": rule["required"],
                    "status": "BLOCKED_NO_MATCH",
                    "reason": "no same asset/timeframe/algo/seed run for ablation preset",
                })
            else:
                comparison_rows.append(make_comparison(candidate, ablation, rule))

    return comparison_rows, missing_rows


def aggregate_by_run(comparisons: list[dict], missing: list[dict]) -> dict[str, dict]:
    by_run: dict[str, list[dict]] = defaultdict(list)
    missing_by_run: dict[str, list[dict]] = defaultdict(list)
    for row in comparisons:
        by_run[row["run_slug"]].append(row)
    for row in missing:
        missing_by_run[row["run_slug"]].append(row)

    all_slugs = set(by_run) | set(missing_by_run)
    result: dict[str, dict] = {}
    for slug in sorted(all_slugs):
        rows = by_run.get(slug, [])
        missing_rows = missing_by_run.get(slug, [])
        applicable_missing = [
            r for r in missing_rows
            if r.get("status") not in {"NOT_APPLICABLE"}
        ]
        required = [r for r in rows if r.get("required") == "true"]
        supporting = [r for r in rows if r.get("required") == "supporting"]
        required_missing = [
            r for r in applicable_missing if r.get("required") == "true"
        ]

        pass_required = [r for r in required if r.get("status") == "PASS"]
        fail_required = [r for r in required if r.get("status") == "FAIL"]
        partial_required = [r for r in required if r.get("status") == "PARTIAL_PASS"]
        pass_any = [r for r in rows if r.get("status") == "PASS"]

        if not rows and not applicable_missing:
            evidence = "NOT_APPLICABLE"
            reason = "baseline preset has no narrower family ablation"
        elif fail_required:
            evidence = "FAIL"
            reason = "required matched family ablation fails"
        elif required_missing and not required:
            evidence = "BLOCKED_NO_MATCH"
            reason = "required matched family ablation run is missing"
        elif required and pass_required and len(pass_required) == len(required):
            evidence = "PASS"
            reason = "all required matched family ablations pass"
        elif required and (pass_required or partial_required):
            evidence = "PARTIAL_PASS"
            reason = "required ablation evidence is incomplete or pessimistic check missing"
        elif not required and pass_any:
            evidence = "PARTIAL_PASS"
            reason = "supporting ablation passes, but no required direct comparison is defined"
        else:
            evidence = "BLOCKED_NO_MATCH" if applicable_missing else "INDETERMINATE"
            reason = "no usable matched family ablation evidence"

        best_delta = None
        positive_deltas = [
            safe_float(r.get("delta_base_return"))
            for r in rows if safe_float(r.get("delta_base_return")) is not None
        ]
        if positive_deltas:
            best_delta = max(positive_deltas)

        result[slug] = {
            "run_slug": slug,
            "b9_evidence": evidence,
            "reason": reason,
            "n_comparisons": len(rows),
            "n_missing_comparisons": len(applicable_missing),
            "n_pass": sum(1 for r in rows if r.get("status") == "PASS"),
            "n_partial_pass": sum(1 for r in rows if r.get("status") == "PARTIAL_PASS"),
            "n_fail": sum(1 for r in rows if r.get("status") == "FAIL"),
            "best_delta_base_return": best_delta,
            "comparisons": rows,
            "missing": applicable_missing,
        }
    return result


def aggregate_by_family(comparisons: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in comparisons:
        asset = str(row.get("asset", ""))
        asset_class = "crypto" if "usdt" in asset.lower() else "fx"
        grouped[(row["family_id"], asset_class)].append(row)

    output: list[dict] = []
    for (family_id, asset_class), rows in sorted(grouped.items()):
        deltas = [safe_float(r.get("delta_base_return")) for r in rows]
        deltas = [d for d in deltas if d is not None]
        sharpe_deltas = [safe_float(r.get("delta_sharpe")) for r in rows]
        sharpe_deltas = [d for d in sharpe_deltas if d is not None]
        dd_deltas = [safe_float(r.get("delta_max_drawdown_pct")) for r in rows]
        dd_deltas = [d for d in dd_deltas if d is not None]
        status_counts = Counter(r.get("status", "") for r in rows)
        output.append({
            "family_id": family_id,
            "asset_class": asset_class,
            "matched_runs": len(rows),
            "pass": status_counts.get("PASS", 0),
            "partial_pass": status_counts.get("PARTIAL_PASS", 0),
            "fail": status_counts.get("FAIL", 0),
            "delta_base_return_mean": statistics.mean(deltas) if deltas else None,
            "delta_base_return_median": statistics.median(deltas) if deltas else None,
            "delta_base_return_max": max(deltas) if deltas else None,
            "delta_sharpe_mean": statistics.mean(sharpe_deltas) if sharpe_deltas else None,
            "delta_max_drawdown_pct_mean": statistics.mean(dd_deltas) if dd_deltas else None,
            "verdict": family_verdict(status_counts, len(rows)),
        })
    return output


def family_verdict(counts: Counter, total: int) -> str:
    if total <= 0:
        return "NO_EVIDENCE"
    if counts.get("PASS", 0) >= max(1, total // 2 + 1):
        return "PROMISING"
    if counts.get("PASS", 0) > 0:
        return "MIXED"
    if counts.get("FAIL", 0) > 0:
        return "WEAK_OR_NEGATIVE"
    return "INDETERMINATE"


def write_csv(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "run_slug", "machine", "asset", "timeframe", "algo", "seed",
        "candidate_preset", "ablation_preset", "ablation_run_slug",
        "family_id", "comparison_id", "required", "status",
        "candidate_base_return", "ablation_base_return", "delta_base_return",
        "candidate_pessimistic_return", "ablation_pessimistic_return",
        "delta_pessimistic_return", "candidate_sharpe", "ablation_sharpe",
        "delta_sharpe", "candidate_max_drawdown_pct",
        "ablation_max_drawdown_pct", "delta_max_drawdown_pct",
        "candidate_trades_total", "ablation_trades_total",
        "delta_trades_total", "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_report(
    comparisons: list[dict],
    missing: list[dict],
    by_run: dict[str, dict],
    by_family: list[dict],
) -> None:
    status_counts = Counter(v["b9_evidence"] for v in by_run.values())
    comparison_counts = Counter(r["status"] for r in comparisons)
    best = by_run.get(BEST_RUN_SLUG)

    payload = {
        "generated_at": utc_now(),
        "worker": "stage31_family_ablation_worker.py",
        "summary": {
            "total_runs_with_b9_status": len(by_run),
            "comparison_rows": len(comparisons),
            "missing_or_not_applicable_rows": len(missing),
            "b9_status_counts": dict(sorted(status_counts.items())),
            "comparison_status_counts": dict(sorted(comparison_counts.items())),
        },
        "b9_clearance": clearance_text(status_counts),
        "best_run_slug": BEST_RUN_SLUG,
        "best_run_b9": best,
        "family_value_ranking": by_family,
        "all_run_comparisons": [
            {
                "run_slug": slug,
                "b9_evidence": item["b9_evidence"],
                "reason": item["reason"],
                "n_comparisons": item["n_comparisons"],
                "n_missing_comparisons": item["n_missing_comparisons"],
                "n_pass": item["n_pass"],
                "n_partial_pass": item["n_partial_pass"],
                "n_fail": item["n_fail"],
                "best_delta_base_return": item["best_delta_base_return"],
            }
            for slug, item in sorted(by_run.items())
        ],
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    lines = [
        "# Stage 3.1 B9 Feature-Family Ablation Report",
        "",
        f"Generated: {utc_now()}",
        "",
        "## Summary",
        "",
        f"- Runs with B9 status: {len(by_run)}",
        f"- Matched comparison rows: {len(comparisons)}",
        f"- Missing/not-applicable rows: {len(missing)}",
        "",
        "| B9 evidence | Count |",
        "| --- | ---: |",
    ]
    for key, value in sorted(status_counts.items()):
        lines.append(f"| {key} | {value} |")
    lines += [
        "",
        "| Comparison status | Count |",
        "| --- | ---: |",
    ]
    for key, value in sorted(comparison_counts.items()):
        lines.append(f"| {key} | {value} |")

    lines += [
        "",
        "## Best Run",
        "",
        f"`{BEST_RUN_SLUG}`",
        "",
    ]
    if best:
        lines += [
            f"- B9 evidence: **{best['b9_evidence']}**",
            f"- Reason: {best['reason']}",
            f"- Matched comparisons: {best['n_comparisons']}",
            f"- Best base-cost delta: {fmt(best['best_delta_base_return'])}",
            "",
            "| Family | Comparison | Ablation preset | Status | Delta base | Delta pessimistic | Delta Sharpe |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
        for row in best["comparisons"]:
            lines.append(
                f"| {row['family_id']} | {row['comparison_id']} | {row['ablation_preset']} "
                f"| {row['status']} | {fmt(row['delta_base_return'])} "
                f"| {fmt(row['delta_pessimistic_return'])} | {fmt(row['delta_sharpe'])} |"
            )
    else:
        lines.append("Best run not found in B9 evidence.")

    lines += [
        "",
        "## Family Value Ranking",
        "",
        "| Family | Asset class | Matched runs | Pass | Partial | Fail | Mean delta base | Mean delta Sharpe | Mean delta DD | Verdict |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in by_family:
        lines.append(
            f"| {row['family_id']} | {row['asset_class']} | {row['matched_runs']} "
            f"| {row['pass']} | {row['partial_pass']} | {row['fail']} "
            f"| {fmt(row['delta_base_return_mean'])} | {fmt(row['delta_sharpe_mean'])} "
            f"| {fmt(row['delta_max_drawdown_pct_mean'])} | {row['verdict']} |"
        )

    lines += [
        "",
        "## Caveats",
        "",
        "- This is matched Stage A evidence only; it does not replace Stage B retraining.",
        "- Comparisons are valid only for same asset, timeframe, algorithm, and seed.",
        "- For learned embeddings, the comparison is against `tech_stat` when available; those presets may replace rather than strictly add raw features.",
        "- `kitchen_sink_guarded` is exploratory unless direct ablation evidence supports it.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def clearance_text(counts: Counter) -> str:
    passes = counts.get("PASS", 0)
    partial = counts.get("PARTIAL_PASS", 0)
    fail = counts.get("FAIL", 0)
    blocked = counts.get("BLOCKED_NO_MATCH", 0)
    na = counts.get("NOT_APPLICABLE", 0)
    return (
        f"PARTIALLY_CLEARED - {passes} PASS, {partial} PARTIAL_PASS, "
        f"{fail} FAIL, {blocked} BLOCKED_NO_MATCH, {na} NOT_APPLICABLE. "
        "B9 is cleared per-run only for PASS evidence."
    )


def update_tasks(by_run: dict[str, dict]) -> None:
    tasks = HARDENING_OUT / "TASKS.md"
    if not tasks.exists():
        return
    text = tasks.read_text(encoding="utf-8")
    text = text.replace(
        "- [ ] B9: Feature-family ablation - requires matched runs with one family removed per config",
        "- [x] B9: Feature-family ablation - matched Stage A evidence computed by stage31_family_ablation_worker.py",
    )
    text = text.replace(
        "- [ ] B9: Feature-family ablation — requires matched runs with one family removed per config",
        "- [x] B9: Feature-family ablation — matched Stage A evidence computed by stage31_family_ablation_worker.py",
    )
    marker = "\n## B9 family ablation evidence\n"
    if marker not in text:
        best = by_run.get(BEST_RUN_SLUG, {})
        text += (
            marker
            + "\n"
            + f"- Generated: {utc_now()}\n"
            + f"- Best run B9 evidence: {best.get('b9_evidence', 'NOT_FOUND')}\n"
            + f"- Best run reason: {best.get('reason', 'not found')}\n"
            + "- Outputs: `family_ablation_results.csv`, `family_ablation_report.md`, `family_ablation_report.json`\n"
        )
    tasks.write_text(text, encoding="utf-8")


def main() -> int:
    HARDENING_OUT.mkdir(parents=True, exist_ok=True)
    DESIGN_OUT.mkdir(parents=True, exist_ok=True)

    index_rows = load_csv(INDEX_CSV)
    promotion_rows = load_csv(PROMOTION_CSV)
    rows = merge_metrics(index_rows, promotion_rows)
    comparisons, missing = build_comparisons(rows)
    by_run = aggregate_by_run(comparisons, missing)
    by_family = aggregate_by_family(comparisons)

    all_rows_for_csv = comparisons + missing
    write_csv(RESULTS_CSV, all_rows_for_csv)
    write_csv(DESIGN_RESULTS_CSV, comparisons)
    write_report(comparisons, missing, by_run, by_family)
    update_tasks(by_run)

    status_counts = Counter(v["b9_evidence"] for v in by_run.values())
    best = by_run.get(BEST_RUN_SLUG, {})
    print(f"[INFO] Wrote {RESULTS_CSV}")
    print(f"[INFO] Wrote {REPORT_MD}")
    print(f"[INFO] Wrote {REPORT_JSON}")
    print(f"[INFO] B9 status counts: {dict(sorted(status_counts.items()))}")
    print(f"[INFO] Best run B9: {best.get('b9_evidence')} - {best.get('reason')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
