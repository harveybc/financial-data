#!/usr/bin/env python3
"""Generate the targeted Stage B session-calendar diagnostic run plan.

This worker turns the three ``*_plus_session_calendar`` diagnostic inputs into
locked agent-multi configs and a financial-data dispatch plan. It does not
launch training and keeps Stage C denied in every emitted config.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AGENT_MULTI_ROOT = Path("/home/harveybc/Documents/GitHub/agent-multi")
PYTHON = Path("/home/harveybc/anaconda3/envs/trading-stack/bin/python")
AGENT_MULTI_TOOL = AGENT_MULTI_ROOT / "tools" / "project3_stageb_run_plan.py"
AGENT_MULTI_TEMPLATE = AGENT_MULTI_ROOT / "examples" / "config" / "project3_ethusdt_4h_sac_train_val_test_v3.json"

DIAGNOSTIC_INPUT_SUMMARY = (
    ROOT / "experiments" / "stage_b_validation" / "diagnostic_inputs" / "ethusdt" / "4h"
    / "feature_variant_materialization_summary.json"
)
OUT_ROOT = ROOT / "experiments" / "stage_b_validation" / "session_calendar_run_plan"
REFERENCE_DIR = OUT_ROOT / "reference_configs"
SUMMARY_JSON = OUT_ROOT / "stageb_session_calendar_run_plan_summary.json"
SUMMARY_MD = OUT_ROOT / "stageb_session_calendar_run_plan_summary.md"
PLAN_DIR = OUT_ROOT / "run_plan"
PLAN_JSON = PLAN_DIR / "stage_b_session_calendar_locked_run_plan.json"
PLAN_CSV = PLAN_DIR / "stage_b_session_calendar_locked_run_plan.csv"
PLAN_MD = PLAN_DIR / "stage_b_session_calendar_locked_run_plan.md"

HELDOUT_START = "2025-01-01"
COST_SCENARIOS = ["base", "plus_50pct", "plus_100pct"]
BASELINES = ["no_trade", "buy_and_hold", "random", "momentum", "reversal"]
TARGET_SUFFIX = "_plus_session_calendar"


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


def target_variants() -> list[dict[str, Any]]:
    summary = load_json(DIAGNOSTIC_INPUT_SUMMARY)
    variants = [
        item for item in (summary.get("variants") or [])
        if str(item.get("variant", "")).endswith(TARGET_SUFFIX)
    ]
    if len(variants) != 3:
        raise RuntimeError(f"expected 3 session-calendar variants, found {len(variants)}")
    return variants


def write_reference_configs(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pragmatic = load_worker_module(
        ROOT / "_scripts" / "workers" / "stage_b_pragmatic_run_plan_worker.py",
        "stage_b_pragmatic_run_plan_worker_for_session_calendar",
    )
    template = load_json(AGENT_MULTI_TEMPLATE)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    refs: list[dict[str, Any]] = []
    for variant_meta in variants:
        cfg = pragmatic.build_reference_config(template, variant_meta)
        name = str(variant_meta["variant"])
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
        "schema_version": "project3_stage_b_session_calendar_run_plan_summary_v1",
        "plan_id": "stageb_session_calendar_ethusdt_4h_sac_diagnostic_v1",
        "generated_at": utc_now(),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "variant_count": len(results),
        "cost_scenarios": COST_SCENARIOS,
        "baselines": BASELINES,
        "total_locked_configs": total_configs,
        "selection_rule": (
            "targeted session-calendar Stage B diagnostic: 3 ETHUSDT 4h SAC "
            "feature variants x 5 seeds x 3 costs x candidate+5 baselines"
        ),
        "results": results,
    }
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    lines = [
        "# Stage B Session-Calendar Run Plan Summary",
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
        "| variant | locked configs | feature count | manifest |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in results:
        out = row["agent_multi_stdout"]
        ref = load_json(Path(row["reference_config"]))
        lines.append(
            f"| `{row['variant']}` | {out['config_count']} | "
            f"{len(ref.get('feature_columns') or [])} | `{out.get('manifest_file')}` |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def write_dispatch_plan(summary: dict[str, Any]) -> dict[str, Any]:
    dispatch = load_worker_module(
        ROOT / "_scripts" / "workers" / "stage_b_pragmatic_dispatch_plan_worker.py",
        "stage_b_pragmatic_dispatch_plan_worker_for_session_calendar",
    )
    dispatch.SUMMARY_JSON = SUMMARY_JSON
    dispatch.PLAN_DIR = PLAN_DIR
    dispatch.PLAN_JSON = PLAN_JSON
    dispatch.PLAN_CSV = PLAN_CSV
    dispatch.PLAN_MD = PLAN_MD
    entries = dispatch.build_entries(summary)
    return dispatch.write_outputs(entries, summary)


def main() -> int:
    variants = target_variants()
    refs = write_reference_configs(variants)
    results = [run_agent_multi_plan(ref) for ref in refs]
    summary = write_summary(results)
    dispatch = write_dispatch_plan(summary)
    print(json.dumps({
        "ok": True,
        "variant_count": summary["variant_count"],
        "total_locked_configs": summary["total_locked_configs"],
        "machine_assignment_counts": dispatch["machine_assignment_counts"],
        "summary_json": str(SUMMARY_JSON),
        "summary_md": str(SUMMARY_MD),
        "plan_json": str(PLAN_JSON),
        "plan_md": str(PLAN_MD),
        "training_launched": False,
        "stage_c_access": "DENIED",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
