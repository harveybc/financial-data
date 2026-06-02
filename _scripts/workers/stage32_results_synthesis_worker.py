#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
STAGE_A = ROOT / "experiments" / "stage_a_screening"
STAGE_B = ROOT / "experiments" / "stage_b_validation"
OUT = STAGE_A / "synthesis"

INDEX = STAGE_A / "index.csv"
APPROVAL = STAGE_A / "stage_b_approval" / "stage_b_approval_packet.json"
DSR_PBO = STAGE_B / "hardening" / "stageb_dsr_pbo_report.json"
BASELINES = STAGE_A / "hardening" / "simple_baseline_report.json"
FAMILY_ABLATION = STAGE_A / "hardening" / "family_ablation_report.json"
LEAKAGE = STAGE_A / "hardening" / "leakage_heldout_audit_report.json"
NO_TRADE = STAGE_A / "hardening" / "no_trade_diagnostic_report.json"
RUN_PLAN_STATUS = STAGE_B / "run_plan" / "stage_b_run_plan_status.json"


PRESET_TO_FAMILIES = {
    "baseline_12": ["baseline"],
    "tech_full": ["technical"],
    "tech_stat": ["technical", "statistical"],
    "tech_stat_decomp": ["technical", "statistical", "decomposition"],
    "learned_lstm": ["learned_embeddings", "lstm_autoencoder"],
    "learned_cnn": ["learned_embeddings", "cnn_autoencoder"],
    "sota_low_cost": ["technical", "statistical", "sota_low_cost"],
    "crypto_full": ["technical", "statistical", "crypto_structure", "paid_or_subscription"],
    "fx_full": ["technical", "statistical", "fx_structure", "paid_or_subscription"],
    "kitchen_sink_guarded": [
        "technical",
        "statistical",
        "decomposition",
        "learned_embeddings",
        "paid_or_subscription",
        "kitchen_sink_guarded",
    ],
}

SOURCE_MAP = {
    "baseline_12": ["own_asset_ohlcv"],
    "tech_full": ["own_asset_ohlcv"],
    "tech_stat": ["own_asset_ohlcv"],
    "tech_stat_decomp": ["own_asset_ohlcv"],
    "learned_lstm": ["own_asset_ohlcv"],
    "learned_cnn": ["own_asset_ohlcv"],
    "sota_low_cost": ["own_asset_ohlcv", "derived_market_structure"],
    "crypto_full": ["crypto_paid_or_onchain_bundle"],
    "fx_full": ["fx_paid_or_macro_bundle"],
    "kitchen_sink_guarded": ["mixed_all_available_bundle"],
}

PAID_SOURCE_NOTES = {
    "CryptoQuant": "Acquired and integrated as crypto/on-chain candidate source family; final value not clear without Stage B pass.",
    "FXMacroData": "Acquired and integrated as FX macro timing source; final value not clear without Stage B pass.",
    "Glassnode": "Planned/evaluated as crypto subscription family; no Stage B-cleared marginal value evidence yet.",
    "Polygon/FMP/etc.": "Tracked in Phase 1 catalog; current Project 3 trading evidence is not sufficient for a keep/cancel decision.",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def read_rows() -> list[dict]:
    if not INDEX.exists():
        raise FileNotFoundError(f"Missing Stage A index: {INDEX}")
    with INDEX.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fnum(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def mean(values: Iterable[float | None]) -> float | None:
    vals = [v for v in values if v is not None]
    return statistics.fmean(vals) if vals else None


def median(values: Iterable[float | None]) -> float | None:
    vals = sorted(v for v in values if v is not None)
    return statistics.median(vals) if vals else None


def fmt(value, digits: int = 4) -> str:
    num = fnum(value)
    if num is None:
        return "-"
    return f"{num:.{digits}f}"


def slug_id(row: dict) -> tuple:
    return (
        row.get("asset", ""),
        row.get("timeframe", ""),
        row.get("algo", ""),
        row.get("seed", ""),
    )


def grouped(rows: list[dict], key: str) -> list[dict]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get(key, ""))].append(row)
    out = []
    for name, items in buckets.items():
        returns = [fnum(x.get("total_return")) for x in items]
        sharpes = [fnum(x.get("sharpe_ratio")) for x in items]
        trades = [fnum(x.get("trades_total")) for x in items]
        out.append(
            {
                "name": name,
                "runs": len(items),
                "mean_return": mean(returns),
                "median_return": median(returns),
                "mean_sharpe": mean(sharpes),
                "mean_trades": mean(trades),
                "positive_runs": sum(1 for x in returns if x is not None and x > 0),
                "zero_trade_runs": sum(1 for x in trades if x == 0),
            }
        )
    return sorted(out, key=lambda x: (x["mean_return"] is None, -(x["mean_return"] or -999)))


