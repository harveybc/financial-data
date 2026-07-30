#!/usr/bin/env python3
"""Build the provisional OANDA Practice asset manifest from Project3 OLAP evidence."""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SELECTION_SCHEMA = "project3.oanda_practice_asset_selection.v1"
E4_STAGE = "E4_ASSET_POLICY_TRAINING"
HISTORICAL_PHASE = "annual_diversity_survey_fast40k_v2"


@dataclass(frozen=True)
class Candidate:
    canonical_asset: str
    oanda_instrument: str
    timeframe: str
    role: str
    portfolio_relevance: float
    phase: str


CANDIDATES = (
    Candidate("eurusd", "EUR_USD", "1h", "execution_control", 1.0, "day_1"),
    Candidate("usdcad", "USD_CAD", "4h", "long_horizon_alpha_shadow", 1.0, "day_1"),
    Candidate("nzdusd", "NZD_USD", "1h", "short_horizon_alpha_shadow", 1.0, "day_1"),
    Candidate(
        "gbpjpy",
        "GBP_JPY",
        "1h",
        "activity_diversification_shadow",
        0.9,
        "day_1",
    ),
    Candidate("usdjpy", "USD_JPY", "1h", "activity_alternate", 0.7, "day_1"),
    Candidate(
        "eurjpy",
        "EUR_JPY",
        "4h",
        "historical_positive_comparator",
        0.6,
        "day_1",
    ),
)


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _json_object(value: str | None) -> dict[str, Any]:
    parsed = json.loads(value or "{}")
    return parsed if isinstance(parsed, dict) else {}


