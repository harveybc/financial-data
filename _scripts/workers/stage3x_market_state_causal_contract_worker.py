#!/usr/bin/env python3
"""Emit a weekly market-state causal-audit contract for Project 3.

The contract maps the user's patient/medicine/outcome analogy onto the weekly
trading system:

- patient: target asset at a weekly decision anchor;
- patient state: market-state summary known before the decision cutoff;
- "medicine": observed exposure/input families available to the model or
  supervisor before the cutoff;
- outcome: next-week market-status vector.

This worker does not estimate causal effects. It creates the fail-closed data
contract needed before EconML/DoWhy/DoubleML-style estimators or invariant
screening are allowed to consume the weekly panel.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WEEKLY_CONTRACT = (
    ROOT
    / "experiments"
    / "stage3x_weekly_walk_forward_contract"
    / "stage3x_weekly_walk_forward_contract.json"
)
OUT_ROOT = ROOT / "experiments" / "stage3x_market_state_causal_contract"

SCHEMA_VERSION = "project3_stage3x_market_state_causal_contract_v1"
HELDOUT_START = dt.date(2025, 1, 1)
DEFAULT_PRETRADE_GAP_HOURS = 12
DEFAULT_LOOKBACK_HOURS = 7 * 24

STATE_FEATURE_FAMILIES = [
    "own_asset_return_vol_trend_liquidity",
    "cross_asset_return_vol_correlation",
    "seasonal_calendar_sin_cos",
    "force_close_calendar_context",
    "event_calendar_known_before_cutoff",
    "train_only_regime_probabilities",
    "train_only_ood_scores",
]

EXPOSURE_TREATMENT_FAMILIES = [
    "own_asset_feature_family_enabled",
    "cross_asset_feature_family_enabled",
    "macro_event_feature_family_enabled",
    "regime_context_enabled",
    "ood_overlay_enabled",
    "portfolio_no_trade_flag",
    "portfolio_weight_bucket",
]

OUTCOME_COMPONENTS = [
    "next_week_net_return",
    "next_week_realized_volatility",
    "next_week_max_drawdown",
    "next_week_cvar_95",
    "next_week_trade_count",
    "next_week_force_close_violations",
    "next_week_trend_score",
    "next_week_regime_transition_summary",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_date(value: Any) -> dt.date:
    return dt.date.fromisoformat(str(value))


def parse_dt(value: Any) -> dt.datetime:
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text[: len(fmt)], fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    parsed = dt.datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _date_to_utc_start(day: str) -> dt.datetime:
    return dt.datetime.combine(parse_date(day), dt.time(0, 0), tzinfo=dt.timezone.utc)


def _date_to_utc_end(day: str) -> dt.datetime:
    return dt.datetime.combine(parse_date(day), dt.time(23, 59, 59), tzinfo=dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_temporal_row(row: dict[str, Any], *, pretrade_gap_hours: int) -> list[str]:
    issues: list[str] = []
    obs_start = parse_dt(row["observation_window_start"])
    obs_end = parse_dt(row["observation_window_end"])
    decision_cutoff = parse_dt(row["decision_cutoff"])
    outcome_start = parse_dt(row["outcome_window_start"])
    outcome_end = parse_dt(row["outcome_window_end"])
    required_gap = dt.timedelta(hours=pretrade_gap_hours)
    if not obs_start <= obs_end <= decision_cutoff:
        issues.append("OBSERVATION_WINDOW_NOT_BEFORE_DECISION_CUTOFF")
    if decision_cutoff + required_gap > outcome_start:
        issues.append("PRETRADE_GAP_TOO_SMALL")
    if not outcome_start < outcome_end:
        issues.append("OUTCOME_WINDOW_INVALID")
    if outcome_end.date() >= HELDOUT_START:
        issues.append("STAGE_C_OUTCOME_WINDOW")
    return issues


def build_rows(
    weekly_contract: dict[str, Any],
    *,
    pretrade_gap_hours: int,
    lookback_hours: int,
    state_encoding_mode: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for contract in weekly_contract.get("contracts") or []:
        outcome_start = _date_to_utc_start(contract["test_start"])
        outcome_end = _date_to_utc_end(contract["test_end"])
        if outcome_end.date() >= HELDOUT_START:
            continue
        decision_cutoff = outcome_start - dt.timedelta(hours=pretrade_gap_hours)
        observation_end = decision_cutoff
        if state_encoding_mode == "snapshot":
            observation_start = observation_end
        else:
            observation_start = observation_end - dt.timedelta(hours=lookback_hours)
        row = {
            "causal_unit_id": f"{contract['contract_id']}__causal_state",
            "weekly_anchor_id": contract["weekly_anchor_id"],
            "target_asset": contract["target_asset"],
            "broker_profile": contract.get("broker_profile"),
            "state_encoding_mode": state_encoding_mode,
            "observation_window_start": _iso(observation_start),
            "observation_window_end": _iso(observation_end),
            "decision_cutoff": _iso(decision_cutoff),
            "pretrade_gap_hours": pretrade_gap_hours,
            "outcome_window_start": _iso(outcome_start),
            "outcome_window_end": _iso(outcome_end),
            "input_asset_mask": contract.get("input_asset_mask") or [],
            "patient_state_feature_families": STATE_FEATURE_FAMILIES,
            "exposure_treatment_families": EXPOSURE_TREATMENT_FAMILIES,
            "outcome_components": OUTCOME_COMPONENTS,
            "allowed_estimators": [
                "blocked_time_series_cross_fit_double_ml",
                "doubly_robust_learners",
                "causal_forest_as_diagnostic",
                "invariant_risk_screening",
                "lag_only_conditional_dependence_screen",
            ],
            "forbidden_uses": [
                "causal_alpha_proof",
                "automatic_feature_deletion",
                "validation_tuned_threshold_without_trial_count",
                "stage_c_tuning",
            ],
        }
        row["temporal_issues"] = validate_temporal_row(row, pretrade_gap_hours=pretrade_gap_hours)
        rows.append(row)
    return rows


def build_contract(
    *,
    weekly_contract: dict[str, Any],
    pretrade_gap_hours: int,
    lookback_hours: int,
    state_encoding_mode: str,
) -> dict[str, Any]:
    if pretrade_gap_hours < 6:
        raise ValueError("pretrade_gap_hours must be at least 6")
    if lookback_hours <= 0:
        raise ValueError("lookback_hours must be positive")
    if state_encoding_mode not in {"window_summary", "snapshot"}:
        raise ValueError("state_encoding_mode must be window_summary or snapshot")
    rows = build_rows(
        weekly_contract,
        pretrade_gap_hours=pretrade_gap_hours,
        lookback_hours=lookback_hours,
        state_encoding_mode=state_encoding_mode,
    )
    issue_rows = [row for row in rows if row["temporal_issues"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "heldout_start": HELDOUT_START.isoformat(),
        "pretrade_gap_hours": pretrade_gap_hours,
        "lookback_hours": lookback_hours,
        "state_encoding_mode": state_encoding_mode,
        "causal_role_mapping": {
            "patient": "target_asset_at_weekly_anchor",
            "patient_state": "market_state_observed_before_decision_cutoff",
            "medicine": "observed_input_or_supervisor_exposure_defined_before_cutoff",
            "outcome": "next_week_market_status_vector",
        },
        "assumption_notes": [
            "Observed market features are not randomized treatments.",
            "Causal estimators are diagnostic screens and hypothesis generators.",
            "Trading promotion still requires paired RL evidence, costs, seeds, and gates.",
            "Weekend border data must be excluded by the pretrade gap before weekly open.",
        ],
        "row_count": len(rows),
        "temporal_issue_count": len(issue_rows),
        "ok": len(rows) > 0 and not issue_rows,
        "rows": rows,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X Market-State Causal Contract",
        "",
        f"- schema_version: `{payload['schema_version']}`",
        f"- ok: `{str(payload['ok']).lower()}`",
        f"- stage_c_access: `{payload['stage_c_access']}`",
        f"- training_launched: `{str(payload['training_launched']).lower()}`",
        f"- pretrade_gap_hours: `{payload['pretrade_gap_hours']}`",
        f"- lookback_hours: `{payload['lookback_hours']}`",
        f"- state_encoding_mode: `{payload['state_encoding_mode']}`",
        f"- rows: `{payload['row_count']}`",
        f"- temporal_issue_count: `{payload['temporal_issue_count']}`",
        "",
        "## Role Mapping",
        "",
    ]
    for key, value in payload["causal_role_mapping"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| unit | target | obs window | cutoff | outcome window | issues |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["rows"][:30]:
        lines.append(
            f"| `{row['causal_unit_id']}` | `{row['target_asset']}` | {row['observation_window_start']} to {row['observation_window_end']} | {row['decision_cutoff']} | {row['outcome_window_start']} to {row['outcome_window_end']} | {','.join(row['temporal_issues'])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weekly-contract", type=Path, default=DEFAULT_WEEKLY_CONTRACT)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--pretrade-gap-hours", type=int, default=DEFAULT_PRETRADE_GAP_HOURS)
    parser.add_argument("--lookback-hours", type=int, default=DEFAULT_LOOKBACK_HOURS)
    parser.add_argument("--state-encoding-mode", choices=["window_summary", "snapshot"], default="window_summary")
    args = parser.parse_args()
    weekly = load_json(args.weekly_contract)
    payload = build_contract(
        weekly_contract=weekly,
        pretrade_gap_hours=args.pretrade_gap_hours,
        lookback_hours=args.lookback_hours,
        state_encoding_mode=args.state_encoding_mode,
    )
    args.out_root.mkdir(parents=True, exist_ok=True)
    out_json = args.out_root / "stage3x_market_state_causal_contract.json"
    out_md = args.out_root / "stage3x_market_state_causal_contract.md"
    write_json(out_json, payload)
    out_md.write_text(render_md(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "row_count": payload["row_count"],
                "temporal_issue_count": payload["temporal_issue_count"],
                "stage_c_access": payload["stage_c_access"],
                "training_launched": payload["training_launched"],
                "out_json": str(out_json),
                "out_md": str(out_md),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
