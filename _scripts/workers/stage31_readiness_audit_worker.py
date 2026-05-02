from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
AGENT_MULTI_ROOT = Path(os.environ.get("AGENT_MULTI_ROOT", "/home/harveybc/Documents/GitHub/agent-multi"))
ASSETS = ("btcusdt", "ethusdt", "btcusdt_perp", "eurusd", "usdjpy")
FIRST_WAVE_TIMEFRAMES = ("1h", "4h")
LEARNED_METHODS = ("lstm", "cnn")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def check_path(label: str, path: Path) -> dict[str, Any]:
    return {"label": label, "path": str(path), "exists": path.exists()}


def check_python_module(name: str) -> dict[str, Any]:
    return {"module": name, "available": importlib.util.find_spec(name) is not None}


def git_head(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        cp = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except Exception:
        return None
    return cp.stdout.strip() or None


def feature_path(asset: str, timeframe: str, name: str) -> Path:
    return ROOT / "features" / "trading_asset_features" / asset / timeframe / name


def stage2_feature_coverage() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for asset in ASSETS:
        for timeframe in FIRST_WAVE_TIMEFRAMES:
            expected = {
                "technical": feature_path(asset, timeframe, "technical.parquet"),
                "statistical": feature_path(asset, timeframe, "statistical.parquet"),
                "wavelet": feature_path(asset, timeframe, "wavelet.parquet"),
                "emd": feature_path(asset, timeframe, "emd.parquet"),
                "fracdiff": feature_path(asset, timeframe, "fracdiff.parquet"),
                "sota_intrabar_realized": feature_path(asset, timeframe, "sota_intrabar_realized.parquet"),
                "sota_hmm_regime": feature_path(asset, timeframe, "sota_hmm_regime.parquet"),
            }
            for method in LEARNED_METHODS:
                expected[f"learned_{method}"] = feature_path(asset, timeframe, f"learned_{method}.parquet")
            missing = [name for name, path in expected.items() if not path.exists()]
            rows.append(
                {
                    "asset": asset,
                    "timeframe": timeframe,
                    "status": "ready" if not missing else "incomplete",
                    "missing": missing,
                    "available": sorted(name for name in expected if name not in missing),
                }
            )
    return rows


def run_audit(machine: str) -> dict[str, Any]:
    design_docs = [
        check_path("pre_registered_design", ROOT / "experiments" / "design" / "pre_registered_design.md"),
        check_path("kill_criteria", ROOT / "experiments" / "design" / "kill_criteria.md"),
        check_path("multiple_testing_correction", ROOT / "experiments" / "design" / "multiple_testing_correction.md"),
        check_path("stage_a_runs_dir", ROOT / "experiments" / "stage_a_screening" / "runs"),
    ]
    agent_multi_checks = [
        check_path("agent_multi_repo", AGENT_MULTI_ROOT),
        check_path("seed_sweep", AGENT_MULTI_ROOT / "tools" / "seed_sweep.py"),
        check_path("ppo_agent", AGENT_MULTI_ROOT / "agent_plugins" / "ppo_agent.py"),
        check_path("sac_agent", AGENT_MULTI_ROOT / "agent_plugins" / "sac_agent.py"),
        check_path("dqn_agent", AGENT_MULTI_ROOT / "agent_plugins" / "dqn_agent.py"),
    ]
    modules = [check_python_module(name) for name in ("numpy", "pandas", "stable_baselines3", "gymnasium")]
    coverage = stage2_feature_coverage()
    incomplete = [row for row in coverage if row["status"] != "ready"]
    blockers: list[str] = []
    if any(not item["exists"] for item in design_docs):
        blockers.append("Stage 3.1 design docs are incomplete.")
    if any(not item["exists"] for item in agent_multi_checks):
        blockers.append("agent-multi run infrastructure is incomplete.")
    if any(not item["available"] for item in modules):
        blockers.append("One or more Stage 3 Python runtime modules are missing in the active environment.")
    if incomplete:
        blockers.append("Some first-wave Stage 2 feature inputs are incomplete; Stage A must skip those presets until complete.")
    return {
        "generated_at": utc_now(),
        "stage": "Stage 3.1",
        "machine": machine,
        "deliverable": "Phase 3 experiment framework readiness audit",
        "financial_data_git_head": git_head(ROOT),
        "agent_multi_git_head": git_head(AGENT_MULTI_ROOT),
        "python": sys.executable,
        "design_docs": design_docs,
        "agent_multi_checks": agent_multi_checks,
        "python_modules": modules,
        "first_wave_feature_coverage": coverage,
        "first_wave_ready_cells": len(coverage) - len(incomplete),
        "first_wave_total_cells": len(coverage),
        "blockers": blockers,
        "status": "ready_with_skips" if incomplete and not blockers[:-1] else ("blocked" if blockers else "ready"),
    }


def write_outputs(machine: str, payload: dict[str, Any]) -> None:
    metadata_path = ROOT / "_metadata" / f"stage31_readiness_audit_{machine}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report_path = ROOT / "_logs" / "supervisor_reports" / f"stage31_readiness_audit_{machine}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 3.1 Readiness Audit",
        "",
        f"Generated: {payload['generated_at']}",
        f"Machine: {machine}",
        f"Status: `{payload['status']}`",
        "",
        "## Summary",
        "",
        f"- Stage: {payload['stage']}",
        f"- Deliverable: {payload['deliverable']}",
        f"- financial-data git head: `{payload['financial_data_git_head']}`",
        f"- agent-multi git head: `{payload['agent_multi_git_head']}`",
        f"- First-wave ready cells: {payload['first_wave_ready_cells']}/{payload['first_wave_total_cells']}",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["blockers"]) if payload["blockers"] else lines.append("- none")
    lines.extend(["", "## First-Wave Incomplete Cells", ""])
    incomplete = [row for row in payload["first_wave_feature_coverage"] if row["status"] != "ready"]
    if incomplete:
        for row in incomplete:
            lines.append(f"- `{row['asset']}:{row['timeframe']}` missing: {', '.join(row['missing'])}")
    else:
        lines.append("- none")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--machine", default="gamma")
    args = parser.parse_args()
    payload = run_audit(args.machine)
    write_outputs(args.machine, payload)
    print(json.dumps({"status": payload["status"], "blockers": payload["blockers"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
