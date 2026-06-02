#!/usr/bin/env python3
"""Build the next tiny Stage 3X micro-NSGA generation.

This worker consumes the completed micro-NSGA synthesis and emits a new locked
selected-contract packet for agent-multi. It does not launch training and keeps
Stage C denied. The generated individuals are deliberately small-window probes:
they widen feature/preprocessing/SAC search without pretending the previous
short-window returns prove tradability.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = ROOT.parent / "agent-multi"
PYTHON_BIN = Path("/home/harveybc/anaconda3/envs/tensorflow/bin/python")
AGENT_MULTI_TOOL = AGENT_MULTI_ROOT / "tools" / "project3_stage3x_sac_smoke_plan.py"

DEFAULT_MICRO_SYNTHESIS = (
    ROOT
    / "experiments"
    / "stage3x_micro_nsga_results"
    / "stage3x_sac_smoke_result_synthesis.json"
)
DEFAULT_SELECTED_CONTRACTS = (
    ROOT / "experiments" / "stage3x_target_relation_screen" / "selected_feature_contracts.json"
)
DEFAULT_GENERATION = 1
DEFAULT_OUT_ROOT = ROOT / "experiments" / "stage3x_micro_nsga_g01_plan"
DEFAULT_AGENT_MULTI_OUTPUT_DIR = AGENT_MULTI_ROOT / "experiments" / "stage3x_micro_nsga_g01_plan"

SCHEMA_VERSION = "project3_stage3x_micro_nsga_nextgen_plan_v1"
SELECTED_SCHEMA_VERSION = "project3_stage3x_selected_feature_contracts_v1"

GEN1_VARIANTS: tuple[dict[str, Any], ...] = (
    {
        "name": "seed_robust_fast_actor_top75",
        "feature_fraction": 0.75,
        "learning_rate": 1e-3,
        "batch_size": 32,
        "gamma": 0.95,
        "tau": 0.02,
        "train_freq": 1,
        "gradient_steps": 16,
        "continuous_action_threshold": 0.15,
        "learning_starts": 1,
        "buffer_size": 20_000,
        "ent_coef": 0.0001,
        "use_sde": False,
        "net_arch": [32, 32],
        "epoch_timesteps": 2_000,
        "max_epochs": 8,
        "l1_patience": 7,
        "l1_min_delta": 0.0,
        "total_timesteps": 16_000,
        "train_days": 28,
        "val_days": 14,
        "test_days": 14,
    },
    {
        "name": "seed_robust_stable_mid_entropy_top50",
        "feature_fraction": 0.50,
        "learning_rate": 2e-4,
        "batch_size": 128,
        "gamma": 0.985,
        "tau": 0.01,
        "train_freq": 1,
        "gradient_steps": 4,
        "continuous_action_threshold": 0.18,
        "learning_starts": 16,
        "buffer_size": 25_000,
        "ent_coef": 0.002,
        "use_sde": False,
        "net_arch": [64, 64],
        "epoch_timesteps": 2_000,
        "max_epochs": 8,
        "l1_patience": 7,
        "l1_min_delta": 0.0,
        "total_timesteps": 16_000,
        "train_days": 28,
        "val_days": 14,
        "test_days": 14,
    },
    {
        "name": "seed_robust_smoother_full",
        "feature_fraction": 1.00,
        "learning_rate": 1e-4,
        "batch_size": 128,
        "gamma": 0.995,
        "tau": 0.005,
        "train_freq": 1,
        "gradient_steps": 4,
        "continuous_action_threshold": 0.08,
        "learning_starts": 16,
        "buffer_size": 20_000,
        "ent_coef": 0.005,
        "use_sde": False,
        "net_arch": [64, 64],
        "epoch_timesteps": 2_000,
        "max_epochs": 8,
        "l1_patience": 7,
        "l1_min_delta": 0.0,
        "total_timesteps": 16_000,
        "train_days": 28,
        "val_days": 14,
        "test_days": 14,
    },
)


class MicroNsgaNextgenError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def selected_contract_map(path: Path) -> dict[str, dict[str, Any]]:
    doc = load_json(path)
    if doc.get("stage_c_access") != "DENIED" or bool(doc.get("training_launched")):
        raise MicroNsgaNextgenError("Selected contracts must deny Stage C and avoid launching training.")
    return {
        str(row["contract_id"]): row
        for row in doc.get("contracts") or []
        if row.get("contract_id")
    }


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def parent_id(contract_id: str) -> str:
    marker = "__micro_nsga_"
    if marker in contract_id:
        return contract_id.split(marker, 1)[0]
    return contract_id


def score_summary(row: dict[str, Any]) -> float:
    """Rank tiny-window results as optimizer inputs, not promotion evidence."""
    validation_return = _to_float(row.get("median_validation_return"))
    test_return = _to_float(row.get("median_test_return"))
    test_trades = _to_float(row.get("median_test_trades"))
    test_tpw = _to_float(row.get("median_test_trades_per_week"))
    cost_ratio = _to_float(row.get("median_test_cost_to_gross_edge_ratio"), default=0.0)
    warning_penalty = 0.0025 * len(row.get("warnings") or [])
    target_trade_penalty = abs(test_tpw - 4.0) * 0.001
    no_trade_penalty = 0.05 if test_trades <= 0 else 0.0
    cost_penalty = max(0.0, cost_ratio - 0.75) * 0.01
    return (
        validation_return * 0.60
        + test_return * 0.25
        + min(test_tpw, 6.0) * 0.002
        - warning_penalty
        - target_trade_penalty
        - no_trade_penalty
        - cost_penalty
    )


def score_seed_rows(rows: list[dict[str, Any]]) -> float:
    """Prefer individuals that work across seeds, not one lucky seed."""
    if not rows:
        return float("-inf")
    validation_returns = [_to_float(row.get("validation_return")) for row in rows]
    test_returns = [_to_float(row.get("test_return")) for row in rows]
    test_tpw = [_to_float(row.get("test_trades_per_week")) for row in rows]
    test_trades = [_to_float(row.get("test_trades")) for row in rows]
    positive_both = sum(
        1
        for val_ret, test_ret in zip(validation_returns, test_returns)
        if val_ret > 0 and test_ret > 0
    )
    min_val = min(validation_returns)
    min_test = min(test_returns)
    median_val = sorted(validation_returns)[len(validation_returns) // 2]
    median_test = sorted(test_returns)[len(test_returns) // 2]
    avg_tpw = sum(test_tpw) / len(test_tpw)
    no_trade_penalty = 0.05 * sum(1 for trades in test_trades if trades <= 0)
    target_trade_penalty = abs(avg_tpw - 4.0) * 0.001
    robustness_bonus = positive_both * 0.02
    fragility_penalty = (len(rows) - positive_both) * 0.01
    return (
        min_val * 0.35
        + min_test * 0.25
        + median_val * 0.25
        + median_test * 0.15
        + robustness_bonus
        - fragility_penalty
        - no_trade_penalty
        - target_trade_penalty
    )


def ranked_parent_ids(
    synthesis: dict[str, Any],
    *,
    max_parents: int = 4,
    strip_micro_parent: bool = True,
) -> list[str]:
    if synthesis.get("stage_c_access") != "DENIED" or synthesis.get("stage_c_allowed") is not False:
        raise MicroNsgaNextgenError("Micro synthesis must deny Stage C.")
    rows_by_parent: dict[str, list[dict[str, Any]]] = {}
    for row in synthesis.get("rows") or []:
        if row.get("status") and row.get("status") != "done":
            continue
        raw_id = str(row.get("contract_id") or "")
        if not raw_id:
            continue
        pid = parent_id(raw_id) if strip_micro_parent else raw_id
        rows_by_parent.setdefault(pid, []).append(row)
    if rows_by_parent:
        ranked_rows = sorted(
            ((pid, score_seed_rows(rows)) for pid, rows in rows_by_parent.items()),
            key=lambda item: item[1],
            reverse=True,
        )
        return [pid for pid, _ in ranked_rows[:max_parents]]

    scored: dict[str, float] = {}
    for row in synthesis.get("contract_summary") or []:
        if row.get("blockers"):
            continue
        raw_id = str(row.get("contract_id") or "")
        pid = parent_id(raw_id) if strip_micro_parent else raw_id
        scored[pid] = max(scored.get(pid, float("-inf")), score_summary(row))
    return [pid for pid, _ in sorted(scored.items(), key=lambda item: item[1], reverse=True)[:max_parents]]


def add_untried_neighbor_parent_ids(
    parents: list[str],
    selected_by_id: dict[str, dict[str, Any]],
    *,
    max_total: int = 4,
) -> list[str]:
    """Add the next adjacent preprocessing parent, e.g. p06 after p03-p05."""
    out = list(parents)
    pattern = re.compile(r"__p(\d+)__selected$")
    keyed: list[tuple[int, str]] = []
    for cid in selected_by_id:
        if not cid.startswith("btcusdt_perp__4h__sota_low_cost__mutual_info_topk__p"):
            continue
        match = pattern.search(cid)
        if match:
            keyed.append((int(match.group(1)), cid))
    parent_numbers = [
        int(match.group(1))
        for cid in parents
        if (match := pattern.search(cid))
    ]
    start_after = max(parent_numbers) if parent_numbers else -1
    ordered = [cid for _, cid in sorted((n, cid) for n, cid in keyed if n > start_after)]
    ordered.extend(cid for _, cid in sorted(keyed) if cid not in ordered)
    for cid in ordered:
        if cid not in out:
            out.append(cid)
        if len(out) >= max_total:
            break
    return out[:max_total]


def feature_slice(features: list[str], fraction: float, *, variant_index: int) -> list[str]:
    if not features:
        return []
    n = max(4, int(round(len(features) * fraction)))
    n = min(len(features), n)
    if variant_index == 1:
        return features[-n:]
    if variant_index == 2 and len(features) > n:
        step = max(1, len(features) // n)
        picked = features[::step][:n]
        return picked if len(picked) >= 4 else features[:n]
    return features[:n]


def build_contracts(
    parents: list[str],
    selected_by_id: dict[str, dict[str, Any]],
    *,
    generation: int,
) -> list[dict[str, Any]]:
    contracts: list[dict[str, Any]] = []
    for parent_index, pid in enumerate(parents):
        base = selected_by_id.get(pid)
        if not base:
            continue
        features = [str(f) for f in base.get("selected_features") or []]
        for variant_index, variant in enumerate(GEN1_VARIANTS):
            individual_id = f"g{generation:02d}_i{parent_index:02d}_{variant_index:02d}"
            selected = feature_slice(
                features,
                float(variant["feature_fraction"]),
                variant_index=variant_index,
            )
            contract = dict(base)
            contract.update(
                {
                    "contract_id": f"{pid}__micro_nsga_{individual_id}",
                    "parent_contract_id": pid,
                    "micro_nsga_generation": generation,
                    "micro_nsga_individual_id": individual_id,
                    "micro_nsga_variant": variant["name"],
                    "selected_features": selected,
                    "selected_feature_count": len(selected),
                    "feature_list": selected,
                    "feature_columns": selected,
                    "learning_rate": variant["learning_rate"],
                    "batch_size": variant["batch_size"],
                    "gamma": variant["gamma"],
                    "tau": variant["tau"],
                    "train_freq": variant["train_freq"],
                    "gradient_steps": variant["gradient_steps"],
                    "continuous_action_threshold": variant["continuous_action_threshold"],
                    "learning_starts": variant["learning_starts"],
                    "buffer_size": variant["buffer_size"],
                    "ent_coef": variant["ent_coef"],
                    "use_sde": variant["use_sde"],
                    "net_arch": variant["net_arch"],
                    "epoch_timesteps": variant["epoch_timesteps"],
                    "max_epochs": variant["max_epochs"],
                    "l1_patience": variant["l1_patience"],
                    "l1_min_delta": variant["l1_min_delta"],
                    "split_anchor": "end",
                    "train_days": variant["train_days"],
                    "val_days": variant["val_days"],
                    "test_days": variant["test_days"],
                    "min_split_rows": 30,
                    "window_size": "16",
                    "total_timesteps": int(variant["total_timesteps"]),
                    "stage_c_access": "DENIED",
                    "training_launched": False,
                    "screen_score": float(base.get("screen_score") or 0.0) - (variant_index * 1e-6),
                    "nextgen_source": f"stage3x_micro_nsga_g{generation:02d}_from_completed_g{generation - 1:02d}",
                }
            )
            contracts.append(contract)
    return contracts


def build_command(*, selected_file: Path, output_dir: Path, top_n: int, validate_only: bool) -> list[str]:
    cmd = [
        str(PYTHON_BIN),
        str(AGENT_MULTI_TOOL),
        "--selected-contracts",
        str(selected_file),
        "--output-dir",
        str(output_dir),
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


def build_payload(
    *,
    synthesis_file: Path,
    selected_contracts: Path,
    out_root: Path,
    agent_multi_output_dir: Path,
    generation: int = DEFAULT_GENERATION,
    max_parents: int = 4,
) -> dict[str, Any]:
    if generation < 1:
        raise MicroNsgaNextgenError("--generation must be >= 1")
    synthesis = load_json(synthesis_file)
    selected_by_id = selected_contract_map(selected_contracts)
    parents = ranked_parent_ids(
        synthesis,
        max_parents=max_parents if generation > 1 else min(3, max_parents),
        strip_micro_parent=(generation == 1),
    )
    if generation == 1:
        parents = add_untried_neighbor_parent_ids(parents, selected_by_id, max_total=max_parents)
    contracts = build_contracts(parents, selected_by_id, generation=generation)
    blockers: list[str] = []
    if not parents:
        blockers.append("NO_RANKED_MICRO_NSGA_PARENT")
    if not contracts:
        blockers.append("NO_NEXTGEN_MICRO_NSGA_CONTRACTS")
    generation_label = f"g{generation:02d}"
    previous_label = f"g{generation - 1:02d}"
    selected_file = out_root / f"selected_feature_contracts_micro_nsga_{generation_label}.json"
    generated_at = utc_now()
    selected_population = {
        "schema_version": SELECTED_SCHEMA_VERSION,
        "generated_at": generated_at,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "selection_policy": f"stage3x_micro_nsga_nextgen_{generation_label}_v1",
        "source_synthesis_file": str(synthesis_file),
        "source_selected_contracts_file": str(selected_contracts),
        "contracts": contracts,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "micro_nsga_plan_allowed": not blockers,
        "micro_nsga_generation": generation,
        "source_micro_nsga_generation": generation - 1,
        "next_action": f"write_locked_stage3x_micro_nsga_{generation_label}_configs" if not blockers else f"repair_micro_nsga_{generation_label}_inputs",
        "blockers": blockers,
        "parent_contract_ids": parents,
        "micro_nsga_contract_count": len(contracts),
        "variants_per_parent": len(GEN1_VARIANTS),
        "seeds_per_individual": 3,
        "expected_config_count": len(contracts) * 3,
        "selected_population_file": str(selected_file),
        "agent_multi_output_dir": str(agent_multi_output_dir),
        "commands": {
            "validate_only": build_command(
                selected_file=selected_file,
                output_dir=agent_multi_output_dir,
                top_n=len(contracts),
                validate_only=True,
            ),
            "write_locked_plan": build_command(
                selected_file=selected_file,
                output_dir=agent_multi_output_dir,
                top_n=len(contracts),
                validate_only=False,
            ),
        },
        "selected_population": selected_population,
    }


def render_md(payload: dict[str, Any]) -> str:
    generation = int(payload.get("micro_nsga_generation") or 1)
    lines = [
        f"# Stage 3X Micro-NSGA Generation {generation} Plan",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched by this worker: `{payload['training_launched']}`",
        f"- Micro-NSGA plan allowed: `{payload['micro_nsga_plan_allowed']}`",
        f"- Parent contracts: `{len(payload['parent_contract_ids'])}`",
        f"- Micro individuals: `{payload['micro_nsga_contract_count']}`",
        f"- Expected locked configs: `{payload['expected_config_count']}`",
        f"- Next action: `{payload['next_action']}`",
        "",
        "## Parent Contracts",
        "",
    ]
    for cid in payload["parent_contract_ids"]:
        lines.append(f"- `{cid}`")
    lines.extend(["", "## Mutations", ""])
    for variant in GEN1_VARIANTS:
        lines.append(
            f"- `{variant['name']}`: feature_fraction={variant['feature_fraction']}, "
            f"lr={variant['learning_rate']}, threshold={variant['continuous_action_threshold']}, "
            f"gamma={variant['gamma']}, batch={variant['batch_size']}"
        )
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


def write_payload(payload: dict[str, Any], out_root: Path) -> None:
    out_root.mkdir(parents=True, exist_ok=True)
    selected = payload["selected_population"]
    Path(payload["selected_population_file"]).write_text(canonical_json(selected), encoding="utf-8")
    public = {k: v for k, v in payload.items() if k != "selected_population"}
    generation = int(public.get("micro_nsga_generation") or 1)
    generation_label = f"g{generation:02d}"
    (out_root / f"stage3x_micro_nsga_{generation_label}_plan.json").write_text(canonical_json(public), encoding="utf-8")
    (out_root / f"stage3x_micro_nsga_{generation_label}_plan.md").write_text(render_md(public), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthesis-file", type=Path, default=DEFAULT_MICRO_SYNTHESIS)
    parser.add_argument("--selected-contracts", type=Path, default=DEFAULT_SELECTED_CONTRACTS)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT_ROOT)
    parser.add_argument("--agent-multi-output-dir", type=Path, default=DEFAULT_AGENT_MULTI_OUTPUT_DIR)
    parser.add_argument("--generation", type=int, default=DEFAULT_GENERATION)
    parser.add_argument("--max-parents", type=int, default=4)
    args = parser.parse_args(argv)
    payload = build_payload(
        synthesis_file=args.synthesis_file,
        selected_contracts=args.selected_contracts,
        out_root=args.out_root,
        agent_multi_output_dir=args.agent_multi_output_dir,
        generation=args.generation,
        max_parents=args.max_parents,
    )
    write_payload(payload, args.out_root)
    print(
        json.dumps(
            {
                "micro_nsga_plan_allowed": payload["micro_nsga_plan_allowed"],
                "parent_contracts": len(payload["parent_contract_ids"]),
                "micro_nsga_contract_count": payload["micro_nsga_contract_count"],
                "expected_config_count": payload["expected_config_count"],
                "next_action": payload["next_action"],
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