def matched_delta(rows: list[dict], with_predicate, without_predicate) -> dict:
    with_rows: dict[tuple, list[dict]] = defaultdict(list)
    without_rows: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = slug_id(row)
        if with_predicate(row):
            with_rows[key].append(row)
        if without_predicate(row):
            without_rows[key].append(row)
    deltas = []
    for key, lhs in with_rows.items():
        rhs = without_rows.get(key)
        if not rhs:
            continue
        left = mean(fnum(x.get("total_return")) for x in lhs)
        right = mean(fnum(x.get("total_return")) for x in rhs)
        if left is not None and right is not None:
            deltas.append(left - right)
    return {
        "matched_pairs": len(deltas),
        "mean_delta_return": mean(deltas),
        "median_delta_return": median(deltas),
        "positive_pairs": sum(1 for x in deltas if x > 0),
    }


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(out)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def gate_snapshot() -> dict:
    approval = read_json(APPROVAL)
    dsr = read_json(DSR_PBO)
    baselines = read_json(BASELINES)
    ablation = read_json(FAMILY_ABLATION)
    leakage = read_json(LEAKAGE)
    no_trade = read_json(NO_TRADE)
    run_plan = read_json(RUN_PLAN_STATUS)
    summary = approval.get("summary", {})
    dsr_summary = dsr.get("summary", {})
    return {
        "stage_b_ready": int(summary.get("n_stage_b_ready") or 0),
        "approval_counts": summary.get("status_counts", {}),
        "trace_found": dsr_summary.get("trace_found"),
        "trace_missing": dsr_summary.get("trace_missing"),
        "dsr_pass": dsr_summary.get("dsr_pass"),
        "dsr_fail": dsr_summary.get("dsr_fail"),
        "pbo_group_count": dsr_summary.get("pbo_group_count"),
        "baseline_summary": baselines.get("summary", {}),
        "family_summary": ablation.get("summary", {}),
        "leakage_summary": leakage.get("summary", {}),
        "no_trade_summary": no_trade.get("summary", {}),
        "run_plan_status": run_plan.get("status_counts", {}),
        "run_plan_anomalies": run_plan.get("anomaly_counts", {}),
    }


