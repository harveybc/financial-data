#!/usr/bin/env python3
"""Prepare the Project 3 Stage 3X micro-NSGA seed plan.

This worker does not launch training. It converts contracts that already carry
the existing ``eligible_for_stage3x_micro_nsga`` smoke-synthesis action into a
small, countable seed population for the next optimizer run.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = ROOT.parent / "agent-multi"
SYNTHESIS = ROOT / "experiments" / "stage3x_sac_smoke_results" / "stage3x_sac_smoke_result_synthesis.json"
SELECTED_CONTRACTS = ROOT / "experiments" / "stage3x_target_relation_screen" / "selected_feature_contracts.json"
OUT_ROOT = ROOT / "experiments" / "stage3x_micro_nsga_plan"
OUT_JSON = OUT_ROOT / "stage3x_micro_nsga_plan.json"
OUT_MD = OUT_ROOT / "stage3x_micro_nsga_plan.md"
OUT_SELECTED = OUT_ROOT / "selected_feature_contracts_micro_nsga_seed_population.json"

AGENT_MULTI_TOOL = AGENT_MULTI_ROOT / "tools" / "project3_stage3x_sac_smoke_plan.py"
AGENT_MULTI_OUTPUT_DIR = AGENT_MULTI_ROOT / "experiments" / "stage3x_micro_nsga_plan"
PYTHON_BIN = Path("/home/harveybc/anaconda3/envs/tensorflow/bin/python")

SCHEMA_VERSION = "project3_stage3x_micro_nsga_plan_v1"
SELECTED_SCHEMA_VERSION = "project3_stage3x_selected_feature_contracts_v1"
HELDOUT_START = "2025-01-01"

SAC_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "name": "canonical_full",
        "feature_fraction": 1.00,
        "learning_rate": 1e-4,
        "batch_size": 256,
        "gamma": 0.99,
        "tau": 0.005,
        "train_freq": 1,
        "gradient_steps": 1,
        "continuous_action_threshold": 0.10,
        "total_timesteps": 5_000,
    },
    {
        "name": "faster_actor_full",
        "feature_fraction": 1.00,
        "learning_rate": 3e-4,
        "batch_size": 256,
        "gamma": 0.99,
        "tau": 0.005,
        "train_freq": 1,
        "gradient_steps": 1,
        "continuous_action_threshold": 0.10,
        "total_timesteps": 5_000,
    },
    {
        "name": "robust_top75",
        "feature_fraction": 0.75,
        "learning_rate": 1e-4,
        "batch_size": 384,
        "gamma": 0.985,
        "tau": 0.005,
        "train_freq": 2,
        "gradient_steps": 1,
        "continuous_action_threshold": 0.15,
        "total_timesteps": 5_000,
    },
    {
        "name": "sparse_top50",
        "feature_fraction": 0.50,
        "learning_rate": 2e-4,
        "batch_size": 256,
        "gamma": 0.98,
        "tau": 0.01,
        "train_freq": 2,
        "gradient_steps": 2,
        "continuous_action_threshold": 0.20,
        "total_timesteps": 5_000,
    },
)


class MicroNsgaPlanError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def eligible_contract_ids(synthesis: dict[str, Any]) -> list[str]:
    if synthesis.get("stage_c_access") != "DENIED" or synthesis.get("stage_c_allowed") is not False:
        raise MicroNsgaPlanError("Synthesis must deny Stage C before micro-NSGA planning.")
    if synthesis.get("next_action") != "prepare_stage3x_micro_nsga_plan":
        return []
    ids: list[str] = []
    for row in synthesis.get("contract_summary") or []:
        if row.get("recommended_action") != "eligible_for_stage3x_micro_nsga":
            continue
        if row.get("blockers"):
            continue
        cid = str(row.get("contract_id") or "")
        if cid:
            ids.append(cid)
    return ids


def selected_contract_map(selected_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if selected_doc.get("stage_c_access") != "DENIED" or bool(selected_doc.get("training_launched")):
        raise MicroNsgaPlanError("Selected contracts must deny Stage C and report training_launched=false.")
    return {
        str(row.get("contract_id")): row
        for row in selected_doc.get("contracts") or []
        if row.get("contract_id")
    }


def _feature_slice(features: list[str], fraction: float) -> list[str]:
    if not features:
        return []
    n = max(4, int(round(len(features) * fraction)))
    return features[: min(len(features), n)]


def micro_contracts(
    *,
    eligible_ids: list[str],
    selected_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parent_idx, cid in enumerate(eligible_ids):
        base = selected_by_id.get(cid)
        if base is None:
            continue
        features = [str(f) for f in base.get("selected_features") or []]
        for variant_idx, variant in enumerate(SAC_VARIANTS):
            contract = dict(base)
            selected_features = _feature_slice(features, float(variant["feature_fraction"]))
            individual_id = f"g00_i{parent_idx:02d}_{variant_idx:02d}"
            contract.update(
                {
                    "contract_id": f"{cid}__micro_nsga_{individual_id}",
                    "parent_contract_id": cid,
                    "micro_nsga_generation": 0,
                    "micro_nsga_individual_id": individual_id,
                    "micro_nsga_variant": variant["name"],
                    "selected_features": selected_features,
                    "selected_feature_count": len(selected_features),
                    "feature_list": selected_features,
                    "feature_columns": selected_features,
                    "learning_rate": variant["learning_rate"],
                    "batch_size": variant["batch_size"],
                    "gamma": variant["gamma"],
                    "tau": variant["tau"],
                    "train_freq": variant["train_freq"],
                    "gradient_steps": variant["gradient_steps"],
                    "continuous_action_threshold": variant["continuous_action_threshold"],
                    "split_anchor": "end",
                    "train_days": 14,
                    "val_days": 7,
                    "test_days": 7,
                    "min_split_rows": 30,
                    "total_timesteps": int(variant["total_timesteps"]),
                    "stage_c_access": "DENIED",
                    "training_launched": False,
                    "screen_score": float(base.get("screen_score") or 0.0) - (variant_idx * 1e-6),
                }
            )
            rows.append(contract)
    return rows


def build_command(*, validate_only: bool, top_n: int) -> list[str]:
    cmd = [
        str(PYTHON_BIN),
        str(AGENT_MULTI_TOOL),
        "--selected-contracts",
        str(OUT_SELECTED),
        "--output-dir",
        str(AGENT_MULTI_OUTPUT_DIR),
        "--top-n",
        str(top_n),
        "--seeds",
        "0,1,2",
        "--cost-scenario",
        "base",
    ]
    if validate_only:
        cmd.append("--validate-only")
    return cmd


def build_plan() -> dict[str, Any]:
    synthesis = load_json(SYNTHESIS)
    selected_doc = load_json(SELECTED_CONTRACTS)
    ids = eligible_contract_ids(synthesis)
    selected_by_id = selected_contract_map(selected_doc)
    missing = [cid for cid in ids if cid not in selected_by_id]
    contracts = micro_contracts(eligible_ids=ids, selected_by_id=selected_by_id)
    blockers: list[str] = []
    if not ids:
        blockers.append("NO_ELIGIBLE_STAGE3X_MICRO_NSGA_CONTRACTS")
    if missing:
        blockers.append("ELIGIBLE_CONTRACT_MISSING_FROM_SELECTED_SOURCE")
    if not contracts:
        blockers.append("NO_STAGE3X_MICRO_NSGA_SEED_POPULATION")
    allowed = not blockers
    generated_at = utc_now()
    selected_population = {
        "schema_version": SELECTED_SCHEMA_VERSION,
        "generated_at": generated_at,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "selection_policy": "stage3x_micro_nsga_seed_population_v1",
        "source_synthesis_file": str(SYNTHESIS),
        "source_selected_contracts_file": str(SELECTED_CONTRACTS),
        "contracts": contracts,
    }
    top_n = len(contracts)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "micro_nsga_plan_allowed": allowed,
        "next_action": "write_locked_stage3x_micro_nsga_configs" if allowed else "repair_micro_nsga_plan_inputs",
        "blockers": blockers,
        "eligible_parent_contract_ids": ids,
        "missing_parent_contract_ids": missing,
        "micro_nsga_contract_count": len(contracts),
        "variants_per_parent": len(SAC_VARIANTS),
        "seeds_per_individual": 3,
        "expected_config_count": len(contracts) * 3,
        "selected_population_file": str(OUT_SELECTED),
        "agent_multi_output_dir": str(AGENT_MULTI_OUTPUT_DIR),
        "commands": {
            "validate_only": build_command(validate_only=True, top_n=top_n),
            "write_locked_plan": build_command(validate_only=False, top_n=top_n),
        },
        "selected_population": selected_population,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X Micro-NSGA Plan",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched by this worker: `{payload['training_launched']}`",
        f"- Micro-NSGA plan allowed: `{payload['micro_nsga_plan_allowed']}`",
        f"- Next action: `{payload['next_action']}`",
        f"- Parent contracts: `{len(payload['eligible_parent_contract_ids'])}`",
        f"- Micro individuals: `{payload['micro_nsga_contract_count']}`",
        f"- Expected locked configs: `{payload['expected_config_count']}`",
        "",
        "## Eligible Parent Contracts",
        "",
    ]
    for cid in payload["eligible_parent_contract_ids"]:
        lines.append(f"- `{cid}`")
    lines.extend(["", "## Commands", "", "Validate only:", "", "```bash"])
    lines.append(" ".join(payload["commands"]["validate_only"]))
    lines.extend(["```", "", "Write locked plan files, still no training:", "", "```bash"])
    lines.append(" ".join(payload["commands"]["write_locked_plan"]))
    lines.append("```")
    if payload["blockers"]:
        lines.extend(["", "## Blockers", ""])
        for blocker in payload["blockers"]:
            lines.append(f"- `{blocker}`")
    return "\n".join(lines) + "\n"


def write_plan(payload: dict[str, Any]) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    selected_population = payload["selected_population"]
    OUT_SELECTED.write_text(canonical_json(selected_population), encoding="utf-8")
    public_payload = {k: v for k, v in payload.items() if k != "selected_population"}
    OUT_JSON.write_text(canonical_json(public_payload), encoding="utf-8")
    OUT_MD.write_text(render_md(public_payload), encoding="utf-8")


def main() -> int:
    payload = build_plan()
    write_plan(payload)
    public = {k: v for k, v in payload.items() if k != "selected_population"}
    print(
        json.dumps(
            {
                "micro_nsga_plan_allowed": public["micro_nsga_plan_allowed"],
                "parent_contracts": len(public["eligible_parent_contract_ids"]),
                "micro_nsga_contract_count": public["micro_nsga_contract_count"],
                "expected_config_count": public["expected_config_count"],
                "next_action": public["next_action"],
                "stage_c_access": "DENIED",
                "training_launched": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
