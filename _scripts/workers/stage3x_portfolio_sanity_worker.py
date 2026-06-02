#!/usr/bin/env python3
"""Validate tiny Project 3 Stage 3X portfolio evidence fixtures.

This is a CPU-only mechanical guard. It proves that portfolio evidence can
represent per-asset accounting, portfolio accounting, broker trade-frequency
policy, and force-close fields without touching Stage C or launching training.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
WORKERS = Path(__file__).resolve().parent
if str(WORKERS) not in sys.path:
    sys.path.insert(0, str(WORKERS))

from stage3x_sac_smoke_result_synthesis_worker import (  # noqa: E402
    HELDOUT_START,
    infer_broker_profile,
    lookup_trade_frequency_policy,
    split_duration_weeks,
    trades_per_week,
)


OUT_ROOT = ROOT / "experiments" / "stage3x_portfolio_contract"
EVIDENCE_JSON = OUT_ROOT / "portfolio_evidence_fixture.json"
OUT_JSON = OUT_ROOT / "stage3x_portfolio_sanity_report.json"
OUT_MD = OUT_ROOT / "stage3x_portfolio_sanity_report.md"
CONTRACT_MD = OUT_ROOT / "portfolio_evidence_contract.md"

EVIDENCE_SCHEMA_VERSION = "project3_stage3x_portfolio_evidence_v1"
REPORT_SCHEMA_VERSION = "project3_stage3x_portfolio_sanity_report_v1"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_ts(value: Any) -> dt.datetime | None:
    if not value:
        return None
    text = str(value).replace("T", " ").replace("Z", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text[: len(fmt)], fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    try:
        parsed = dt.datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def add_issue(target: list[dict[str, Any]], code: str, severity: str, message: str, evidence: Any = None) -> None:
    target.append({"code": code, "severity": severity, "message": message, "evidence": evidence})


def build_fixture() -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "portfolio_id": "tiny_two_asset_fixture",
        "weekly_anchor_id": "anchor_2024-06-17",
        "first_timestamp": "2024-06-17 00:00:00",
        "last_timestamp": "2024-06-23 20:00:00",
        "portfolio_return": 0.0125,
        "portfolio_trades": 4,
        "portfolio_cost": 0.0014,
        "max_drawdown": -0.018,
        "cvar_95": -0.011,
        "allocation": {"eurusd": 0.6, "btcusdt_perp": 0.4},
        "no_trade_flags": {"eurusd": False, "btcusdt_perp": False},
        "assets": [
            {
                "asset": "eurusd",
                "timeframe": "4h",
                "broker_profile": "oanda_us_fx",
                "weight": 0.6,
                "net_return": 0.015,
                "trades": 1,
                "cost": 0.0004,
                "first_timestamp": "2024-06-17 00:00:00",
                "last_timestamp": "2024-06-23 20:00:00",
                "force_close_exposed_bars": 0,
                "friday_force_flat_violations": 0,
                "daily_break_trade_attempts": 0,
            },
            {
                "asset": "btcusdt_perp",
                "timeframe": "4h",
                "broker_profile": "crypto_exchange_perp",
                "weight": 0.4,
                "net_return": 0.00875,
                "trades": 3,
                "cost": 0.0010,
                "first_timestamp": "2024-06-17 00:00:00",
                "last_timestamp": "2024-06-23 20:00:00",
                "force_close_exposed_bars": 0,
                "friday_force_flat_violations": 0,
                "daily_break_trade_attempts": 0,
            },
        ],
    }


def timestamp_has_stage_c(value: Any) -> bool:
    ts = parse_ts(value)
    if ts is None:
        return False
    return ts.strftime("%Y-%m-%d") >= HELDOUT_START


def validate_evidence(evidence: dict[str, Any], *, tolerance: float = 1e-9) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    if evidence.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        add_issue(blockers, "BAD_PORTFOLIO_EVIDENCE_SCHEMA", "block", "Unexpected portfolio evidence schema.", evidence.get("schema_version"))
    if evidence.get("stage_c_access") != "DENIED" or evidence.get("stage_c_allowed") is True:
        add_issue(blockers, "PORTFOLIO_STAGE_C_NOT_DENIED", "block", "Portfolio evidence must deny Stage C.")
    if evidence.get("training_launched") is not False:
        add_issue(blockers, "PORTFOLIO_TRAINING_LAUNCHED_FLAG", "block", "Portfolio fixture must not claim training launched.")
    for key in ("first_timestamp", "last_timestamp"):
        if timestamp_has_stage_c(evidence.get(key)):
            add_issue(blockers, "PORTFOLIO_STAGE_C_TIMESTAMP", "block", f"Portfolio {key} crosses heldout boundary.", evidence.get(key))

    assets = evidence.get("assets") or []
    if not isinstance(assets, list) or not assets:
        add_issue(blockers, "PORTFOLIO_ASSETS_MISSING", "block", "Portfolio evidence must include at least one asset.")
        assets = []
    if len(assets) > 5:
        add_issue(blockers, "PORTFOLIO_TOO_MANY_ASSETS_FOR_SMOKE", "block", "Tiny portfolio smoke supports up to 5 assets.", len(assets))

    allocation = evidence.get("allocation") or {}
    if not isinstance(allocation, dict) or not allocation:
        add_issue(blockers, "PORTFOLIO_ALLOCATION_MISSING", "block", "Portfolio allocation map is required.")
        allocation = {}
    weight_sum = sum(float(v or 0.0) for v in allocation.values())
    if weight_sum <= 0 or weight_sum > 1.000000001:
        add_issue(blockers, "PORTFOLIO_WEIGHT_SUM_INVALID", "block", "Portfolio weights must sum within (0, 1].", weight_sum)

    aggregate_return = 0.0
    aggregate_trades = 0
    aggregate_cost = 0.0
    aggregate_hard_max = 0.0
    aggregate_warning_above = 0.0
    portfolio_weeks = split_duration_weeks(evidence.get("first_timestamp"), evidence.get("last_timestamp"))

    for asset_row in assets:
        asset = str(asset_row.get("asset") or "").lower()
        timeframe = str(asset_row.get("timeframe") or "").lower()
        broker_profile = str(asset_row.get("broker_profile") or "")
        if not broker_profile:
            broker_profile = infer_broker_profile(f"{asset}__{timeframe}").get("broker_profile", "")
        weight = float(asset_row.get("weight") or allocation.get(asset) or 0.0)
        net_return = float(asset_row.get("net_return") or 0.0)
        trades = int(asset_row.get("trades") or 0)
        cost = float(asset_row.get("cost") or 0.0)
        weeks = split_duration_weeks(asset_row.get("first_timestamp"), asset_row.get("last_timestamp"))
        tpw = trades_per_week(trades, weeks)
        policy = lookup_trade_frequency_policy(broker_profile, timeframe)
        row_blockers: list[str] = []
        row_warnings: list[str] = []

        for key in ("first_timestamp", "last_timestamp"):
            if timestamp_has_stage_c(asset_row.get(key)):
                row_blockers.append("ASSET_STAGE_C_TIMESTAMP")

        required_force_fields = ("force_close_exposed_bars", "friday_force_flat_violations", "daily_break_trade_attempts")
        missing_force = [key for key in required_force_fields if key not in asset_row]
        if missing_force:
            row_blockers.append("ASSET_FORCE_CLOSE_FIELDS_MISSING")
        if int(asset_row.get("friday_force_flat_violations") or 0) > 0:
            row_blockers.append("ASSET_FRIDAY_FORCE_FLAT_VIOLATION")
        if int(asset_row.get("daily_break_trade_attempts") or 0) > 0:
            row_blockers.append("ASSET_DAILY_BREAK_TRADE_ATTEMPT")

        if not policy.get("policy_known"):
            row_warnings.append("TRADE_FREQUENCY_POLICY_UNKNOWN")
        else:
            hard_max = float(policy["hard_max"])
            warning_above = float(policy["warning_above"])
            aggregate_hard_max += hard_max
            aggregate_warning_above += warning_above
            if tpw is not None and tpw > hard_max:
                row_blockers.append("ASSET_TRADE_FREQUENCY_HARD_MAX_EXCEEDED")
            elif tpw is not None and tpw > warning_above:
                row_warnings.append("ASSET_TRADE_FREQUENCY_WARNING_BAND_EXCEEDED")

        aggregate_return += weight * net_return
        aggregate_trades += trades
        aggregate_cost += cost
        rows.append(
            {
                "asset": asset,
                "timeframe": timeframe,
                "broker_profile": broker_profile,
                "weight": weight,
                "net_return": net_return,
                "trades": trades,
                "weeks": weeks,
                "trades_per_week": tpw,
                "trade_frequency_policy": policy,
                "blockers": row_blockers,
                "warnings": row_warnings,
            }
        )
        for code in row_blockers:
            add_issue(blockers, code, "block", f"{asset} failed portfolio asset sanity.", asset_row)
        for code in row_warnings:
            add_issue(warnings, code, "warn", f"{asset} raised portfolio asset warning.", asset_row)

    expected_return = float(evidence.get("portfolio_return") or 0.0)
    if abs(aggregate_return - expected_return) > tolerance:
        add_issue(
            blockers,
            "PORTFOLIO_RETURN_AGGREGATION_MISMATCH",
            "block",
            "Weighted per-asset returns do not match portfolio_return.",
            {"expected": expected_return, "computed": aggregate_return},
        )
    expected_trades = int(evidence.get("portfolio_trades") or 0)
    if aggregate_trades != expected_trades:
        add_issue(
            blockers,
            "PORTFOLIO_TRADE_COUNT_MISMATCH",
            "block",
            "Per-asset trades do not sum to portfolio_trades.",
            {"expected": expected_trades, "computed": aggregate_trades},
        )
    expected_cost = float(evidence.get("portfolio_cost") or 0.0)
    if abs(aggregate_cost - expected_cost) > tolerance:
        add_issue(
            blockers,
            "PORTFOLIO_COST_AGGREGATION_MISMATCH",
            "block",
            "Per-asset costs do not sum to portfolio_cost.",
            {"expected": expected_cost, "computed": aggregate_cost},
        )

    portfolio_tpw = trades_per_week(aggregate_trades, portfolio_weeks)
    if portfolio_tpw is not None and aggregate_hard_max > 0 and portfolio_tpw > aggregate_hard_max:
        add_issue(blockers, "PORTFOLIO_TRADE_FREQUENCY_HARD_MAX_EXCEEDED", "block", "Portfolio trades/week exceeds aggregate hard max.", portfolio_tpw)
    elif portfolio_tpw is not None and aggregate_warning_above > 0 and portfolio_tpw > aggregate_warning_above:
        add_issue(warnings, "PORTFOLIO_TRADE_FREQUENCY_WARNING_BAND_EXCEEDED", "warn", "Portfolio trades/week exceeds aggregate warning band.", portfolio_tpw)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "ok": not blockers,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "portfolio_id": evidence.get("portfolio_id"),
        "weekly_anchor_id": evidence.get("weekly_anchor_id"),
        "asset_count": len(assets),
        "portfolio_weeks": portfolio_weeks,
        "portfolio_trades_per_week": portfolio_tpw,
        "computed_portfolio_return": aggregate_return,
        "reported_portfolio_return": expected_return,
        "computed_portfolio_trades": aggregate_trades,
        "reported_portfolio_trades": expected_trades,
        "computed_portfolio_cost": aggregate_cost,
        "reported_portfolio_cost": expected_cost,
        "asset_rows": rows,
    }


def render_contract_md() -> str:
    return """# Project 3 Stage 3X Portfolio Evidence Contract