def write_feature_ranking(rows: list[dict], gate: dict) -> Path:
    techniques = sorted({fam for preset in PRESET_TO_FAMILIES.values() for fam in preset})
    table_rows = []
    for fam in techniques:
        delta = matched_delta(
            rows,
            lambda r, fam=fam: fam in PRESET_TO_FAMILIES.get(r.get("preset", ""), []),
            lambda r, fam=fam: fam not in PRESET_TO_FAMILIES.get(r.get("preset", ""), []),
        )
        runs = sum(1 for r in rows if fam in PRESET_TO_FAMILIES.get(r.get("preset", ""), []))
        verdict = "DIAGNOSTIC_ONLY_BLOCKED_STAGE_B"
        if delta["matched_pairs"] and (delta["mean_delta_return"] or 0) <= 0:
            verdict = "NEGATIVE_OR_NEUTRAL_DIAGNOSTIC"
        table_rows.append(
            [
                fam,
                str(runs),
                str(delta["matched_pairs"]),
                fmt(delta["mean_delta_return"], 6),
                fmt(delta["median_delta_return"], 6),
                str(delta["positive_pairs"]),
                verdict,
            ]
        )
    text = "\n".join(
        [
            "# Feature Technique Value Ranking",
            "",
            f"Generated: {now()}",
            "",
            "Status: diagnostic only. No technique is promoted because Stage B has zero ready candidates.",
            "",
            md_table(
                [
                    "Technique / family",
                    "Runs",
                    "Matched pairs",
                    "Mean Δ return",
                    "Median Δ return",
                    "Positive pairs",
                    "Verdict",
                ],
                table_rows,
            ),
            "",
            "Interpretation: these are matched Stage A deltas by `(asset, timeframe, algo, seed)`. They are useful for triage, not final evidence.",
            f"Stage B ready candidates: {gate['stage_b_ready']}. DSR pass/fail: {gate['dsr_pass']}/{gate['dsr_fail']}.",
        ]
    )
    path = OUT / "feature_technique_value_ranking.md"
    write(path, text)
    return path


def write_source_ranking(rows: list[dict], gate: dict) -> Path:
    sources = sorted({src for preset in SOURCE_MAP.values() for src in preset})
    table_rows = []
    for source in sources:
        delta = matched_delta(
            rows,
            lambda r, source=source: source in SOURCE_MAP.get(r.get("preset", ""), []),
            lambda r, source=source: source not in SOURCE_MAP.get(r.get("preset", ""), []),
        )
        runs = sum(1 for r in rows if source in SOURCE_MAP.get(r.get("preset", ""), []))
        if "paid" in source or "bundle" in source:
            verdict = "DEFER_KEEP_CANCEL_DECISION"
        else:
            verdict = "OWN_DERIVED_BASELINE_CONTEXT"
        table_rows.append(
            [
                source,
                str(runs),
                str(delta["matched_pairs"]),
                fmt(delta["mean_delta_return"], 6),
                fmt(delta["median_delta_return"], 6),
                str(delta["positive_pairs"]),
                verdict,
            ]
        )
    text = "\n".join(
        [
            "# Data Source Value Ranking",
            "",
            f"Generated: {now()}",
            "",
            "Status: diagnostic only. Paid/source-family cancellation decisions are deferred until at least one candidate passes Stage B statistical gates.",
            "",
            md_table(
                ["Source family", "Runs", "Matched pairs", "Mean Δ return", "Median Δ return", "Positive pairs", "Verdict"],
                table_rows,
            ),
            "",
            "Important: `crypto_paid_or_onchain_bundle`, `fx_paid_or_macro_bundle`, and `mixed_all_available_bundle` are preset-level bundles, not individual-vendor proof.",
        ]
    )
    path = OUT / "data_source_value_ranking.md"
    write(path, text)
    return path


def write_subscription_recs(gate: dict) -> Path:
    rows = []
    for source, note in PAID_SOURCE_NOTES.items():
        rows.append([source, "DEFER", note, "No cancellation or keep decision from unpromoted Stage A/B evidence."])
    text = "\n".join(
        [
            "# Subscription Cancellation Recommendations",
            "",
            f"Generated: {now()}",
            "",
            "No paid-source cancellation is recommended from the current evidence. The correct action is `DEFER`, because no candidate passed Stage B.",
            "",
            md_table(["Subscription/source", "Action", "Evidence note", "Reason"], rows),
        ]
    )
    path = OUT / "subscription_cancellation_recommendations.md"
    write(path, text)
    return path


