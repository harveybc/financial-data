#!/usr/bin/env python3
"""Generate a locked Stage B force-close reward-penalty diagnostic plan.

The force-close observation repair proved the policy can now see Friday-close
state and that behavior changes, but it still leaves too much late-Friday
exposure. This worker creates the next narrow diagnostic: same ETHUSDT 4h SAC
tech_stat_full branch, same CSV features, force-close observation enabled, and
one explicit normalized reward penalty for carrying exposure near the forced
Friday close.

No training is launched here. Stage C remains denied.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = Path("/home/harveybc/Documents/GitHub/agent-multi")
PYTHON = Path("/home/harveybc/anaconda3/envs/tensorflow/bin/python")
AGENT_MULTI_TOOL = AGENT_MULTI_ROOT / "tools" / "project3_stageb_run_plan.py"
AGENT_MULTI_TEMPLATE = (
    AGENT_MULTI_ROOT / "examples" / "config" / "project3_ethusdt_4h_sac_train_val_test_v3.json"
)

DIAGNOSTIC_INPUT_SUMMARY = (
    ROOT
    / "experiments"
    / "stage_b_validation"
    / "diagnostic_inputs"
    / "ethusdt"
    / "4h"
    / "feature_variant_materialization_summary.json"
)
OUT_ROOT = ROOT / "experiments" / "stage_b_validation" / "force_close_penalty_run_plan"
REFERENCE_DIR = OUT_ROOT / "reference_configs"
SUMMARY_JSON = OUT_ROOT / "stageb_force_close_penalty_run_plan_summary.json"
SUMMARY_MD = OUT_ROOT / "stageb_force_close_penalty_run_plan_summary.md"
PLAN_DIR = OUT_ROOT / "run_plan"
PLAN_JSON = PLAN_DIR / "stage_b_force_close_penalty_locked_run_plan.json"
PLAN_CSV = PLAN_DIR / "stage_b_force_close_penalty_locked_run_plan.csv"
PLAN_MD = PLAN_DIR / "stage_b_force_close_penalty_locked_run_plan.md"

ACTIVE_PLAN_DIR = ROOT / "experiments" / "stage_b_validation" / "run_plan"
ACTIVE_PLAN_JSON = ACTIVE_PLAN_DIR / "stage_b_locked_run_plan.json"
ACTIVE_PLAN_CSV = ACTIVE_PLAN_DIR / "stage_b_locked_run_plan.csv"
ACTIVE_PLAN_MD = ACTIVE_PLAN_DIR / "stage_b_locked_run_plan.md"

HELDOUT_START = "2025-01-01"
COST_SCENARIOS = ["base", "plus_50pct", "plus_100pct"]
BASELINES = ["no_trade", "buy_and_hold", "random", "momentum", "reversal"]
TARGET_VARIANT = "tech_stat_full"
PENALTY_COEFFICIENTS = [0.0001, 0.0003]
PENALTY_WINDOW_HOURS = 4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_worker_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def coefficient_label(value: float) -> str:
    return f"penalty_{str(value).replace('.', 'p')}"


def selected_variant() -> dict[str, Any]:
    summary = load_json(DIAGNOSTIC_INPUT_SUMMARY)
    for item in summary.get("variants") or []:
        if str(item.get("variant")) == TARGET_VARIANT:
            return item
    raise RuntimeError(f"missing diagnostic variant: {TARGET_VARIANT}")


def write_reference_configs(variant_meta: dict[str, Any]) -> list[dict[str, Any]]:
    pragmatic = load_worker_module(
        ROOT / "_scripts" / "workers" / "stage_b_pragmatic_run_plan_worker.py",
        "stage_b_pragmatic_run_plan_worker_for_force_close_penalty",
    )
    template = load_json(AGENT_MULTI_TEMPLATE)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    refs: list[dict[str, Any]] = []
    for coef in PENALTY_COEFFICIENTS:
        cfg = pragmatic.build_reference_config(template, variant_meta)
        label = coefficient_label(coef)
        variant = f"{TARGET_VARIANT}_plus_force_close_obs_{label}"
        cfg["features_preset"] = variant
        cfg["_project3_force_close_penalty_diagnostic"] = True
        cfg["_project3_force_close_penalty_source_variant"] = TARGET_VARIANT
        cfg["stage_b_force_close_obs"] = True
        cfg["stage_b_force_close_reward_penalty"] = True
        cfg["force_close_exposure_penalty_coef"] = coef
        cfg["force_close_exposure_penalty_window_hours"] = PENALTY_WINDOW_HOURS
        cfg["force_close_dow"] = 4
        cfg["force_close_hour"] = 20
        cfg["force_close_window_hours"] = 4
        cfg["monday_entry_window_hours"] = 4
        cfg["stage_c_access"] = "DENIED"
        cfg["final_stage_c_evaluation"] = False
        cfg["stage_c_acknowledged"] = False
        cfg["feature_list"] = list(cfg.get("feature_columns") or [])
        path = REFERENCE_DIR / f"{variant}.json"
        path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        refs.append(
            {
                "variant": variant,
                "source_variant": TARGET_VARIANT,
                "reference_config": str(path),
                "input_data_file": cfg["input_data_file"],
                "feature_count": len(cfg["feature_columns"]),
                "stage_b_force_close_obs": True,
                "stage_b_force_close_reward_penalty": True,
                "force_close_exposure_penalty_coef": coef,
                "force_close_exposure_penalty_window_hours": PENALTY_WINDOW_HOURS,
            }
        )
    return refs


def run_agent_multi_plan(reference: dict[str, Any]) -> dict[str, Any]:
    variant = reference["variant"]
    output_dir = OUT_ROOT / "plans" / variant
    cmd = [
        str(PYTHON),
        str(AGENT_MULTI_TOOL),
        "--reference-config",
        reference["reference_config"],
        "--candidate-id",
        f"ethusdt_4h_sac_{variant}",
        "--output-dir",
        str(output_dir),
        "--cost-scenarios",
        ",".join(COST_SCENARIOS),
        "--baselines",
        ",".join(BASELINES),
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(AGENT_MULTI_ROOT),
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = json.loads(proc.stdout)
    return {
        "variant": variant,
        "source_variant": reference["source_variant"],
        "reference_config": reference["reference_config"],
        "output_dir": str(output_dir),
        "force_close_exposure_penalty_coef": reference["force_close_exposure_penalty_coef"],
        "force_close_exposure_penalty_window_hours": reference[
            "force_close_exposure_penalty_window_hours"
        ],
        "command": cmd,
        "agent_multi_stdout": payload,
        "agent_multi_stderr": proc.stderr,
    }


def write_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_configs = sum(int(r["agent_multi_stdout"]["config_count"]) for r in results)
    payload = {
        "schema_version": "project3_stage_b_force_close_penalty_run_plan_summary_v1",
        "plan_id": "stageb_force_close_penalty_ethusdt_4h_sac_diagnostic_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "variant_count": len(results),
        "source_variants": [TARGET_VARIANT],
        "penalty_coefficients": PENALTY_COEFFICIENTS,
        "penalty_window_hours": PENALTY_WINDOW_HOURS,
        "cost_scenarios": COST_SCENARIOS,
        "baselines": BASELINES,
        "total_locked_configs": total_configs,
        "selection_rule": (
            "focused force-close reward diagnostic: ETHUSDT 4h SAC tech_stat_full "
            "with force-close observation visible plus normalized late-Friday "
            "exposure reward penalties; all cells are counted Stage B trials"
        ),
        "results": results,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Stage B Force-Close Reward-Penalty Run Plan Summary",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched: `{payload['training_launched']}`",
        f"- Variants: `{payload['variant_count']}`",
        f"- Penalty coefficients: `{payload['penalty_coefficients']}`",
        f"- Penalty window hours: `{payload['penalty_window_hours']}`",
        f"- Cost scenarios: `{payload['cost_scenarios']}`",
        f"- Baselines: `{payload['baselines']}`",
        f"- Total locked configs: `{payload['total_locked_configs']}`",
        "",
        "## Selection Rule",
        "",
        payload["selection_rule"],
        "",
        "| variant | penalty coefficient | locked configs | manifest |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in results:
        out = row["agent_multi_stdout"]
        lines.append(
            f"| `{row['variant']}` | {row['force_close_exposure_penalty_coef']} | "
            f"{out['config_count']} | `{out.get('manifest_file')}` |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def write_dispatch_plan(summary: dict[str, Any]) -> dict[str, Any]:
    dispatch = load_worker_module(
        ROOT / "_scripts" / "workers" / "stage_b_pragmatic_dispatch_plan_worker.py",
        "stage_b_pragmatic_dispatch_plan_worker_for_force_close_penalty",
    )
    dispatch.SUMMARY_JSON = SUMMARY_JSON
    dispatch.PLAN_DIR = PLAN_DIR
    dispatch.PLAN_JSON = PLAN_JSON
    dispatch.PLAN_CSV = PLAN_CSV
    dispatch.PLAN_MD = PLAN_MD
    entries = dispatch.build_entries(summary)
    payload = dispatch.write_outputs(entries, summary)
    ACTIVE_PLAN_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PLAN_JSON, ACTIVE_PLAN_JSON)
    shutil.copy2(PLAN_CSV, ACTIVE_PLAN_CSV)
    shutil.copy2(PLAN_MD, ACTIVE_PLAN_MD)
    payload["activated_plan_json"] = str(ACTIVE_PLAN_JSON)
    payload["activated_plan_md"] = str(ACTIVE_PLAN_MD)
    return payload


def main() -> int:
    variant = selected_variant()
    refs = write_reference_configs(variant)
    results = [run_agent_multi_plan(ref) for ref in refs]
    summary = write_summary(results)
    dispatch = write_dispatch_plan(summary)
    print(
        json.dumps(
            {
                "ok": True,
                "variant_count": summary["variant_count"],
                "penalty_coefficients": summary["penalty_coefficients"],
                "total_locked_configs": summary["total_locked_configs"],
                "machine_assignment_counts": dispatch["machine_assignment_counts"],
                "summary_json": str(SUMMARY_JSON),
                "summary_md": str(SUMMARY_MD),
                "plan_json": str(PLAN_JSON),
                "plan_md": str(PLAN_MD),
                "activated_plan_json": dispatch["activated_plan_json"],
                "activated_plan_md": dispatch["activated_plan_md"],
                "training_launched": False,
                "stage_c_access": "DENIED",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
