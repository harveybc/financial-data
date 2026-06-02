#!/usr/bin/env python3
"""Build the executable Stage B dispatch plan from the pragmatic run plans.

This worker is the bridge between the Stage B pragmatic matrix and the existing
executor/status tooling. It does not launch training. It translates the
per-variant agent-multi manifests into the canonical
``stage_b_locked_run_plan.json`` schema, assigns each cell to dragon/gamma/omega,
and keeps Stage C denied in every emitted row.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SUMMARY_JSON = (
    ROOT / "experiments" / "stage_b_validation" / "pragmatic_run_plan"
    / "stageb_pragmatic_run_plan_summary.json"
)
PLAN_DIR = ROOT / "experiments" / "stage_b_validation" / "run_plan"
PLAN_JSON = PLAN_DIR / "stage_b_locked_run_plan.json"
PLAN_CSV = PLAN_DIR / "stage_b_locked_run_plan.csv"
PLAN_MD = PLAN_DIR / "stage_b_locked_run_plan.md"

HELDOUT_START = "2025-01-01"
MACHINE_CYCLE = ("dragon", "gamma", "dragon", "gamma", "omega")


class DispatchPlanError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise DispatchPlanError(f"failed to load JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise DispatchPlanError(f"expected JSON object at {path}")
    return payload


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def metadata_for_config(config: dict[str, Any]) -> dict[str, Any]:
    meta_path = Path(str(config.get("_project3_pragmatic_source_metadata", "")))
    if meta_path.exists():
        return load_json(meta_path)
    return {}


def role_label(entry: dict[str, Any]) -> str:
    if entry.get("role") == "baseline":
        return "baseline"
    return "candidate"


def variant_id(*, variant: str, entry: dict[str, Any]) -> str:
    role = role_label(entry)
    baseline = entry.get("baseline_name")
    seed = entry.get("seed")
    cost = entry.get("cost_scenario")
    if role == "baseline":
        return f"baseline_{baseline}_{variant}_s{seed}_{cost}"
    return f"candidate_{variant}_s{seed}_{cost}"


def validate_locked_config(config_path: Path, config: dict[str, Any]) -> None:
    problems: list[str] = []
    if config.get("_NOT_TO_RUN_UNTIL_STAGE_B_APPROVED") is not True:
        problems.append("LOCK_FLAG_MISSING")
    if config.get("stage_c_access") != "DENIED":
        problems.append("STAGE_C_ACCESS_NOT_DENIED")
    if config.get("final_stage_c_evaluation") or config.get("stage_c_acknowledged"):
        problems.append("STAGE_C_AUTH_FLAG_SET")
    if config.get("heldout_start") != HELDOUT_START:
        problems.append("HELDOUT_START_MISMATCH")
    for key in ("progress_file", "training_progress_file", "return_trace_dir", "return_trace_file"):
        if not config.get(key):
            problems.append(f"{key.upper()}_MISSING")
    if config.get("progress_file") != config.get("training_progress_file"):
        problems.append("PROGRESS_FILE_PAIR_MISMATCH")
    if problems:
        raise DispatchPlanError(f"{config_path} is not executor-ready: {problems}")


def build_entries(summary: dict[str, Any]) -> list[dict[str, Any]]:
    if summary.get("stage_c_access") != "DENIED":
        raise DispatchPlanError("summary does not deny Stage C")
    if summary.get("training_launched") is not False:
        raise DispatchPlanError("summary claims training was already launched")

    entries: list[dict[str, Any]] = []
    machine_index = 0
    for result in summary.get("results", []):
        variant = str(result.get("variant", ""))
        stdout = result.get("agent_multi_stdout") or {}
        manifest_file = Path(str(stdout.get("manifest_file", "")))
        manifest = load_json(manifest_file)
        if manifest.get("stage_c_access") != "DENIED":
            raise DispatchPlanError(f"manifest does not deny Stage C: {manifest_file}")
        if manifest.get("promotion_blockers"):
            raise DispatchPlanError(
                f"manifest still has promotion blockers {manifest.get('promotion_blockers')}: {manifest_file}"
            )
        reference_config = str(manifest.get("reference_config") or result.get("reference_config") or "")
        reference_sha = str(manifest.get("reference_config_sha256") or "")

        for item in manifest.get("configs", []):
            config_path = Path(str(item.get("config_file", "")))
            config = load_json(config_path)
            validate_locked_config(config_path, config)
            meta = metadata_for_config(config)
            role = role_label(item)
            machine = MACHINE_CYCLE[machine_index % len(MACHINE_CYCLE)]
            machine_index += 1
            vid = variant_id(variant=variant, entry=item)
            entries.append({
                "variant_id": vid,
                "role": role,
                "baseline_name": item.get("baseline_name") or "",
                "candidate_run_slug": f"ethusdt_4h_sac_{variant}",
                "source_run_slug": f"stageb_pragmatic_{variant}",
                "source_stage_a_status": "PRAGMATIC_STAGE_B_DIAGNOSTIC",
                "asset": "ethusdt",
                "timeframe": "4h",
                "algo": "sac",
                "preset": variant,
                "seed": str(item.get("seed")),
                "cost_scenario": item.get("cost_scenario"),
                "stage_b_timesteps": int(config.get("total_timesteps", 0) or 0),
                "machine_hint": machine,
                "config_file": str(config_path),
                "source_config_file": reference_config,
                "source_config_sha256": reference_sha,
                "input_data_file": str(config.get("input_data_file", "")),
                "input_firewall_status": "PASS_HELDOUT_FIREWALL"
                if meta.get("max_timestamp_lt_heldout") is True else "UNKNOWN",
                "input_max_ts": meta.get("last_timestamp", ""),
                "run_dir": item.get("run_dir") or str(Path(str(config.get("save_model", ""))).parent),
                "progress_file": item.get("progress_file") or config.get("progress_file"),
                "return_trace_dir": item.get("return_trace_dir") or config.get("return_trace_dir"),
                "return_trace_file": item.get("return_trace_file") or config.get("return_trace_file"),
                "expected_evidence_file": item.get("expected_evidence_file") or "",
                "locked": True,
                "training_launched": False,
                "stage_c_access": "DENIED",
                "execution_status": "LOCKED_READY_FOR_STAGE_B_EXECUTION",
                "manifest_file": str(manifest_file),
                "config_sha256": sha256_file(config_path),
            })
    return entries


def write_outputs(entries: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    machine_counts: dict[str, int] = {m: 0 for m in ("dragon", "gamma", "omega")}
    for entry in entries:
        machine_counts[str(entry["machine_hint"])] = machine_counts.get(str(entry["machine_hint"]), 0) + 1
    payload = {
        "schema_version": "project3_stage_b_locked_run_plan_v2",
        "plan_id": summary.get("plan_id", "stageb_pragmatic_ethusdt_4h_sac_diagnostic_v1"),
        "generated_at_utc": utc_now(),
        "source_summary_json": str(SUMMARY_JSON),
        "heldout_start": HELDOUT_START,
        "stage_c_access": "DENIED",
        "training_launched": False,
        "selected_candidate_count": int(summary.get("variant_count", 10) or 10),
        "unique_config_count": len(entries),
        "cost_scenarios": summary.get("cost_scenarios", []),
        "machine_roster": ["dragon", "gamma", "omega"],
        "machine_assignment_rule": "weighted_round_robin dragon,gamma,dragon,gamma,omega",
        "machine_assignment_counts": machine_counts,
        "return_trace_schema_version": "stage_b_return_trace_v1",
        "evidence_schema_version": "project3_return_trace_evidence_v1",
        "no_trade_anomaly_rule": "abort non-no_trade-baseline when progress >= 20% and trades_total == 0",
        "minimum_required_live_progress_fields": [
            "progress_pct",
            "current_step",
            "total_timesteps",
            "trades_total",
            "total_return",
            "profit_percent",
        ],
        "selection_rule": summary.get(
            "selection_rule",
            "pragmatic diagnostic Stage B matrix: 10 ETHUSDT 4h SAC feature variants x 5 seeds x 3 costs x candidate+5 baselines",
        ),
        "promotion_rules": {
            "stage_c_forbidden": True,
            "minimum_paired_seeds": 5,
            "required_cost_scenarios": summary.get("cost_scenarios", []),
            "known_baselines": summary.get("baselines", []),
            "all_runs_count_as_trials": True,
        },
        "configs": entries,
    }
    PLAN_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    fields = [
        "variant_id", "machine_hint", "role", "baseline_name", "asset", "timeframe",
        "algo", "preset", "seed", "cost_scenario", "stage_b_timesteps",
        "execution_status", "config_file", "progress_file", "run_dir",
        "return_trace_file", "return_trace_dir", "expected_evidence_file",
        "input_data_file", "input_max_ts", "stage_c_access",
    ]
    with PLAN_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(entries)
    lines = [
        "# Project 3 Stage B Locked Run Plan",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        f"Plan ID: `{payload['plan_id']}`",
        f"Stage C access: `{payload['stage_c_access']}`",
        f"Training launched: `{payload['training_launched']}`",
        f"Configs: `{payload['unique_config_count']}`",
        f"Machine assignment counts: `{machine_counts}`",
        "",
        "## Dispatch Rule",
        "",
        payload["selection_rule"],
        "",
        "## Machine Counts",
        "",
    ]
    for machine, count in machine_counts.items():
        lines.append(f"- `{machine}`: {count}")
    lines += [
        "",
        "## First 30 Jobs",
        "",
        "| variant | machine | role | baseline | seed | cost | timesteps |",
        "| --- | --- | --- | --- | ---: | --- | ---: |",
    ]
    for entry in entries[:30]:
        lines.append(
            f"| `{entry['variant_id']}` | {entry['machine_hint']} | {entry['role']} | "
            f"{entry['baseline_name']} | {entry['seed']} | {entry['cost_scenario']} | "
            f"{entry['stage_b_timesteps']} |"
        )
    PLAN_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    summary = load_json(SUMMARY_JSON)
    entries = build_entries(summary)
    payload = write_outputs(entries, summary)
    print(json.dumps({
        "ok": True,
        "plan_json": str(PLAN_JSON),
        "plan_csv": str(PLAN_CSV),
        "plan_md": str(PLAN_MD),
        "unique_config_count": payload["unique_config_count"],
        "machine_assignment_counts": payload["machine_assignment_counts"],
        "stage_c_access": payload["stage_c_access"],
        "training_launched": payload["training_launched"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
