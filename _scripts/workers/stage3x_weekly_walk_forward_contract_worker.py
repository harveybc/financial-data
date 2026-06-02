#!/usr/bin/env python3
"""Emit Project 3 weekly walk-forward contract anchors.

This worker is CPU-only. It does not launch training. Its job is to make the
business mechanics explicit: weekend retrain, immediate validation week, next
week test, repeated across historical anchors, with Stage C denied.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "experiments" / "stage3x_weekly_walk_forward_contract"
OUT_JSON = OUT_ROOT / "stage3x_weekly_walk_forward_contract.json"
OUT_MD = OUT_ROOT / "stage3x_weekly_walk_forward_contract.md"

SCHEMA_VERSION = "project3_stage3x_weekly_walk_forward_contract_v1"
HELDOUT_START = dt.date(2025, 1, 1)

DEFAULT_TARGET_ASSETS = ("btcusdt_perp", "eurusd", "audusd")
DEFAULT_INPUT_ASSETS = (
    "btcusdt_perp",
    "ethusdt_perp",
    "eurusd",
    "audusd",
    "gbpusd",
    "usdjpy",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def monday_on_or_after(day: dt.date) -> dt.date:
    return day + dt.timedelta(days=(7 - day.weekday()) % 7)


def infer_broker_profile(asset: str) -> str:
    asset_l = asset.lower()
    fx = {
        "audusd",
        "eurusd",
        "gbpusd",
        "usdjpy",
        "usdcad",
        "usdchf",
        "nzdusd",
        "eurgbp",
        "xauusd",
    }
    if asset_l.endswith("_perp"):
        return "crypto_exchange_perp"
    if asset_l in fx:
        return "oanda_us_fx"
    return "spot_crypto_unconfirmed"


def build_anchor_dates(
    *,
    anchor_start: dt.date,
    anchor_end: dt.date,
    train_days: int,
    validation_days: int,
    test_days: int,
    max_anchors: int,
) -> list[dict[str, str]]:
    if min(train_days, validation_days, test_days, max_anchors) <= 0:
        raise ValueError("train_days, validation_days, test_days, and max_anchors must be positive")
    anchors: list[dict[str, str]] = []
    test_start = monday_on_or_after(anchor_start)
    while test_start <= anchor_end and len(anchors) < max_anchors:
        test_end = test_start + dt.timedelta(days=test_days - 1)
        validation_end = test_start - dt.timedelta(days=1)
        validation_start = validation_end - dt.timedelta(days=validation_days - 1)
        train_end = validation_start - dt.timedelta(days=1)
        train_start = train_end - dt.timedelta(days=train_days - 1)
        if test_end >= HELDOUT_START:
            break
        anchors.append(
            {
                "weekly_anchor_id": f"anchor_{test_start.isoformat()}",
                "train_start": train_start.isoformat(),
                "train_end": train_end.isoformat(),
                "validation_start": validation_start.isoformat(),
                "validation_end": validation_end.isoformat(),
                "test_start": test_start.isoformat(),
                "test_end": test_end.isoformat(),
            }
        )
        test_start += dt.timedelta(days=7)
    return anchors


def _csv_tokens(value: str | None, default: tuple[str, ...]) -> list[str]:
    if not value:
        return list(default)
    return [token.strip().lower() for token in value.split(",") if token.strip()]


def build_contract(
    *,
    mode: str,
    anchor_start: dt.date,
    anchor_end: dt.date,
    train_days: int,
    validation_days: int,
    test_days: int,
    max_anchors: int,
    target_assets: list[str],
    input_assets: list[str],
) -> dict[str, Any]:
    anchors = build_anchor_dates(
        anchor_start=anchor_start,
        anchor_end=anchor_end,
        train_days=train_days,
        validation_days=validation_days,
        test_days=test_days,
        max_anchors=max_anchors,
    )
    contracts: list[dict[str, Any]] = []
    for anchor in anchors:
        for target_asset in target_assets:
            target = target_asset.lower()
            contracts.append(
                {
                    "contract_id": f"{target}__weekly__{anchor['weekly_anchor_id']}",
                    "weekly_anchor_id": anchor["weekly_anchor_id"],
                    "target_asset": target,
                    "broker_profile": infer_broker_profile(target),
                    "own_asset_inputs": True,
                    "input_asset_mask": [asset for asset in input_assets if asset != target],
                    "input_source_mask": [
                        "own_asset_ohlcv",
                        "cross_asset_ohlcv",
                        "technical_statistical",
                        "seasonal_calendar",
                        "broker_force_close_context",
                    ],
                    "feature_family_mask": [
                        "returns",
                        "volatility",
                        "trend",
                        "momentum",
                        "liquidity",
                        "seasonal_sin_cos",
                        "force_close_state",
                    ],
                    "preprocessing_profile": "stage3x_weekly_default_v1",
                    **anchor,
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "mode": mode,
        "heldout_start": HELDOUT_START.isoformat(),
        "train_days": train_days,
        "validation_days": validation_days,
        "test_days": test_days,
        "anchor_count": len(anchors),
        "contract_count": len(contracts),
        "target_assets": target_assets,
        "input_assets": input_assets,
        "anchors": anchors,
        "contracts": contracts,
        "rules": {
            "test_window_is_next_week_only": True,
            "target_asset_is_distinct_from_input_asset_mask": True,
            "stage_c_rows_forbidden": True,
            "negative_returns_are_optimizer_objectives": True,
            "mechanical_blockers_remain_fail_closed": True,
        },
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X Weekly Walk-Forward Contract",
        "",
        f"- schema_version: `{payload['schema_version']}`",
        f"- stage_c_access: `{payload['stage_c_access']}`",
        f"- training_launched: `{str(payload['training_launched']).lower()}`",
        f"- mode: `{payload['mode']}`",
        f"- anchors: `{payload['anchor_count']}`",
        f"- contracts: `{payload['contract_count']}`",
        f"- train_days: `{payload['train_days']}`",
        f"- validation_days: `{payload['validation_days']}`",
        f"- test_days: `{payload['test_days']}`",
        "",
        "## Anchors",
        "",
        "| anchor | train | validation | test |",
        "| --- | --- | --- | --- |",
    ]
    for anchor in payload["anchors"]:
        lines.append(
            "| {weekly_anchor_id} | {train_start} to {train_end} | {validation_start} to {validation_end} | {test_start} to {test_end} |".format(
                **anchor
            )
        )
    lines.extend(
        [
            "",
            "## First Contracts",
            "",
            "| contract | target | broker | input assets |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in payload["contracts"][:20]:
        lines.append(
            f"| `{row['contract_id']}` | `{row['target_asset']}` | `{row['broker_profile']}` | `{','.join(row['input_asset_mask'])}` |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_root: Path) -> tuple[Path, Path]:
    out_root.mkdir(parents=True, exist_ok=True)
    out_json = out_root / "stage3x_weekly_walk_forward_contract.json"
    out_md = out_root / "stage3x_weekly_walk_forward_contract.md"
    out_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")
    return out_json, out_md


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["tiny", "search"], default="tiny")
    parser.add_argument("--anchor-start", default="2024-06-03")
    parser.add_argument("--anchor-end", default="2024-08-26")
    parser.add_argument("--train-days", type=int, default=None)
    parser.add_argument("--validation-days", type=int, default=7)
    parser.add_argument("--test-days", type=int, default=7)
    parser.add_argument("--max-anchors", type=int, default=4)
    parser.add_argument("--target-assets", default=None)
    parser.add_argument("--input-assets", default=None)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = parser.parse_args()
    train_days = args.train_days if args.train_days is not None else (14 if args.mode == "tiny" else 365)
    payload = build_contract(
        mode=args.mode,
        anchor_start=parse_date(args.anchor_start),
        anchor_end=parse_date(args.anchor_end),
        train_days=train_days,
        validation_days=args.validation_days,
        test_days=args.test_days,
        max_anchors=args.max_anchors,
        target_assets=_csv_tokens(args.target_assets, DEFAULT_TARGET_ASSETS),
        input_assets=_csv_tokens(args.input_assets, DEFAULT_INPUT_ASSETS),
    )
    out_json, out_md = write_outputs(payload, args.out_root)
    print(
        json.dumps(
            {
                "anchor_count": payload["anchor_count"],
                "contract_count": payload["contract_count"],
                "stage_c_access": payload["stage_c_access"],
                "training_launched": payload["training_launched"],
                "out_json": str(out_json),
                "out_md": str(out_md),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

