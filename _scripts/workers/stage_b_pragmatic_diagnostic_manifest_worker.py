#!/usr/bin/env python3
"""Emit the locked pragmatic Stage B diagnostic manifest.

This worker converts the next-decision spec into machine-readable artifacts.
It does not launch training and does not inspect Stage C. The generated
manifest is intentionally a plan packet: it can be handed to agent-multi only
after the missing feature/cost infrastructure is implemented and explicitly
approved.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "experiments" / "stage_b_validation" / "manifests"
EXPERIMENT_ID = "stageb_ethusdt_4h_sac_pragmatic_diagnostic_v1"
HELDOUT_START = "2025-01-01"

OUT_JSON = OUT_DIR / f"{EXPERIMENT_ID}.json"
OUT_YAML = OUT_DIR / f"{EXPERIMENT_ID}.yaml"
OUT_MD = OUT_DIR / f"{EXPERIMENT_ID}.md"
OUT_COST_YAML = OUT_DIR / "cost_scenario_manifest.yaml"
OUT_COST_JSON = OUT_DIR / "cost_scenario_manifest.json"

SEEDS = [0, 1, 2, 3, 4]
COST_SCENARIOS = [
    {
        "name": "base",
        "fee_multiplier": 1.0,
        "slippage_multiplier": 1.0,
        "role": "minimum_realistic_cost",
    },
    {
        "name": "plus_50pct",
        "fee_multiplier": 1.5,
        "slippage_multiplier": 1.5,
        "role": "moderate_cost_stress",
    },
    {
        "name": "plus_100pct",
        "fee_multiplier": 2.0,
        "slippage_multiplier": 2.0,
        "role": "hard_cost_stress",
    },
]

FEATURE_VARIANTS = [
    {
        "name": "baseline_12",
        "feature_family": "baseline",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Does the candidate beat a compact OHLCV baseline?",
    },
    {
        "name": "tech_stat_full",
        "feature_family": "technical_statistical",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Does the broad technical/statistical family still carry signal?",
    },
    {
        "name": "tech_stat_reduced_corr_v1",
        "feature_family": "technical_statistical_reduced",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Is the full tech_stat family too redundant/noisy?",
    },
    {
        "name": "tech_stat_volatility_only",
        "feature_family": "technical_statistical_volatility",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Are volatility features driving useful behavior?",
    },
    {
        "name": "tech_stat_trend_only",
        "feature_family": "technical_statistical_trend",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Are trend features driving useful behavior?",
    },
    {
        "name": "tech_stat_momentum_only",
        "feature_family": "technical_statistical_momentum",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Are momentum features driving useful behavior?",
    },
    {
        "name": "tech_stat_volume_liquidity_only",
        "feature_family": "technical_statistical_volume_liquidity",
        "source_family": "ohlcv",
        "status": "materialized_preheldout",
        "question": "Are volume/liquidity features driving useful behavior?",
    },
    {
        "name": "tech_stat_full_plus_train_only_regime_probs",
        "feature_family": "technical_statistical_plus_regime",
        "source_family": "ohlcv_train_only_regime",
        "status": "materialized_preheldout",
        "question": "Do train-only regime probabilities reduce bad exposure?",
    },
    {
        "name": "tech_stat_reduced_corr_v1_plus_train_only_regime_probs",
        "feature_family": "technical_statistical_reduced_plus_regime",
        "source_family": "ohlcv_train_only_regime",
        "status": "materialized_preheldout",
        "question": "Do regime probabilities help after redundancy reduction?",
    },
    {
        "name": "tech_stat_full_plus_train_only_ood_score",
        "feature_family": "technical_statistical_plus_ood",
        "source_family": "ohlcv_train_only_ood",
        "status": "materialized_preheldout",
        "question": "Can train-only OOD state reduce overtrading/drawdown?",
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_manifest() -> dict[str, Any]:
    matrix_size = len(SEEDS) * len(COST_SCENARIOS) * len(FEATURE_VARIANTS)
    return {
        "schema_version": "project3_stage_b_pragmatic_diagnostic_manifest_v1",
        "generated_at": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "purpose": "targeted_stage_b_repair_and_feature_diagnostic",
        "project_rules": {
            "stage_c_allowed": False,
            "stage_c_access": "DENIED",
            "heldout_start": HELDOUT_START,
            "training_launch_allowed_by_this_manifest": False,
            "requires_operator_approval_before_training": True,
            "fixed_algorithms_only": ["SAC"],
            "do_not_modify_algorithms": ["PPO", "SAC", "DQN"],
        },
        "target": {
            "asset": "ETHUSDT",
            "timeframe": "4h",
            "algorithm": "SAC",
            "base_feature_family": "tech_stat",
        },
        "seeds": SEEDS,
        "cost_scenarios": COST_SCENARIOS,
        "feature_variants": FEATURE_VARIANTS,
        "matrix": {
            "feature_variant_count": len(FEATURE_VARIANTS),
            "seed_count": len(SEEDS),
            "cost_scenario_count": len(COST_SCENARIOS),
            "planned_run_cells": matrix_size,
            "paired_design_required": True,
        },
        "required_evidence_per_cell": {
            "trace_schema_version": "stage_b_return_trace_v1",
            "evidence_schema_version": "project3_return_trace_evidence_v1",
            "required_splits": ["evaluation"],
            "required_files": [
                "return_trace.csv",
                "return_trace.csv.meta.json",
                "evidence.json",
            ],
            "required_cost_scenarios": [item["name"] for item in COST_SCENARIOS],
            "required_seed_set": SEEDS,
        },
        "external_infrastructure_status": {
            "feature_variants_materialized": True,
            "feature_variant_materialization_summary": str(
                ROOT / "experiments" / "stage_b_validation" / "diagnostic_inputs"
                / "ethusdt" / "4h" / "feature_variant_materialization_summary.json"
            ),
            "agent_multi_cost_scenarios_supported": True,
            "agent_multi_known_baseline_plugins_supported": True,
            "agent_multi_stageb_run_plan_dry_validated": True,
        },
        "hard_blocks_before_training": [
            "stage_b_operator_approval_missing",
        ],
        "safety_invariants": [
            "stage_c_access_must_remain_denied",
            "training_must_not_launch_from_manifest_alone",
            "all_runs_count_as_new_trials_for_dsr_pbo",
        ],
        "promotion_policy": {
            "diagnostic_results_do_not_unlock_stage_c": True,
            "stage_c_requires_stage_b_approval_gate_pass": True,
            "counts_as_new_trials_for_dsr_pbo": True,
            "synthetic_data_allowed": False,
        },
    }


def build_cost_manifest() -> dict[str, Any]:
    return {
        "schema_version": "project3_stage_b_cost_scenario_manifest_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_allowed": False,
        "cost_scenarios": COST_SCENARIOS,
        "required_for_stage_b_promotion": [item["name"] for item in COST_SCENARIOS],
        "notes": [
            "base is the minimum realistic cost scenario",
            "plus_50pct and plus_100pct are stress scenarios, not tuning knobs",
            "all three scenarios must be paired by seed and feature variant",
        ],
    }


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    safe = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{safe}"'


def to_yaml(value: Any, indent: int = 0) -> list[str]:
    pad = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}{key}:")
                lines.extend(to_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, dict):
                lines.append(f"{pad}-")
                lines.extend(to_yaml(item, indent + 2))
            elif isinstance(item, list):
                lines.append(f"{pad}-")
                lines.extend(to_yaml(item, indent + 2))
            else:
                lines.append(f"{pad}- {yaml_scalar(item)}")
        return lines
    return [f"{pad}{yaml_scalar(value)}"]


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.write_text("\n".join(to_yaml(payload)) + "\n", encoding="utf-8")


def write_md(manifest: dict[str, Any]) -> None:
    variants = manifest["feature_variants"]
    costs = [item["name"] for item in manifest["cost_scenarios"]]
    lines = [
        "# Stage B Pragmatic Diagnostic Manifest",
        "",
        f"Experiment: `{manifest['experiment_id']}`",
        "",
        "## Lock State",
        "",
        f"- Stage C allowed: `{manifest['project_rules']['stage_c_allowed']}`",
        f"- Stage C access: `{manifest['project_rules']['stage_c_access']}`",
        f"- Training launch allowed by this manifest: `{manifest['project_rules']['training_launch_allowed_by_this_manifest']}`",
        f"- Heldout boundary: `{manifest['project_rules']['heldout_start']}`",
        "",
        "## Matrix",
        "",
        f"- Target: `ETHUSDT 4h SAC`",
        f"- Seeds: `{manifest['seeds']}`",
        f"- Cost scenarios: `{costs}`",
        f"- Feature variants: `{len(variants)}`",
        f"- Planned run cells: `{manifest['matrix']['planned_run_cells']}`",
        "",
        "| variant | status | question |",
        "| --- | --- | --- |",
    ]
    for variant in variants:
        lines.append(f"| `{variant['name']}` | `{variant['status']}` | {variant['question']} |")
    lines.extend([
        "",
        "## Hard Blocks Before Training",
        "",
    ])
    for block in manifest["hard_blocks_before_training"]:
        lines.append(f"- `{block}`")
    lines.extend([
        "",
        "This packet is diagnostic-only. It does not unlock Stage C and every",
        "resulting run cell must be counted as a new trial in downstream DSR/PBO",
        "accounting.",
        "",
    ])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def write_outputs() -> dict[str, str]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()
    cost_manifest = build_cost_manifest()
    OUT_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    OUT_COST_JSON.write_text(json.dumps(cost_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_yaml(OUT_YAML, manifest)
    write_yaml(OUT_COST_YAML, cost_manifest)
    write_md(manifest)
    return {
        "manifest_json": str(OUT_JSON),
        "manifest_yaml": str(OUT_YAML),
        "manifest_md": str(OUT_MD),
        "cost_manifest_json": str(OUT_COST_JSON),
        "cost_manifest_yaml": str(OUT_COST_YAML),
    }


def main() -> None:
    outputs = write_outputs()
    print(json.dumps({"ok": True, "outputs": outputs}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