Schema: `project3_stage3x_portfolio_evidence_v1`

Required top-level fields:

- `stage_c_access: DENIED`
- `stage_c_allowed: false`
- `training_launched: false`
- `portfolio_id`
- `weekly_anchor_id`
- `first_timestamp`
- `last_timestamp`
- `portfolio_return`
- `portfolio_trades`
- `portfolio_cost`
- `allocation`
- `no_trade_flags`
- `assets`

Each asset row must include:

- `asset`
- `timeframe`
- `broker_profile`
- `weight`
- `net_return`
- `trades`
- `cost`
- `first_timestamp`
- `last_timestamp`
- `force_close_exposed_bars`
- `friday_force_flat_violations`
- `daily_break_trade_attempts`

Mechanical blockers:

- any 2025-01-01+ timestamp in non-Stage-C evidence;
- Stage C not denied;
- missing per-asset accounting;
- per-asset returns/costs/trades do not aggregate to portfolio totals;
- missing force-close fields;
- OANDA FX force-close/daily-break violations;
- per-asset or portfolio trade frequency above the broker/timeframe hard max.

Negative returns are not blockers here. They are optimizer objectives.
"""


def render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X Portfolio Sanity Report",
        "",
        f"- schema_version: `{report['schema_version']}`",
        f"- ok: `{str(report['ok']).lower()}`",
        f"- stage_c_access: `{report['stage_c_access']}`",
        f"- training_launched: `{str(report['training_launched']).lower()}`",
        f"- blockers: `{report['blocker_count']}`",
        f"- warnings: `{report['warning_count']}`",
        f"- portfolio_trades_per_week: `{report['portfolio_trades_per_week']}`",
        "",
        "## Assets",
        "",
        "| asset | broker | weight | return | trades | trades/week | blockers | warnings |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in report["asset_rows"]:
        lines.append(
            f"| `{row['asset']}` | `{row['broker_profile']}` | {row['weight']:.4f} | {row['net_return']:.6f} | {row['trades']} | {row['trades_per_week'] if row['trades_per_week'] is not None else ''} | {','.join(row['blockers'])} | {','.join(row['warnings'])} |"
        )
    if report["blockers"]:
        lines.extend(["", "## Blockers", ""])
        for issue in report["blockers"]:
            lines.append(f"- `{issue['code']}`: {issue['message']}")
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for issue in report["warnings"]:
            lines.append(f"- `{issue['code']}`: {issue['message']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-json", type=Path, default=EVIDENCE_JSON)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--write-fixture-if-missing", action="store_true")
    args = parser.parse_args()
    if not args.evidence_json.exists():
        if not args.write_fixture_if_missing:
            raise SystemExit(f"Evidence fixture missing: {args.evidence_json}")
        write_json(args.evidence_json, build_fixture())
    evidence = load_json(args.evidence_json)
    report = validate_evidence(evidence)
    args.out_root.mkdir(parents=True, exist_ok=True)
    out_json = args.out_root / "stage3x_portfolio_sanity_report.json"
    out_md = args.out_root / "stage3x_portfolio_sanity_report.md"
    contract_md = args.out_root / "portfolio_evidence_contract.md"
    write_json(out_json, report)
    out_md.write_text(render_md(report), encoding="utf-8")
    contract_md.write_text(render_contract_md(), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "blocker_count": report["blocker_count"],
                "warning_count": report["warning_count"],
                "asset_count": report["asset_count"],
                "stage_c_access": report["stage_c_access"],
                "training_launched": report["training_launched"],
                "out_json": str(out_json),
                "out_md": str(out_md),
                "contract_md": str(contract_md),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

