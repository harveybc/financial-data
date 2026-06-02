#!/usr/bin/env python3
"""Audit Project 3 data-context gaps after the pragmatic Stage B run.

This worker is intentionally read/report only. It checks whether the data shown
to RL policies exposes deterministic session context that the execution strategy
already enforces, and whether paid/source-family variants are represented in the
current Stage B diagnostic lane. It does not launch training and does not read
Stage C rows for evaluation.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPO_PARENT = ROOT.parent
OUT_DIR = ROOT / "experiments" / "stage_b_validation" / "hardening"
OUT_JSON = OUT_DIR / "data_context_gap_audit.json"
OUT_MD = OUT_DIR / "data_context_gap_audit.md"

PREPROCESSOR_ETH_TECH_STAT = (
    REPO_PARENT / "preprocessor" / "examples" / "data" / "ethusdt_4h_tech_stat_full_model_ready.csv"
)
PAID_CRYPTOQUANT_PLAN = ROOT / "experiments" / "paid_data_shadow_cryptoquant.yaml"
STAGEB_DIAG_INPUT_ROOT = ROOT / "experiments" / "stage_b_validation" / "diagnostic_inputs" / "ethusdt" / "4h"
STAGEB_PRAGMATIC_PLAN_ROOT = ROOT / "experiments" / "stage_b_validation" / "pragmatic_run_plan" / "plans"
GYM_FX_PREPROCESSOR = REPO_PARENT / "gym-fx" / "preprocessor_plugins" / "feature_window_preprocessor.py"

CALENDAR_RE = re.compile(
    r"(calendar|weekday|day_of_week|\bdow\b|hour_of_week|hour_of_day|"
    r"hours_to|bars_to|friday|force_close|session|entry_window)",
    re.IGNORECASE,
)
PAID_SOURCE_RE = re.compile(
    r"(cryptoquant|\bcq_|glassnode|coinmetrics|coinglass|funding|open_interest|"
    r"liquidation|exchange_flow|miner|reserve|onchain|fxmacro)",
    re.IGNORECASE,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_header(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def matching_columns(columns: list[str], pattern: re.Pattern[str]) -> list[str]:
    return [col for col in columns if pattern.search(col)]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def summarize_stageb_configs() -> dict[str, Any]:
    config_paths = list((ROOT / "experiments" / "stage_b_validation" / "run_plan" / "configs").glob("*.json"))
    config_paths.extend(STAGEB_PRAGMATIC_PLAN_ROOT.glob("**/config_out.json"))
    session_count = 0
    force_close_count = 0
    feature_names: set[str] = set()
    sampled = 0
    for path in config_paths:
        data = load_json(path)
        if not data:
            continue
        sampled += 1
        if data.get("session_filter") is True:
            session_count += 1
        if data.get("force_close_dow") == 4 and data.get("force_close_hour") == 20:
            force_close_count += 1
        features = data.get("feature_list")
        if isinstance(features, list):
            feature_names.update(str(item) for item in features)
    calendar_features = sorted(matching_columns(sorted(feature_names), CALENDAR_RE))
    paid_features = sorted(matching_columns(sorted(feature_names), PAID_SOURCE_RE))
    return {
        "config_files_seen": sampled,
        "session_filter_true_configs": session_count,
        "force_close_friday_20_configs": force_close_count,
        "unique_feature_count": len(feature_names),
        "calendar_feature_count": len(calendar_features),
        "calendar_features_sample": calendar_features[:40],
        "paid_source_feature_count": len(paid_features),
        "paid_source_features_sample": paid_features[:40],
    }


def summarize_diagnostic_variants() -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    if STAGEB_DIAG_INPUT_ROOT.exists():
        for csv_path in sorted(STAGEB_DIAG_INPUT_ROOT.glob("*/train.csv")):
            header = read_csv_header(csv_path)
            variants.append({
                "variant": csv_path.parent.name,
                "train_csv": str(csv_path),
                "columns": len(header),
                "calendar_columns": matching_columns(header, CALENDAR_RE),
                "paid_source_columns": matching_columns(header, PAID_SOURCE_RE),
            })
    return {
        "variant_count": len(variants),
        "session_calendar_variant_count": sum(1 for item in variants if item["calendar_columns"]),
        "paid_source_variant_count": sum(1 for item in variants if item["paid_source_columns"]),
        "variants": variants,
    }


def summarize_gym_fx_observation_context() -> dict[str, Any]:
    text = GYM_FX_PREPROCESSOR.read_text(encoding="utf-8") if GYM_FX_PREPROCESSOR.exists() else ""
    fields = {
        "position": "position" in text,
        "equity_norm": "equity_norm" in text,
        "unrealized_pnl_norm": "unrealized_pnl_norm" in text,
        "steps_remaining_norm": "steps_remaining_norm" in text,
        "bars_to_force_close": "bars_to_force_close" in text,
        "hours_to_force_close": "hours_to_force_close" in text,
    }
    return {
        "source_file": str(GYM_FX_PREPROCESSOR),
        "file_found": GYM_FX_PREPROCESSOR.exists(),
        "fields_detected": fields,
    }


def build_payload() -> dict[str, Any]:
    sample_header = read_csv_header(PREPROCESSOR_ETH_TECH_STAT)
    sample_calendar_cols = matching_columns(sample_header, CALENDAR_RE)
    sample_paid_cols = matching_columns(sample_header, PAID_SOURCE_RE)
    configs = summarize_stageb_configs()
    variants = summarize_diagnostic_variants()
    observation = summarize_gym_fx_observation_context()
    paid_plan_text = PAID_CRYPTOQUANT_PLAN.read_text(encoding="utf-8") if PAID_CRYPTOQUANT_PLAN.exists() else ""

    gaps: list[str] = []
    if not sample_calendar_cols and configs["force_close_friday_20_configs"] > 0:
        gaps.append("MODEL_READY_DATA_LACKS_EXPLICIT_TIME_TO_FRIDAY_CONTEXT")
    if not observation["fields_detected"]["bars_to_force_close"]:
        gaps.append("OBSERVATION_STATE_LACKS_BARS_TO_FORCE_CLOSE_CONTEXT")
    if PAID_CRYPTOQUANT_PLAN.exists() and variants["paid_source_variant_count"] == 0:
        gaps.append("PAID_CRYPTOQUANT_SHADOW_PLAN_NOT_IN_STAGEB_DIAGNOSTIC_VARIANTS")
    if variants["session_calendar_variant_count"] == 0:
        gaps.append("NO_SESSION_CALENDAR_DIAGNOSTIC_VARIANTS_MATERIALIZED")

    return {
        "schema_version": "project3_stage_b_data_context_gap_audit_v1",
        "generated_at": utc_now(),
        "stage_c_touched": False,
        "heldout_boundary": "2025-01-01",
        "sample_model_ready_file": str(PREPROCESSOR_ETH_TECH_STAT),
        "sample_model_ready_column_count": len(sample_header),
        "sample_calendar_columns": sample_calendar_cols,
        "sample_paid_source_columns": sample_paid_cols,
        "stage_b_config_summary": configs,
        "stage_b_diagnostic_variant_summary": variants,
        "gym_fx_observation_context": observation,
        "paid_cryptoquant_shadow_plan": {
            "path": str(PAID_CRYPTOQUANT_PLAN),
            "exists": PAID_CRYPTOQUANT_PLAN.exists(),
            "mentions_cryptoquant": "CryptoQuant" in paid_plan_text or "cryptoquant" in paid_plan_text.lower(),
        },
        "gaps": gaps,
        "recommended_next_tasks": [
            "Keep the Friday force-close rule, but add deterministic session/calendar context to candidate feature lists.",
            "Add bars/hours-to-force-close observation-state support in agent-multi/gym-fx if the CSV calendar columns are not enough.",
            "Build a paid-source diagnostic lane that compares best free feature stack against free-plus-CryptoQuant using matched asset/timeframe/seed/cost cells.",
            "Treat specialized open/close policy decomposition as a new strategy-family research lane, not as a silent change to the fixed PPO/SAC/DQN comparison.",
        ],
    }


def write_md(payload: dict[str, Any]) -> None:
    variants = payload["stage_b_diagnostic_variant_summary"]["variants"]
    lines = [
        "# Stage B Data Context Gap Audit",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Stage C touched: `{payload['stage_c_touched']}`",
        f"- Heldout boundary: `{payload['heldout_boundary']}`",
        f"- Sample model-ready file: `{payload['sample_model_ready_file']}`",
        f"- Sample model-ready calendar columns: `{len(payload['sample_calendar_columns'])}`",
        f"- Stage B configs with Friday 20:00 force-close: `{payload['stage_b_config_summary']['force_close_friday_20_configs']}`",
        f"- Diagnostic variants with session/calendar columns: `{payload['stage_b_diagnostic_variant_summary']['session_calendar_variant_count']}`",
        f"- Diagnostic variants with paid-source columns: `{payload['stage_b_diagnostic_variant_summary']['paid_source_variant_count']}`",
        "",
        "## Gaps",
        "",
    ]
    if payload["gaps"]:
        lines.extend(f"- `{gap}`" for gap in payload["gaps"])
    else:
        lines.append("- No hard data-context gaps detected by this audit.")
    lines.extend([
        "",
        "## Observation Context",
        "",
    ])
    fields = payload["gym_fx_observation_context"]["fields_detected"]
    for key, value in fields.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend([
        "",
        "## Diagnostic Variants",
        "",
        "| variant | columns | calendar cols | paid/source cols |",
        "| --- | ---: | ---: | ---: |",
    ])
    for item in variants:
        lines.append(
            f"| `{item['variant']}` | {item['columns']} | "
            f"{len(item['calendar_columns'])} | {len(item['paid_source_columns'])} |"
        )
    lines.extend([
        "",
        "## Recommended Next Tasks",
        "",
    ])
    lines.extend(f"- {task}" for task in payload["recommended_next_tasks"])
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_md(payload)
    print(json.dumps({
        "ok": True,
        "gaps": payload["gaps"],
        "report_json": str(OUT_JSON),
        "report_md": str(OUT_MD),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
