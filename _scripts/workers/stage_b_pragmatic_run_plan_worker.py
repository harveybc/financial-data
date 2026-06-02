#!/usr/bin/env python3
"""Generate locked agent-multi run plans for the pragmatic Stage B matrix.

This is a planning/dispatch-prep worker only. It creates reference configs for
the 10 materialized ETHUSDT 4h SAC diagnostic feature variants and asks
agent-multi's Stage B run-plan tool to expand each one into locked configs.
No training is launched and Stage C remains denied.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = Path("/home/harveybc/Documents/GitHub/agent-multi")
PYTHON = Path("/home/harveybc/anaconda3/envs/tensorflow/bin/python")
AGENT_MULTI_TOOL = AGENT_MULTI_ROOT / "tools" / "project3_stageb_run_plan.py"
AGENT_MULTI_TEMPLATE = AGENT_MULTI_ROOT / "examples" / "config" / "project3_ethusdt_4h_sac_train_val_test_v3.json"

DIAGNOSTIC_INPUT_SUMMARY = (
    ROOT / "experiments" / "stage_b_validation" / "diagnostic_inputs" / "ethusdt" / "4h"
    / "feature_variant_materialization_summary.json"
)
OUT_ROOT = ROOT / "experiments" / "stage_b_validation" / "pragmatic_run_plan"
REFERENCE_DIR = OUT_ROOT / "reference_configs"
SUMMARY_JSON = OUT_ROOT / "stageb_pragmatic_run_plan_summary.json"
SUMMARY_MD = OUT_ROOT / "stageb_pragmatic_run_plan_summary.md"

HELDOUT_START = "2025-01-01"
COST_SCENARIOS = ["base", "plus_50pct", "plus_100pct"]
BASELINES = ["no_trade", "buy_and_hold", "random", "momentum", "reversal"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def binary_feature_subset(features: list[str]) -> list[str]:
    prefixes = (
        "ema_cross_",
        "vol_regime_",
        "train_only_regime_prob_",
    )
    return [name for name in features if name.startswith(prefixes)]


def build_reference_config(template: dict[str, Any], variant_meta: dict[str, Any]) -> dict[str, Any]:
    features = list(variant_meta.get("feature_columns") or [])
    if not features:
        raise ValueError(f"variant has no feature columns: {variant_meta.get('variant')}")
    cfg = dict(template)
    variant = str(variant_meta["variant"])
    cfg["input_data_file"] = str(variant_meta["output_csv"])
    cfg["features_preset"] = variant
    cfg["feature_columns"] = features
    cfg["feature_binary_columns"] = binary_feature_subset(features)
    cfg["asset"] = "ethusdt_4h"
    cfg["stage_c_access"] = "DENIED"
    cfg["final_stage_c_evaluation"] = False
    cfg["stage_c_acknowledged"] = False
    cfg["_project3_pragmatic_diagnostic_variant"] = variant
    cfg["_project3_pragmatic_source_metadata"] = str(
        Path(str(variant_meta["output_csv"])).with_name("train_metadata.json")
    )
    return cfg


def write_reference_configs() -> list[dict[str, Any]]:
    template = load_json(AGENT_MULTI_TEMPLATE)
    summary = load_json(DIAGNOSTIC_INPUT_SUMMARY)
    variants = summary.get("variants") or []
    if len(variants) != 10:
        raise ValueError(f"expected 10 variants, found {len(variants)}")
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    refs = []
    for variant in variants:
        cfg = build_reference_config(template, variant)
        name = str(variant["variant"])
        path = REFERENCE_DIR / f"{name}.json"
        path.write_text(json.dumps(cfg, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        refs.append({
            "variant": name,
            "reference_config": str(path),
            "input_data_file": cfg["input_data_file"],
            "feature_count": len(cfg["feature_columns"]),
        })
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
        "reference_config": reference["reference_config"],
        "output_dir": str(output_dir),
        "command": cmd,
        "agent_multi_stdout": payload,
        "agent_multi_stderr": proc.stderr,
    }


def write_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_configs = sum(int(r["agent_multi_stdout"]["config_count"]) for r in results)
    payload = {
        "schema_version": "project3_stage_b_pragmatic_run_plan_summary_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "variant_count": len(results),
        "cost_scenarios": COST_SCENARIOS,
        "baselines": BASELINES,
        "total_locked_configs": total_configs,
        "results": results,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = [
        "# Stage B Pragmatic Run Plan Summary",
        "",
        f"Generated UTC: `{payload['generated_at']}`",
        "",
        f"- Stage C access: `{payload['stage_c_access']}`",
        f"- Training launched: `{payload['training_launched']}`",
        f"- Variants: `{payload['variant_count']}`",
        f"- Cost scenarios: `{payload['cost_scenarios']}`",
        f"- Baselines: `{payload['baselines']}`",
        f"- Total locked configs: `{payload['total_locked_configs']}`",
        "",
        "| variant | locked configs | promotion blockers | manifest |",
        "| --- | ---: | --- | --- |",
    ]
    for row in results:
        out = row["agent_multi_stdout"]
        lines.append(
            f"| `{row['variant']}` | {out['config_count']} | `{out['promotion_blockers']}` | "
            f"`{out.get('manifest_file')}` |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    refs = write_reference_configs()
    results = [run_agent_multi_plan(ref) for ref in refs]
    payload = write_summary(results)
    print(json.dumps({
        "ok": True,
        "variant_count": payload["variant_count"],
        "total_locked_configs": payload["total_locked_configs"],
        "summary_json": str(SUMMARY_JSON),
        "summary_md": str(SUMMARY_MD),
        "training_launched": False,
        "stage_c_access": "DENIED",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
