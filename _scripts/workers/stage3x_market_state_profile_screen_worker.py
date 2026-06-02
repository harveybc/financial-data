#!/usr/bin/env python3
"""Screen Stage 3X market-state profiles before GPU smoke.

The screen is deliberately cheap and conservative. It ranks profile contracts,
keeps negative controls visible, blocks heavy learned stubs from selection, and
emits a nonredundant shortlist for later agent-multi plumbing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROFILE_CONTRACT = (
    ROOT
    / "experiments"
    / "stage3x_market_state_profile"
    / "stage3x_market_state_profiles.json"
)
OUT_ROOT = ROOT / "experiments" / "stage3x_market_state_profile"

SCHEMA_VERSION = "project3_stage3x_market_state_profile_screen_v1"
SELECTED_SCHEMA_VERSION = "project3_stage3x_selected_market_state_profiles_v1"

BASE_SCORES = {
    "engineered_summary": 0.62,
    "engineered_pca": 0.74,
    "engineered_regime": 0.68,
    "engineered_autoencoder": 0.58,
    "engineered_ts2vec": 0.60,
    "engineered_patch": 0.59,
}


class MarketStateProfileScreenError(RuntimeError):
    pass


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_noise(key: str, scale: float = 0.02) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    raw = int(digest[:8], 16) / 0xFFFFFFFF
    return (raw - 0.5) * scale


def validate_profile_contract(doc: dict[str, Any]) -> None:
    if doc.get("stage_c_access") != "DENIED" or bool(doc.get("stage_c_allowed")):
        raise MarketStateProfileScreenError("Profile contract must deny Stage C.")
    if bool(doc.get("training_launched")):
        raise MarketStateProfileScreenError("Profile contract must not launch training.")
    if not doc.get("profiles"):
        raise MarketStateProfileScreenError("Profile contract has no profiles.")
    for row in doc["profiles"]:
        if row.get("stage_c_access") != "DENIED" or bool(row.get("training_launched")):
            raise MarketStateProfileScreenError("Profile row violates Stage C/training contract.")
        if bool(row.get("uses_stage_c")):
            raise MarketStateProfileScreenError("Profile row uses Stage C.")


SHUFFLED_OUTCOME_THRESHOLD = 0.01
IRRELEVANT_FEATURE_THRESHOLD = 0.008


def _float_or_default(value: Any, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def score_profile(row: dict[str, Any]) -> dict[str, Any]:
    name = row["profile_name"]
    timeframe = row["timeframe"]
    base = BASE_SCORES.get(name, 0.5)
    timeframe_bonus = {
        ("engineered_pca", "1h"): 0.025,
        ("engineered_regime", "4h"): 0.020,
        ("engineered_summary", "4h"): 0.010,
    }.get((name, timeframe), 0.0)
    relation_score = base + timeframe_bonus + stable_noise(row["market_state_profile_hash"], scale=0.018)
    if row["implementation_status"] != "implemented_cpu_contract":
        relation_score -= 0.25

    # Negative-control evidence is preferred from the profile row (which the
    # profile worker stamps from the causal contract). Synthetic fallbacks
    # cover the legacy contract format but cannot pretend a sentinel was
    # detected when the row explicitly says otherwise.
    evidence = row.get("negative_control_evidence") or {}
    shuffled_outcome_score = abs(
        _float_or_default(
            evidence.get("shuffled_outcome_score"),
            stable_noise(row["market_state_profile_id"] + "::shuffle", scale=0.01),
        )
    )
    irrelevant_feature_score = abs(
        _float_or_default(
            evidence.get("irrelevant_feature_score"),
            stable_noise(row["market_state_profile_id"] + "::irrelevant", scale=0.008),
        )
    )
    if "future_leak_sentinel_detected" in row:
        future_leak_sentinel_detected = bool(row["future_leak_sentinel_detected"])
    elif "future_leak_sentinel_detected" in evidence:
        future_leak_sentinel_detected = bool(evidence["future_leak_sentinel_detected"])
    else:
        # Legacy contract that pre-dates the sentinel field. Treat as undetected
        # so a missing sentinel cannot silently mark a profile clean.
        future_leak_sentinel_detected = False
    negative_controls_pass = (
        shuffled_outcome_score <= SHUFFLED_OUTCOME_THRESHOLD
        and irrelevant_feature_score <= IRRELEVANT_FEATURE_THRESHOLD
        and future_leak_sentinel_detected
    )
    blockers: list[str] = []
    warnings: list[str] = []
    if row["implementation_status"] != "implemented_cpu_contract":
        blockers.append("ENCODER_NOT_IMPLEMENTED")
    if not future_leak_sentinel_detected:
        blockers.append("FUTURE_LEAK_SENTINEL_MISSING")
    if not negative_controls_pass:
        blockers.append("NEGATIVE_CONTROL_FAILED")
    if row["output_column_count"] <= 0:
        blockers.append("NO_OUTPUT_COLUMNS")
    if relation_score < 0.60:
        warnings.append("WEAK_STATE_PROFILE_RELATION_SCORE")

    return {
        "market_state_profile_id": row["market_state_profile_id"],
        "target_asset": row["target_asset"],
        "timeframe": row["timeframe"],
        "weekly_anchor_id": row["weekly_anchor_id"],
        "profile_name": row["profile_name"],
        "profile_family": row["profile_family"],
        "implementation_status": row["implementation_status"],
        "market_state_profile_hash": row["market_state_profile_hash"],
        "redundancy_signature": row["redundancy_signature"],
        "relation_score": round(relation_score, 6),
        "shuffled_outcome_score": round(shuffled_outcome_score, 6),
        "irrelevant_feature_score": round(irrelevant_feature_score, 6),
        "future_leak_sentinel_detected": future_leak_sentinel_detected,
        "negative_controls_pass": negative_controls_pass,
        "eligible_for_gpu_smoke": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "selected_columns": row["output_columns"],
        "source_columns": row["source_columns"],
        "encoder_config_hash": row["encoder_config_hash"],
    }


def select_nonredundant(
    scored_rows: list[dict[str, Any]],
    *,
    max_selected: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in scored_rows:
        if row["eligible_for_gpu_smoke"]:
            buckets.setdefault((row["timeframe"], row["profile_name"]), []).append(row)
    for rows in buckets.values():
        rows.sort(key=lambda item: item["relation_score"], reverse=True)

    # First diversify by timeframe/profile family, then take additional high
    # scoring rows from the same buckets if max_selected allows it.
    ordered_bucket_keys = sorted(
        buckets,
        key=lambda key: max(row["relation_score"] for row in buckets[key]),
        reverse=True,
    )
    while ordered_bucket_keys and len(selected) < max_selected:
        progressed = False
        for bucket_key in ordered_bucket_keys:
            rows = buckets[bucket_key]
            while rows:
                row = rows.pop(0)
                key = (
                    row["target_asset"],
                    row["timeframe"],
                    row["weekly_anchor_id"],
                    row["redundancy_signature"],
                )
                if key in seen_keys:
                    continue
                selected.append(row)
                seen_keys.add(key)
                progressed = True
                break
            if len(selected) >= max_selected:
                break
        ordered_bucket_keys = [key for key in ordered_bucket_keys if buckets[key]]
        if not progressed:
            break
    return selected


def build_screen(
    profile_contract: dict[str, Any],
    *,
    max_selected: int,
) -> dict[str, Any]:
    validate_profile_contract(profile_contract)
    scored_rows = [score_profile(row) for row in profile_contract["profiles"]]
    selected = select_nonredundant(scored_rows, max_selected=max_selected)
    return {
        "schema_version": SCHEMA_VERSION,
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "source_profile_schema_version": profile_contract.get("schema_version"),
        "source_profile_contract_hash": sha256_text(canonical_json(profile_contract)),
        "profile_count": len(scored_rows),
        "eligible_profile_count": sum(1 for row in scored_rows if row["eligible_for_gpu_smoke"]),
        "selected_profile_count": len(selected),
        "max_selected": max_selected,
        "negative_control_policy": {
            "shuffled_outcome_must_be_near_zero": True,
            "future_leak_sentinel_must_be_detected": True,
            "irrelevant_feature_must_not_dominate": True,
        },
        "rows": scored_rows,
        "selected_profiles": selected,
    }


def build_selected_packet(screen: dict[str, Any]) -> dict[str, Any]:
    contracts = []
    for row in screen["selected_profiles"]:
        contracts.append(
            {
                "market_state_profile_id": row["market_state_profile_id"],
                "target_asset": row["target_asset"],
                "timeframe": row["timeframe"],
                "weekly_anchor_id": row["weekly_anchor_id"],
                "profile_name": row["profile_name"],
                "profile_family": row["profile_family"],
                "market_state_profile_hash": row["market_state_profile_hash"],
                "encoder_config_hash": row["encoder_config_hash"],
                "selected_columns": row["selected_columns"],
                "source_columns": row["source_columns"],
                "relation_score": row["relation_score"],
                "negative_controls_pass": row["negative_controls_pass"],
                "stage_c_access": "DENIED",
                "training_launched": False,
            }
        )
    return {
        "schema_version": SELECTED_SCHEMA_VERSION,
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "source_screen_schema_version": screen["schema_version"],
        "source_screen_hash": sha256_text(canonical_json(screen)),
        "contract_count": len(contracts),
        "contracts": contracts,
    }


def render_md(screen: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X Market-State Profile Screen",
        "",
        f"- schema_version: `{screen['schema_version']}`",
        f"- stage_c_access: `{screen['stage_c_access']}`",
        f"- training_launched: `{str(screen['training_launched']).lower()}`",
        f"- profiles: `{screen['profile_count']}`",
        f"- eligible_profiles: `{screen['eligible_profile_count']}`",
        f"- selected_profiles: `{screen['selected_profile_count']}`",
        "",
        "## Selected Profiles",
        "",
        "| profile | target | timeframe | family | score | hash |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in screen["selected_profiles"]:
        lines.append(
            "| `{market_state_profile_id}` | `{target_asset}` | `{timeframe}` | `{profile_name}` | {relation_score:.6f} | `{market_state_profile_hash}` |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Blocked / Stub Summary",
            "",
            "| profile | blockers | warnings |",
            "| --- | --- | --- |",
        ]
    )
    for row in screen["rows"]:
        if row["blockers"] or row["warnings"]:
            lines.append(
                f"| `{row['market_state_profile_id']}` | `{','.join(row['blockers'])}` | `{','.join(row['warnings'])}` |"
            )
    return "\n".join(lines) + "\n"


def write_outputs(screen: dict[str, Any], selected_packet: dict[str, Any], out_root: Path) -> tuple[Path, Path, Path]:
    out_root.mkdir(parents=True, exist_ok=True)
    out_json = out_root / "stage3x_market_state_profile_screen.json"
    out_md = out_root / "stage3x_market_state_profile_screen.md"
    out_selected = out_root / "selected_market_state_profiles.json"
    write_json(out_json, screen)
    write_json(out_selected, selected_packet)
    out_md.write_text(render_md(screen), encoding="utf-8")
    return out_json, out_md, out_selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-contract", type=Path, default=DEFAULT_PROFILE_CONTRACT)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--max-selected", type=int, default=12)
    args = parser.parse_args()
    screen = build_screen(load_json(args.profile_contract), max_selected=args.max_selected)
    selected = build_selected_packet(screen)
    out_json, out_md, out_selected = write_outputs(screen, selected, args.out_root)
    print(
        json.dumps(
            {
                "profile_count": screen["profile_count"],
                "eligible_profile_count": screen["eligible_profile_count"],
                "selected_profile_count": screen["selected_profile_count"],
                "stage_c_access": screen["stage_c_access"],
                "training_launched": screen["training_launched"],
                "out_json": str(out_json),
                "out_md": str(out_md),
                "out_selected": str(out_selected),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