def write_family_ranking(rows: list[dict], gate: dict) -> Path:
    fam_report = read_json(FAMILY_ABLATION)
    family_value = fam_report.get("family_value_ranking") or []
    table_rows = []
    if isinstance(family_value, list) and family_value:
        for item in family_value:
            table_rows.append(
                [
                    str(item.get("family", item.get("feature_family", "-"))),
                    str(item.get("asset_class", "all")),
                    str(item.get("matched_runs", item.get("n", "-"))),
                    fmt(item.get("mean_delta_return", item.get("delta_return")), 6),
                    str(item.get("verdict", "DIAGNOSTIC_ONLY")),
                ]
            )
    else:
        for fam in sorted({fam for preset in PRESET_TO_FAMILIES.values() for fam in preset}):
            delta = matched_delta(
                rows,
                lambda r, fam=fam: fam in PRESET_TO_FAMILIES.get(r.get("preset", ""), []),
                lambda r, fam=fam: fam not in PRESET_TO_FAMILIES.get(r.get("preset", ""), []),
            )
            table_rows.append([fam, "all", str(delta["matched_pairs"]), fmt(delta["mean_delta_return"], 6), "DIAGNOSTIC_ONLY"])
    text = "\n".join(
        [
            "# Feature Family Value Ranking",
            "",
            f"Generated: {now()}",
            "",
            "This report consumes the Stage A family-ablation artifact when available and falls back to matched diagnostic deltas.",
            "",
            md_table(["Family", "Asset class", "Matched runs", "Δ return", "Verdict"], table_rows),
            "",
            "Promotion interpretation: family support is necessary but not sufficient; DSR/PBO and baseline gates still block every candidate.",
        ]
    )
    path = OUT / "feature_family_value_ranking.md"
    write(path, text)
    return path


def write_cost_and_baseline(rows: list[dict], gate: dict) -> tuple[Path, Path]:
    by_preset = grouped(rows, "preset")
    cost_rows = []
    for item in by_preset:
        preset_rows = [r for r in rows if r.get("preset") == item["name"]]
        base = mean(fnum(r.get("total_return")) for r in preset_rows)
        pess = mean(fnum(r.get("pessimistic_cost_return")) for r in preset_rows)
        cost_rows.append([item["name"], str(item["runs"]), fmt(base), fmt(pess), fmt((pess or 0) - (base or 0))])
    cost_text = "\n".join(
        [
            "# Cost Sensitivity Summary",
            "",
            f"Generated: {now()}",
            "",
            "Stage A cost sensitivity is diagnostic. Promotion requires explicit base and pessimistic cost evidence on matched Stage B candidates.",
            "",
            md_table(["Preset", "Runs", "Mean base return", "Mean pessimistic return", "Mean drag"], cost_rows),
            "",
            f"Stage B run-plan anomalies: {json.dumps(gate.get('run_plan_anomalies', {}), sort_keys=True)}",
        ]
    )
    cost_path = OUT / "cost_sensitivity_summary.md"
    write(cost_path, cost_text)

    baseline_summary = gate.get("baseline_summary", {})
    baseline_text = "\n".join(
        [
            "# Baseline Comparison Summary",
            "",
            f"Generated: {now()}",
            "",
            "Baseline comparison is partially available from the Stage A simple-baseline worker.",
            "",
            md_table(
                ["Metric", "Value"],
                [[str(k), str(v)] for k, v in baseline_summary.items()],
            ),
            "",
            "Promotion interpretation: candidates that fail matched simple baselines remain blocked even when raw return is positive.",
        ]
    )
    baseline_path = OUT / "baseline_comparison_summary.md"
    write(baseline_path, baseline_text)
    return cost_path, baseline_path


def write_leakage_summary(gate: dict) -> Path:
    leakage_summary = gate.get("leakage_summary", {})
    approval_counts = gate.get("approval_counts", {})
    text = "\n".join(
        [
            "# Leakage And Availability Audit Summary",
            "",
            f"Generated: {now()}",
            "",
            "Stage C remains untouched. No 2025-01-01+ data may be inspected for tuning.",
            "",
            "## Stage B Approval Counts",
            "",
            md_table(["Status", "Count"], [[str(k), str(v)] for k, v in sorted(approval_counts.items())]),
            "",
            "## Leakage Audit Summary",
            "",
            md_table(["Metric", "Value"], [[str(k), str(v)] for k, v in leakage_summary.items()]),
            "",
            "## Trace/Statistical Gate Snapshot",
            "",
            md_table(
                ["Metric", "Value"],
                [
                    ["Trace found", str(gate.get("trace_found"))],
                    ["Trace missing", str(gate.get("trace_missing"))],
                    ["DSR pass", str(gate.get("dsr_pass"))],
                    ["DSR fail", str(gate.get("dsr_fail"))],
                    ["PBO groups", str(gate.get("pbo_group_count"))],
                    ["Stage B ready", str(gate.get("stage_b_ready"))],
                ],
            ),
        ]
    )
    path = OUT / "leakage_and_availability_audit_summary.md"
    write(path, text)
    return path


