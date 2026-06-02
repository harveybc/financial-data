#!/usr/bin/env python3
"""Create the Stage 3X input/preprocessing optimization plan.

This worker is intentionally CPU-first. It does not launch training. Its job is
to stop the project from guessing about feature sets, scaling windows,
observation windows, clipping, and representation candidates before another
Stage B GPU batch is scheduled.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HELDOUT_START = "2025-01-01"

DIAGNOSTIC_INPUT_SUMMARY = (
    ROOT
    / "experiments"
    / "stage_b_validation"
    / "diagnostic_inputs"
    / "ethusdt"
    / "4h"
    / "feature_variant_materialization_summary.json"
)
REDUNDANCY_ARTIFACT_DIR = (
    ROOT
    / "experiments"
    / "unsup_causal_audit"
    / "artifacts"
    / "feature_redundancy_stability"
    / "ethusdt_4h_tech_stat"
)

OUT_ROOT = ROOT / "experiments" / "stage3x_input_preprocessing_optimization"
SUMMARY_JSON = OUT_ROOT / "stage3x_input_preprocessing_optimization_plan.json"
SUMMARY_MD = OUT_ROOT / "stage3x_input_preprocessing_optimization_plan.md"
MATRIX_CSV = OUT_ROOT / "stage3x_input_preprocessing_matrix.csv"

TARGET_VARIANTS = [
    "tech_stat_full",
    "tech_stat_reduced_corr_v1",
    "tech_stat_trend_only",
    "tech_stat_momentum_only",
    "tech_stat_volatility_only",
    "tech_stat_volume_liquidity_only",
    "tech_stat_full_plus_train_only_regime_probs",
    "tech_stat_full_plus_train_only_ood_score",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_variant_index() -> dict[str, dict[str, Any]]:
    payload = load_json_if_exists(DIAGNOSTIC_INPUT_SUMMARY)
    return {
        str(row.get("variant")): row
        for row in payload.get("variants", [])
        if row.get("variant")
    }


def build_preprocess_profiles() -> list[dict[str, Any]]:
    return [
        {
            "profile_id": "p00_current_contract",
            "scaling_mode": "rolling_zscore",
            "feature_scaling_window": 256,
            "feature_clip": 10,
            "window_size": 32,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "current comparable baseline; required as control",
        },
        {
            "profile_id": "p01_no_scaling_control",
            "scaling_mode": "none",
            "feature_scaling_window": 0,
            "feature_clip": 0,
            "window_size": 32,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "tests whether scaling itself is destroying usable magnitude information",
        },
        {
            "profile_id": "p02_rolling_short_64",
            "scaling_mode": "rolling_zscore",
            "feature_scaling_window": 64,
            "feature_clip": 10,
            "window_size": 32,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "more reactive normalization for regime shifts",
        },
        {
            "profile_id": "p03_rolling_long_512",
            "scaling_mode": "rolling_zscore",
            "feature_scaling_window": 512,
            "feature_clip": 10,
            "window_size": 32,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "slower normalization; checks over-reactive rolling stats",
        },
        {
            "profile_id": "p04_expanding_zscore",
            "scaling_mode": "expanding_zscore",
            "feature_scaling_window": 0,
            "feature_clip": 10,
            "window_size": 32,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "stable train-only normalization without rolling-window discontinuity",
        },
        {
            "profile_id": "p05_clip_tight_5",
            "scaling_mode": "rolling_zscore",
            "feature_scaling_window": 256,
            "feature_clip": 5,
            "window_size": 32,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "checks whether extreme normalized values dominate policy behavior",
        },
        {
            "profile_id": "p06_wide_observation_64",
            "scaling_mode": "rolling_zscore",
            "feature_scaling_window": 256,
            "feature_clip": 10,
            "window_size": 64,
            "include_price_window": True,
            "include_agent_state": True,
            "rationale": "tests whether the policy needs a longer visible state history",
        },
    ]


def selected_variants(variant_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name in TARGET_VARIANTS:
        meta = variant_index.get(name, {})
        rows.append(
            {
                "variant": name,
                "available": bool(meta),
                "input_data_file": str(meta.get("output_csv", "")),
                "feature_count": int(len(meta.get("feature_columns") or [])),
                "feature_columns": list(meta.get("feature_columns") or []),
            }
        )
    return rows


def build_matrix(
    variants: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for variant in variants:
        for profile in profiles:
            rows.append(
                {
                    "cell_id": f"{variant['variant']}__{profile['profile_id']}",
                    "stage": "stage3x_pre_rl_input_screen",
                    "asset": "ethusdt",
                    "timeframe": "4h",
                    "algo_scope": "fixed_ppo_sac_dqn_no_algorithm_change",
                    "source_variant": variant["variant"],
                    "variant_available": variant["available"],
                    "input_data_file": variant["input_data_file"],
                    "feature_count": variant["feature_count"],
                    "preprocess_profile": profile["profile_id"],
                    "scaling_mode": profile["scaling_mode"],
                    "feature_scaling_window": profile["feature_scaling_window"],
                    "feature_clip": profile["feature_clip"],
                    "window_size": profile["window_size"],
                    "include_price_window": profile["include_price_window"],
                    "include_agent_state": profile["include_agent_state"],
                    "requires_training": False,
                    "requires_gpu": False,
                    "stage_c_access": "DENIED",
                    "heldout_start": HELDOUT_START,
                    "status": "PLANNED_CPU_DIAGNOSTIC",
                    "next_worker": "stage3x_pre_rl_feature_target_screen_worker",
                    "pass_to_gpu_only_if": (
                        "feature_hash_present AND observation_hash_present AND "
                        "nondegenerate_feature_screen AND no_stage_c_rows"
                    ),
                    "rationale": profile["rationale"],
                }
            )
    return rows


def diagnostic_tasks() -> list[dict[str, Any]]:
    return [
        {
            "task_id": "D1_feature_contract",
            "owner": "codex",
            "artifact": "feature_list_hash + observation_state_hash in evidence",
            "hard_gate": True,
            "success_rule": "all new evidence has non-null feature_list_hash and observation_state_hash",
        },
        {
            "task_id": "D2_redundancy_stability",
            "owner": "codex",
            "artifact": str(REDUNDANCY_ARTIFACT_DIR),
            "hard_gate": True,
            "success_rule": "near-constant and highly redundant features are explicitly tagged",
        },
        {
            "task_id": "D3_target_relation_screen",
            "owner": "claude_or_codex",
            "artifact": "train/validation-only MI, rank IC, and regime-conditioned utility report",
            "hard_gate": True,
            "success_rule": "candidate feature groups show nonzero train-to-validation stable relation to future returns",
        },
        {
            "task_id": "D4_preprocessing_ablation",
            "owner": "claude_or_codex",
            "artifact": str(MATRIX_CSV),
            "hard_gate": True,
            "success_rule": "scaling/window/clip choices selected from train/validation diagnostics, not preference",
        },
        {
            "task_id": "D5_representation_research",
            "owner": "chatgpt55_pro",
            "artifact": "research memo for PCA/AE/VAE/contrastive/CNN/LSTM/Transformer encoders",
            "hard_gate": False,
            "success_rule": "only train-row pretraining proposals become counted trials",
        },
    ]


def write_outputs(payload: dict[str, Any]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    rows = payload["matrix"]
    if rows:
        with MATRIX_CSV.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    lines = [
        "# Stage 3X Input / Preprocessing / Representation Optimization Plan",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        "## Decision",
        "",
        (
            "Do not spend another broad GPU batch on the same feature/preprocessing "
            "contract. The next step is a CPU-first selection protocol that proves "
            "which inputs and preprocessing settings deserve counted RL trials."
        ),
        "",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched: `{payload['training_launched']}`",
        f"- Planned diagnostic cells: `{payload['matrix_count']}`",
        f"- Selected feature variants: `{payload['variant_count']}`",
        f"- Preprocessing profiles: `{payload['profile_count']}`",
        "",
        "## Hard Gates Before More GPU",
        "",
    ]
    for task in payload["diagnostic_tasks"]:
        gate = "hard" if task["hard_gate"] else "research"
        lines.append(f"- `{task['task_id']}` ({gate}): {task['success_rule']}")
    lines.extend(
        [
            "",
            "## Matrix",
            "",
            "| cell_id | source_variant | profile | scaling | window | clip | obs_window |",
            "| --- | --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in rows:
        lines.append(
            f"| `{row['cell_id']}` | `{row['source_variant']}` | "
            f"`{row['preprocess_profile']}` | `{row['scaling_mode']}` | "
            f"{row['feature_scaling_window']} | {row['feature_clip']} | {row['window_size']} |"
        )
    lines.extend(
        [
            "",
            "## Non-Negotiables",
            "",
            "- Stage C remains locked; no 2025-01-01+ rows are used for selection.",
            "- PPO/SAC/DQN algorithms remain fixed; this plan selects inputs and preprocessing.",
            "- Any future RL smoke or Stage B run is a counted trial in the ledger.",
            "- CryptoQuant stays cancelled unless a free/paid-source coverage audit proves it is uniquely needed.",
        ]
    )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_payload() -> dict[str, Any]:
    variant_index = load_variant_index()
    variants = selected_variants(variant_index)
    profiles = build_preprocess_profiles()
    matrix = build_matrix(variants, profiles)
    return {
        "schema_version": "project3_stage3x_input_preprocessing_optimization_plan_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "variant_count": len(variants),
        "available_variant_count": sum(1 for row in variants if row["available"]),
        "profile_count": len(profiles),
        "matrix_count": len(matrix),
        "source_summary": str(DIAGNOSTIC_INPUT_SUMMARY),
        "redundancy_artifact_dir": str(REDUNDANCY_ARTIFACT_DIR),
        "variants": variants,
        "preprocess_profiles": profiles,
        "diagnostic_tasks": diagnostic_tasks(),
        "matrix": matrix,
    }


def main() -> None:
    payload = build_payload()
    write_outputs(payload)
    print(
        json.dumps(
            {
                "ok": True,
                "summary_json": str(SUMMARY_JSON),
                "summary_md": str(SUMMARY_MD),
                "matrix_csv": str(MATRIX_CSV),
                "matrix_count": payload["matrix_count"],
                "training_launched": False,
                "stage_c_access": "DENIED",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
