#!/usr/bin/env python3
"""Build the parametric Project 3 data/preprocessing search space.

The point of this worker is to make data contracts first-class, searchable
objects. It does not launch training. It enumerates existing train-only input
datasets, defines DEAP/NSGA-ready genes for data, feature selection, and
preprocessing, and emits a seed population for later CPU screening.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
INPUT_ROOT = ROOT / "experiments" / "stage_a_screening" / "inputs"
OUT_ROOT = ROOT / "experiments" / "stage3x_parametric_data_space"
SCHEMA_JSON = OUT_ROOT / "project3_data_preprocessing_search_space.schema.json"
POPULATION_CSV = OUT_ROOT / "project3_data_preprocessing_seed_population.csv"
SUMMARY_JSON = OUT_ROOT / "project3_data_preprocessing_search_space_summary.json"
SUMMARY_MD = OUT_ROOT / "project3_data_preprocessing_search_space_summary.md"

HELDOUT_START = "2025-01-01"
CORE_COLUMNS = {"DATE_TIME", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}

FEATURE_SELECTION_METHODS = [
    "family_allowlist",
    "corr_stability_topk",
    "rank_ic_topk",
    "mutual_info_topk",
    "regime_conditioned_topk",
    "nsga_sparse_mask",
]

# Methods that are implemented by stage3x_target_relation_screen_worker and
# cheap enough to use before the first NSGA population exists.
CPU_SCREENING_FEATURE_SELECTION_METHODS = (
    "corr_stability_topk",
    "rank_ic_topk",
    "mutual_info_topk",
    "regime_conditioned_topk",
)

PREPROCESSING_PROFILES = [
    {
        "profile_id": "p00_current_contract",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 256,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p01_no_scaling_control",
        "scaling_mode": "none",
        "feature_scaling_window": 0,
        "feature_clip": 0,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p02_rolling_short_64",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 64,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p03_rolling_long_512",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 512,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p04_expanding_zscore",
        "scaling_mode": "expanding_zscore",
        "feature_scaling_window": 0,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p05_clip_tight_5",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 256,
        "feature_clip": 5,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p06_wide_observation_64",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 256,
        "feature_clip": 10,
        "window_size": 64,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p07_rolling_mid_128",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 128,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p08_rolling_long_1024",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 1024,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p09_clip_loose_20",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 256,
        "feature_clip": 20,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p10_wide_observation_96",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 256,
        "feature_clip": 10,
        "window_size": 96,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 4,
        "monday_entry_window_hours": 4,
    },
    {
        "profile_id": "p11_tight_force_close_2h",
        "scaling_mode": "rolling_zscore",
        "feature_scaling_window": 256,
        "feature_clip": 10,
        "window_size": 32,
        "stage_b_force_close_obs": True,
        "force_close_dow": 4,
        "force_close_hour": 20,
        "force_close_window_hours": 2,
        "monday_entry_window_hours": 4,
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def csv_header(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        return next(reader)


def discover_inputs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for train_csv in sorted(INPUT_ROOT.glob("*/*/*/train.csv")):
        rel = train_csv.relative_to(INPUT_ROOT)
        if len(rel.parts) != 4:
            continue
        asset, timeframe, preset, _ = rel.parts
        metadata = load_json(train_csv.with_name("train_metadata.json"))
        header = csv_header(train_csv)
        feature_columns = [col for col in header if col not in CORE_COLUMNS]
        rows.append(
            {
                "asset": asset,
                "timeframe": timeframe,
                "feature_preset": preset,
                "input_data_file": str(train_csv),
                "metadata_file": str(train_csv.with_name("train_metadata.json")),
                "feature_count": len(feature_columns),
                "has_metadata": bool(metadata),
                "date_start": metadata.get("date_start") or metadata.get("start") or "",
                "date_end": metadata.get("date_end") or metadata.get("end") or "",
            }
        )
    return rows


def source_family(preset: str) -> str:
    if preset.startswith("learned_"):
        return "learned_representation"
    if preset in {"tech_full", "tech_stat", "tech_stat_decomp", "baseline_12"}:
        return "technical_statistical"
    if "crypto" in preset:
        return "crypto_source_family"
    if "fx" in preset:
        return "fx_source_family"
    if "kitchen" in preset:
        return "mixed_guarded"
    if "sota" in preset:
        return "curated_low_cost"
    return "other"


def build_schema(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    assets = sorted({row["asset"] for row in inputs})
    timeframes = sorted({row["timeframe"] for row in inputs})
    presets = sorted({row["feature_preset"] for row in inputs})
    return {
        "schema_version": "project3_data_preprocessing_search_space_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "optimizer": {
            "library": "deap",
            "algorithm": "NSGA-II",
            "status": "planned_after_cpu_screening",
            "primary_model": "SAC",
            "comparators": ["PPO", "DQN"],
        },
        "gene_space": {
            "asset": assets,
            "timeframe": timeframes,
            "feature_preset": presets,
            "source_family": sorted({source_family(preset) for preset in presets}),
            "feature_selection_method": FEATURE_SELECTION_METHODS,
            "feature_budget": [8, 12, 16, 24, 32, 48, 64],
            "preprocessing_profile": [row["profile_id"] for row in PREPROCESSING_PROFILES],
            "seasonal_context": ["off", "calendar_features", "force_close_obs"],
            "representation_method": ["raw_selected", "pca", "autoencoder", "contrastive_timeseries"],
            "sac_learning_rate": [3e-5, 1e-4, 3e-4],
            "sac_batch_size": [128, 256, 512],
            "sac_gamma": [0.97, 0.99, 0.995],
            "sac_tau": [0.002, 0.005, 0.01],
            "sac_ent_coef": ["auto", 0.005, 0.01, 0.03],
        },
        "hard_constraints": [
            "no_stage_c_rows",
            "feature_list_hash_required",
            "observation_state_hash_required",
            "no_no_trade_collapse",
            "no_excessive_trade_hard_flag",
            "no_always_in_market_losing_flag",
            "every_gpu_trial_counted_in_ledger",
            "cpu_target_relation_screen_before_gpu",
        ],
    }


def seed_population(inputs: list[dict[str, Any]], limit_per_family: int = 6) -> list[dict[str, Any]]:
    """Pick a small, diverse CPU-screening seed population from actual inputs."""
    by_family: dict[str, list[dict[str, Any]]] = {}
    for row in inputs:
        family = source_family(row["feature_preset"])
        by_family.setdefault(family, []).append(row)

    population: list[dict[str, Any]] = []
    for family, rows in sorted(by_family.items()):
        # Prefer 4h/1h first for trade-rate sanity, then largest feature sets.
        ordered = sorted(
            rows,
            key=lambda r: (
                0 if r["timeframe"] in {"4h", "1h"} else 1,
                -int(r["feature_count"]),
                r["asset"],
                r["feature_preset"],
            ),
        )
        for row in ordered[:limit_per_family]:
            for method in CPU_SCREENING_FEATURE_SELECTION_METHODS:
                for profile in PREPROCESSING_PROFILES:
                    profile_token = str(profile["profile_id"]).split("_", 1)[0]
                    population.append(
                        {
                            "genome_id": (
                                f"{row['asset']}__{row['timeframe']}__{row['feature_preset']}__"
                                f"{method}__{profile_token}"
                            ),
                            "asset": row["asset"],
                            "timeframe": row["timeframe"],
                            "feature_preset": row["feature_preset"],
                            "source_family": family,
                            "input_data_file": row["input_data_file"],
                            "feature_count_available": row["feature_count"],
                            "feature_selection_method": method,
                            "feature_budget": min(32, max(8, int(row["feature_count"]))),
                            "preprocessing_profile": profile["profile_id"],
                            "scaling_mode": profile["scaling_mode"],
                            "feature_scaling_window": profile["feature_scaling_window"],
                            "feature_clip": profile["feature_clip"],
                            "window_size": profile["window_size"],
                            "stage_b_force_close_obs": profile["stage_b_force_close_obs"],
                            "force_close_dow": profile["force_close_dow"],
                            "force_close_hour": profile["force_close_hour"],
                            "force_close_window_hours": profile["force_close_window_hours"],
                            "monday_entry_window_hours": profile["monday_entry_window_hours"],
                            "seasonal_context": "force_close_obs" if row["timeframe"] == "4h" else "calendar_features",
                            "representation_method": "raw_selected",
                            "requires_training": False,
                            "requires_gpu": False,
                            "stage_c_access": "DENIED",
                            "status": "CPU_SCREENING_SEED",
                        }
                    )
    return population


def write_outputs(schema: dict[str, Any], inputs: list[dict[str, Any]], population: list[dict[str, Any]]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema_version": "project3_data_preprocessing_search_space_summary_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "input_dataset_count": len(inputs),
        "asset_count": len({row["asset"] for row in inputs}),
        "timeframe_count": len({row["timeframe"] for row in inputs}),
        "feature_preset_count": len({row["feature_preset"] for row in inputs}),
        "seed_population_count": len(population),
        "schema_json": str(SCHEMA_JSON),
        "population_csv": str(POPULATION_CSV),
    }
    SCHEMA_JSON.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if population:
        with POPULATION_CSV.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(population[0].keys()))
            writer.writeheader()
            writer.writerows(population)
    lines = [
        "# Project 3 Parametric Data / Preprocessing Search Space",
        "",
        f"Generated UTC: `{summary['generated_at']}`",
        "",
        f"- Stage C access: `{summary['stage_c_access']}`",
        f"- Training launched: `{summary['training_launched']}`",
        f"- Input datasets discovered: `{summary['input_dataset_count']}`",
        f"- Assets: `{summary['asset_count']}`",
        f"- Timeframes: `{summary['timeframe_count']}`",
        f"- Feature presets: `{summary['feature_preset_count']}`",
        f"- CPU-screening seed genomes: `{summary['seed_population_count']}`",
        "",
        "## Purpose",
        "",
        (
            "This is the active search surface for Project 3. The object being "
            "searched is not just a model; it is the full data contract: asset, "
            "timeframe, source family, feature selector, preprocessing profile, "
            "seasonal context, and later SAC hyperparameters."
        ),
        "",
        "## Guardrail",
        "",
        (
            "The seed population is CPU-screening only. DEAP/NSGA-II may consume "
            "this schema after target-relation screening reduces the feature universe. "
            "No Stage C rows and no uncounted GPU trial are allowed."
        ),
    ]
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    inputs = discover_inputs()
    schema = build_schema(inputs)
    population = seed_population(inputs)
    write_outputs(schema, inputs, population)
    print(
        json.dumps(
            {
                "ok": True,
                "input_dataset_count": len(inputs),
                "seed_population_count": len(population),
                "schema_json": str(SCHEMA_JSON),
                "summary_md": str(SUMMARY_MD),
                "training_launched": False,
                "stage_c_access": "DENIED",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