def write_final(rows: list[dict], gate: dict, outputs: list[Path]) -> Path:
    top = sorted(rows, key=lambda r: (fnum(r.get("total_return")) is None, -(fnum(r.get("total_return")) or -999)))[:15]
    top_rows = [
        [
            str(i),
            f"`{r.get('run_slug')}`",
            r.get("asset", ""),
            r.get("timeframe", ""),
            r.get("algo", ""),
            r.get("preset", ""),
            fmt(r.get("total_return")),
            fmt(r.get("sharpe_ratio")),
            str(r.get("trades_total", "")),
        ]
        for i, r in enumerate(top, 1)
    ]
    text = "\n".join(
        [
            "# Project 3 Final Report Draft",
            "",
            f"Generated: {now()}",
            "",
            "## Executive Summary",
            "",
            "Stage A and the current Stage B trace audit are complete enough for diagnostic synthesis, but not for promotion. "
            "There are zero Stage B-ready candidates. Therefore Stage C must not be launched yet.",
            "",
            "## Current Gate State",
            "",
            md_table(
                ["Gate", "Current result"],
                [
                    ["Stage A indexed runs", str(len(rows))],
                    ["Stage B ready candidates", str(gate.get("stage_b_ready"))],
                    ["DSR pass/fail", f"{gate.get('dsr_pass')}/{gate.get('dsr_fail')}"],
                    ["Return traces found/missing", f"{gate.get('trace_found')}/{gate.get('trace_missing')}"],
                    ["Run-plan status", json.dumps(gate.get("run_plan_status", {}), sort_keys=True)],
                ],
            ),
            "",
            "## Top Raw Stage A Runs",
            "",
            md_table(["#", "Run", "Asset", "TF", "Algo", "Preset", "Return", "Sharpe", "Trades"], top_rows),
            "",
            "## Decision",
            "",
            "- Stage C launch: **BLOCKED**.",
            "- Correct next work: finish Stage 3.2 diagnostic synthesis, inspect DSR/PBO failures, and decide whether any Stage B rerun design is justified.",
            "- Synthetic Phase 4 remains training-only/protocol-locked and cannot rescue a failed real-data Stage B gate.",
            "",
            "## Deliverables Written",
            "",
            *[str(p.relative_to(ROOT)) for p in outputs],
        ]
    )
    path = OUT / "PROJECT_3_FINAL_REPORT.md"
    write(path, text)
    return path


def main() -> int:
    rows = read_rows()
    gate = gate_snapshot()
    outputs: list[Path] = []
    outputs.append(write_feature_ranking(rows, gate))
    outputs.append(write_source_ranking(rows, gate))
    outputs.append(write_subscription_recs(gate))
    outputs.append(write_family_ranking(rows, gate))
    cost_path, baseline_path = write_cost_and_baseline(rows, gate)
    outputs.extend([cost_path, baseline_path])
    outputs.append(write_leakage_summary(gate))
    final_path = write_final(rows, gate, outputs)
    outputs.append(final_path)

    manifest = {
        "generated_at": now(),
        "stage": "3.2",
        "status": "diagnostic_synthesis_complete_stage_c_blocked",
        "stage_b_ready": gate.get("stage_b_ready"),
        "runs": len(rows),
        "outputs": [str(p) for p in outputs],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "synthesis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
