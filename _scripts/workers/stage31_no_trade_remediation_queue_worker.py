#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
PLAN_CSV = ROOT / "experiments" / "stage_a_screening" / "hardening" / "no_trade_remediation_plan.csv"
QUEUES = ROOT / "experiments" / "stage_a_screening" / "queues"
OUT_DIR = ROOT / "experiments" / "stage_a_screening" / "hardening"
OUT_JSON = OUT_DIR / "no_trade_remediation_queue_packet.json"
OUT_MD = OUT_DIR / "no_trade_remediation_queue_packet.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    tmp.replace(path)


def load_plan() -> list[dict[str, str]]:
    with PLAN_CSV.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_queues() -> dict[str, list[dict[str, Any]]]:
    queues: dict[str, list[dict[str, Any]]] = {}
    for machine in ("dragon", "gamma", "omega"):
        payload = read_json(QUEUES / f"{machine}.json", [])
        queues[machine] = payload if isinstance(payload, list) else []
    return queues


def all_run_ids(queues: dict[str, list[dict[str, Any]]]) -> set[str]:
    return {
        str(job.get("run_id"))
        for jobs in queues.values()
        for job in jobs
        if job.get("run_id")
    }


def base_config(row: dict[str, str]) -> dict[str, Any]:
    cfg = read_json(Path(row.get("run_dir") or "") / "config.json", {})
    return cfg if isinstance(cfg, dict) else {}


def original_timesteps(row: dict[str, str]) -> int:
    cfg = base_config(row)
    for key in ("total_timesteps", "timesteps"):
        try:
            value = int(float(cfg.get(key)))
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass
    return 50_000


def fix_id(patch: dict[str, Any]) -> str:
    return str(patch.get("no_trade_fix_id") or "unknown_fix")


def diagnostic_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected = []
    for row in rows:
        if str(row.get("recommended_action") or "").startswith("diagnostic_"):
            if str(row.get("duplicate_existing_exact_signature")).lower() == "true":
                continue
            selected.append(row)
    return selected


def choose_machine(row: dict[str, str], counts: Counter[str]) -> str:
    algo = row.get("algo", "").lower()
    timeframe = row.get("timeframe", "")
    if algo in {"ppo", "dqn"} and timeframe in {"1h", "4h"}:
        return "omega"
    return "dragon" if counts["dragon"] <= counts["gamma"] else "gamma"


def build_job(row: dict[str, str], timesteps_cap: int) -> dict[str, Any]:
    patch = json.loads(row.get("parameter_patch_json") or "{}")
    smoke_timesteps = min(original_timesteps(row), timesteps_cap)
    run_id = (
        f"{row['asset']}_{row['timeframe']}_{row['preset']}_{row['algo']}"
        f"_s{row['seed']}_{smoke_timesteps}_notrade_{fix_id(patch)}"
    )
    return {
        "algo": row["algo"],
        "asset": row["asset"],
        "config_overrides": patch,
        "device": "cuda",
        "diagnostic_origin_run_slug": row.get("run_slug", ""),
        "diagnostic_reason": row.get("reason", ""),
        "no_trade_diagnostic": True,
        "preset": row["preset"],
        "run_id": run_id,
        "seed": int(float(row["seed"])),
        "stage": "3.1_no_trade_diagnostic_smoke",
        "status": "pending",
        "timeframe": row["timeframe"],
        "timesteps": smoke_timesteps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue first-layer no-trade diagnostic smoke jobs.")
    parser.add_argument("--execute", action="store_true", help="Append jobs to machine queue JSON files.")
    parser.add_argument("--timesteps-cap", type=int, default=10_000)
    parser.add_argument("--limit", type=int, default=0, help="Optional cap for smoke jobs; 0 means all diagnostic rows.")
    args = parser.parse_args()

    queues = load_queues()
    known = all_run_ids(queues)
    counts = Counter({machine: 0 for machine in queues})
    appended: dict[str, list[dict[str, Any]]] = {machine: [] for machine in queues}
    skipped = Counter()

    rows = diagnostic_rows(load_plan())
    if args.limit > 0:
        rows = rows[: args.limit]
    for row in rows:
        job = build_job(row, max(1_000, int(args.timesteps_cap)))
        if job["run_id"] in known:
            skipped["already_known_run_id"] += 1
            continue
        machine = choose_machine(row, counts)
        counts[machine] += 1
        known.add(job["run_id"])
        appended[machine].append(job)
        if args.execute:
            queues[machine].append(job)

    if args.execute:
        for machine, jobs in queues.items():
            write_json(QUEUES / f"{machine}.json", jobs)

    payload = {
        "schema_version": "project3_no_trade_remediation_queue_packet_v1",
        "generated_at_utc": utc_now(),
        "execute": bool(args.execute),
        "timesteps_cap": int(args.timesteps_cap),
        "plan_csv": str(PLAN_CSV),
        "diagnostic_rows_considered": len(rows),
        "appended_counts": {machine: len(jobs) for machine, jobs in appended.items()},
        "skipped": dict(skipped),
        "policy": {
            "first_layer_no_trade_preflight_required": True,
            "diagnostic_jobs_are_new_trials": True,
            "telemetry_only_rows_not_enqueued": True,
            "exact_existing_signatures_not_enqueued": True,
            "promotion_eligible": False,
        },
        "jobs": appended,
    }
    write_json(OUT_JSON, payload)

    lines = [
        "# Stage 3.1 No-Trade Remediation Queue Packet",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Execute: `{payload['execute']}`",
        f"Diagnostic rows considered: `{payload['diagnostic_rows_considered']}`",
        "",
        "| Machine | Appended smoke jobs |",
        "| --- | ---: |",
    ]
    for machine in ("dragon", "gamma", "omega"):
        lines.append(f"| {machine} | {len(appended[machine])} |")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- Every appended job uses the existing forced-action no-trade preflight before training.",
            "- Every appended job is diagnostic-only and not promotion evidence.",
            "- Telemetry-only rows are not enqueued; they need better logs, not blind reruns.",
            "- Existing exact signatures are skipped.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("execute", "appended_counts", "skipped")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