def load_e4_evidence(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Aggregate validation-only E4 evidence and retain the best artifact job."""
    connection = _connect_read_only(path)
    try:
        rows = connection.execute(
            """
            SELECT
                job_id,
                config_json,
                validation_annualized_return,
                validation_annual_rap,
                validation_max_drawdown,
                validation_evaluation_weeks
            FROM evidence_result_olap
            WHERE stage=? AND status='completed'
              AND validation_annual_rap IS NOT NULL
            """,
            (E4_STAGE,),
        ).fetchall()
    finally:
        connection.close()

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        config = _json_object(row["config_json"])
        key = (str(config.get("asset", "")).lower(), str(config.get("timeframe", "")))
        if not all(key):
            continue
        grouped.setdefault(key, []).append(
            {
                "job_id": row["job_id"],
                "annual_return": float(row["validation_annualized_return"]),
                "annual_rap": float(row["validation_annual_rap"]),
                "max_drawdown": float(row["validation_max_drawdown"]),
                "evaluation_weeks": float(row["validation_evaluation_weeks"]),
                "evaluation_protocol_id": config.get("upstream_evaluation_protocol_id"),
                "selected_feature_count": len(config.get("upstream_selected_features") or []),
                "model_family": "sac",
                "feature_selection_method": config.get("feature_selection_method"),
                "preprocessing_mode": config.get("preprocessing_mode"),
            }
        )

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for key, values in grouped.items():
        best = max(values, key=lambda item: item["annual_rap"])
        raps = [item["annual_rap"] for item in values]
        result[key] = {
            "seed_count": len(values),
            "mean_evaluation_weeks": statistics.mean(
                item["evaluation_weeks"] for item in values
            ),
            "mean_annual_return": statistics.mean(
                item["annual_return"] for item in values
            ),
            "mean_annual_rap": statistics.mean(raps),
            "worst_seed_annual_rap": min(raps),
            "annual_rap_seed_stddev": statistics.pstdev(raps),
            "mean_max_drawdown": statistics.mean(
                item["max_drawdown"] for item in values
            ),
            "best_artifact_job_id": best["job_id"],
            "best_seed_annual_rap": best["annual_rap"],
            "evaluation_protocol_id": best["evaluation_protocol_id"],
            "selected_feature_count": best["selected_feature_count"],
            "model_family": best["model_family"],
            "feature_selection_method": best["feature_selection_method"],
            "preprocessing_mode": best["preprocessing_mode"],
        }
    return result


def load_historical_activity(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load one comparable full-year validation row per asset and timeframe."""
    connection = _connect_read_only(path)
    try:
        rows = connection.execute(
            """
            WITH ranked AS (
                SELECT
                    asset,
                    timeframe,
                    candidate_id,
                    model_family,
                    annual_validation_return,
                    annual_validation_rap,
                    worst_weekly_validation_rap,
                    mean_weekly_validation_trades,
                    unique_validation_weeks,
                    ROW_NUMBER() OVER (
                        PARTITION BY asset,timeframe
                        ORDER BY annual_validation_rap DESC, candidate_id
                    ) AS rank_in_pair
                FROM weekly_result_validation_year_olap
                WHERE experiment_phase=?
                  AND has_near_full_year_coverage=1
            )
            SELECT * FROM ranked WHERE rank_in_pair=1
            """,
            (HISTORICAL_PHASE,),
        ).fetchall()
    finally:
        connection.close()

    return {
        (str(row["asset"]).lower(), str(row["timeframe"])): {
            "candidate_id": row["candidate_id"],
            "model_family": row["model_family"],
            "annual_return": row["annual_validation_return"],
            "annual_rap": row["annual_validation_rap"],
            "worst_weekly_rap": row["worst_weekly_validation_rap"],
            "mean_weekly_trades": row["mean_weekly_validation_trades"],
            "unique_validation_weeks": row["unique_validation_weeks"],
            "experiment_phase": HISTORICAL_PHASE,
        }
        for row in rows
    }


def _rank_quality(
    candidates: Iterable[Candidate],
    e4: dict[tuple[str, str], dict[str, Any]],
) -> dict[tuple[str, str], float]:
    keys = [
        (item.canonical_asset, item.timeframe)
        for item in candidates
        if (item.canonical_asset, item.timeframe) in e4
    ]
    ordered = sorted(keys, key=lambda key: e4[key]["mean_annual_rap"])
    if len(ordered) < 2:
        return {key: 1.0 for key in ordered}
    return {key: index / (len(ordered) - 1) for index, key in enumerate(ordered)}


def build_selection(
    e4: dict[tuple[str, str], dict[str, Any]],
    historical: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create a role-aware observation priority without declaring a live winner."""
    quality = _rank_quality(CANDIDATES, e4)
    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        key = (candidate.canonical_asset, candidate.timeframe)
        e4_row = e4.get(key)
        historical_row = historical.get(key)

        coverage = 0.0
        stability = 0.0
        if e4_row:
            coverage = min(e4_row["seed_count"] / 3.0, 1.0) * min(
                e4_row["mean_evaluation_weeks"] / 49.0, 1.0
            )
            stability = max(
                0.0,
                1.0 - min(e4_row["annual_rap_seed_stddev"] / 0.05, 1.0),
            )
        elif historical_row:
            coverage = min(historical_row["unique_validation_weeks"] / 49.0, 1.0) * 0.35
            stability = 0.25

        weekly_trades = (
            float(historical_row["mean_weekly_trades"])
            if historical_row and historical_row["mean_weekly_trades"] is not None
            else 0.0
        )
        activity = min(math.log1p(max(weekly_trades, 0.0)) / math.log(11.0), 1.0)
        quality_score = quality.get(key, 0.35 if historical_row else 0.0)
        priority_score = 100.0 * (
            0.25 * coverage
            + 0.25 * activity
            + 0.20 * quality_score
            + 0.15 * stability
            + 0.15 * candidate.portfolio_relevance
        )
        rows.append(
            {
                **asdict(candidate),
                "observation_priority_score": round(priority_score, 3),
                "score_components": {
                    "evidence_coverage": round(coverage, 6),
                    "historical_activity": round(activity, 6),
                    "e4_validation_quality_rank": round(quality_score, 6),
                    "e4_seed_stability": round(stability, 6),
                    "portfolio_relevance": candidate.portfolio_relevance,
                },
                "e4_validation": e4_row,
                "historical_activity_proxy": historical_row,
                "broker_availability": "pending_practice_preflight",
                "execution_permission": "read_only",
            }
        )

    rows.sort(
        key=lambda item: (
            item["role"] != "execution_control",
            -item["observation_priority_score"],
            item["oanda_instrument"],
        )
    )
    for priority, row in enumerate(rows, 1):
        row["priority"] = priority
    return rows


def write_outputs(output_dir: Path, rows: list[dict[str, Any]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": SELECTION_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "selection_scope": "OANDA Practice execution-reality calibration",
        "selection_warning": (
            "The score orders observation effort. It is not a financial promotion "
            "metric and it does not combine incompatible protocols as profit evidence."
        ),
        "day_1_metrics": [
            "instrument_availability",
            "price_observation_coverage",
            "spread_bps_p50_p95",
            "api_error_rate",
            "transaction_reconciliation",
        ],
        "week_1_metrics": [
            "protected_order_acceptance_rate",
            "sl_tp_attachment_rate",
            "implementation_shortfall",
            "realized_spread_cost",
            "financing",
            "execution_adjusted_weekly_return",
            "execution_adjusted_weekly_rap",
            "backtest_live_metric_drift",
        ],
        "assets": rows,
    }
    (output_dir / "oanda_practice_asset_selection_v1.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# OANDA Practice Asset Selection",
        "",
        "This table is generated from validation-only E4 evidence and the comparable",
        "Project3 annual survey. The score orders live-observation effort; it is not",
        "a claim that unlike experimental protocols have a common financial scale.",
        "",
        "| Priority | Instrument | Role | TF | Score | E4 seeds | E4 annual return | E4 annual RAP | Historical trades/week | Artifact |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        e4_row = row["e4_validation"] or {}
        historical_row = row["historical_activity_proxy"] or {}
        annual_return = e4_row.get("mean_annual_return")
        annual_rap = e4_row.get("mean_annual_rap")
        lines.append(
            "| {priority} | `{instrument}` | {role} | {timeframe} | {score:.1f} | "
            "{seeds} | {annual_return} | {annual_rap} | {trades} | `{artifact}` |".format(
                priority=row["priority"],
                instrument=row["oanda_instrument"],
                role=row["role"],
                timeframe=row["timeframe"],
                score=row["observation_priority_score"],
                seeds=e4_row.get("seed_count", "-"),
                annual_return=(
                    f"{100.0 * annual_return:+.3f}%"
                    if annual_return is not None
                    else "-"
                ),
                annual_rap=(
                    f"{100.0 * annual_rap:+.3f}%"
                    if annual_rap is not None
                    else "-"
                ),
                trades=(
                    f"{float(historical_row['mean_weekly_trades']):.3f}"
                    if historical_row.get("mean_weekly_trades") is not None
                    else "-"
                ),
                artifact=e4_row.get("best_artifact_job_id", "-"),
            )
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- Observe all listed instruments during the 24-hour read-only phase.",
            "- Use `USD_CAD` and `NZD_USD` as the first model-linked shadows.",
            "- Keep `GBP_JPY` and `USD_JPY` to expose the higher-activity path.",
            "- Keep `EUR_USD` as the execution control and `EUR_JPY` as a historical comparator.",
            "- Submit no order until account preflight, 24-hour observation, and explicit protected-canary authorization pass.",
            "",
            "One live day calibrates plumbing and costs. One live week supplies descriptive",
            "execution drift; it is not enough evidence to promote or reject an alpha model.",
            "",
        ]
    )
    (output_dir / "PROJECT3_OANDA_PRACTICE_ASSET_SELECTION_2026_07_29.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project3-db", required=True, type=Path)
    parser.add_argument("--evidence-db", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    e4 = load_e4_evidence(args.evidence_db)
    historical = load_historical_activity(args.project3_db)
    rows = build_selection(e4, historical)
    write_outputs(args.output_dir, rows)
    print(
        json.dumps(
            {
                "schema": SELECTION_SCHEMA,
                "asset_count": len(rows),
                "output_dir": str(args.output_dir),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
