#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
QUEUES = ROOT / "experiments" / "stage_a_screening" / "queues"
LEDGER_CANDIDATES = [
    ROOT / "artifacts" / "run_ledger.jsonl",
    ROOT / "artifacts" / "run_ledger_events" / "dragon.remote.jsonl",
    ROOT / "artifacts" / "run_ledger_events" / "gamma.remote.jsonl",
    ROOT / "artifacts" / "run_ledger_events" / "omega.jsonl",
]
OUT_DIR = ROOT / "experiments" / "stage_a_screening" / "job_timing"

RUNNABLE = {"", "pending", "queued", "retry", "needs_retry"}
ACTIVE = {"training", "running", "registered", "preparing_input"}
END_EVENTS = {"complete", "failed"}


def parse_ts(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def iter_ledger_events() -> list[dict[str, Any]]:
    seen: set[str] = set()
    events: list[dict[str, Any]] = []
    for path in LEDGER_CANDIDATES:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_id = str(event.get("event_id") or f"{path}:{len(events)}")
                if event_id in seen:
                    continue
                seen.add(event_id)
                events.append(event)
    events.sort(key=lambda item: str(item.get("event_ts") or ""))
    return events


def job_key(job: dict[str, Any]) -> tuple[str, str, str, int]:
    return (
        str(job.get("timeframe") or ""),
        str(job.get("feature_preset") or job.get("preset") or ""),
        str(job.get("algorithm") or job.get("algo") or ""),
        int(job.get("timesteps") or 0),
    )


def duration_register(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    starts: dict[tuple[str, str], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for event in events:
        run_id = str(event.get("run_id") or "")
        machine = str(event.get("machine") or "")
        if not run_id or not machine:
            continue
        event_type = str(event.get("event_type") or event.get("status") or "").lower()
        ts = parse_ts(event.get("event_ts"))
        if ts is None:
            continue
        key = (machine, run_id)
        if event_type == "training":
            starts[key] = event
            continue
        if event_type not in END_EVENTS or key not in starts:
            continue
        start = starts.pop(key)
        start_ts = parse_ts(start.get("event_ts"))
        if start_ts is None or ts < start_ts:
            continue
        minutes = (ts - start_ts).total_seconds() / 60.0
        if minutes <= 0:
            continue
        rows.append(
            {
                "machine": machine,
                "run_id": run_id,
                "asset": event.get("asset") or start.get("asset") or "",
                "timeframe": event.get("timeframe") or start.get("timeframe") or "",
                "preset": event.get("feature_preset") or start.get("feature_preset") or "",
                "algorithm": event.get("algorithm") or start.get("algorithm") or "",
                "seed": event.get("seed") if event.get("seed") is not None else start.get("seed"),
                "timesteps": event.get("timesteps") or start.get("timesteps") or "",
                "start_time_utc": start_ts.isoformat(),
                "end_time_utc": ts.isoformat(),
                "duration_minutes": f"{minutes:.2f}",
                "end_status": event_type,
                "exit_code": event.get("exit_code"),
            }
        )
    return rows


def build_duration_groups(register: list[dict[str, Any]]) -> dict[str, dict[tuple, list[float]]]:
    groups: dict[str, dict[tuple, list[float]]] = {
        "exact": defaultdict(list),
        "preset_algo": defaultdict(list),
        "timeframe_preset": defaultdict(list),
        "preset": defaultdict(list),
        "timeframe": defaultdict(list),
        "global": defaultdict(list),
    }
    for row in register:
        if row.get("end_status") != "complete":
            continue
        try:
            minutes = float(row["duration_minutes"])
        except Exception:
            continue
        timeframe = str(row.get("timeframe") or "")
        preset = str(row.get("preset") or "")
        algo = str(row.get("algorithm") or "")
        timesteps = int(row.get("timesteps") or 0)
        groups["exact"][(timeframe, preset, algo, timesteps)].append(minutes)
        groups["preset_algo"][(preset, algo, timesteps)].append(minutes)
        groups["timeframe_preset"][(timeframe, preset, timesteps)].append(minutes)
        groups["preset"][(preset, timesteps)].append(minutes)
        groups["timeframe"][(timeframe, timesteps)].append(minutes)
        groups["global"][("global",)].append(minutes)
    return groups


def estimate_minutes(job: dict[str, Any], groups: dict[str, dict[tuple, list[float]]]) -> tuple[float | None, str, int]:
    timeframe, preset, algo, timesteps = job_key(job)
    lookups = [
        ("exact", (timeframe, preset, algo, timesteps)),
        ("preset_algo", (preset, algo, timesteps)),
        ("timeframe_preset", (timeframe, preset, timesteps)),
        ("preset", (preset, timesteps)),
        ("timeframe", (timeframe, timesteps)),
        ("global", ("global",)),
    ]
    for label, key in lookups:
        values = groups[label].get(key, [])
        if values:
            return statistics.median(values), label, len(values)
    return None, "no_history", 0


def load_queue_jobs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for machine in ("omega", "dragon", "gamma"):
        queue = read_json(QUEUES / f"{machine}.json", [])
        if not isinstance(queue, list):
            continue
        for idx, job in enumerate(queue):
            status = str(job.get("status") or "pending").lower()
            if status not in RUNNABLE and status not in ACTIVE:
                continue
            row = dict(job)
            row["machine"] = machine
            row["queue_index"] = idx
            row["status"] = status or "pending"
            rows.append(row)
    return rows


def find_latest_start(events: list[dict[str, Any]], machine: str, run_id: str) -> str:
    latest: datetime | None = None
    for event in events:
        if str(event.get("machine") or "") != machine:
            continue
        if str(event.get("run_id") or "") != run_id:
            continue
        if str(event.get("event_type") or event.get("status") or "").lower() not in ACTIVE:
            continue
        ts = parse_ts(event.get("event_ts"))
        if ts and (latest is None or ts > latest):
            latest = ts
    return latest.isoformat() if latest else ""


def candidate_progress_files(job: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    config_path = job.get("config")
    if config_path:
        cfg = read_json(Path(str(config_path)), {})
        if isinstance(cfg, dict):
            for key in ("training_progress_file", "progress_file"):
                value = cfg.get(key)
                if value:
                    candidates.append(Path(str(value)))
    for key in ("training_progress_file", "progress_file"):
        value = job.get(key)
        if value:
            candidates.append(Path(str(value)))
    machine = str(job.get("machine") or "")
    run_id = str(job.get("run_id") or "")
    if machine and run_id:
        candidates.append(ROOT / "experiments" / "stage_a_screening" / "runs" / machine / f"{run_id}_training_progress.json")
    unique: list[Path] = []
    seen: set[str] = set()
    for path in candidates:
        key = str(path)
        if key not in seen:
            unique.append(path)
            seen.add(key)
    return unique


def load_progress(job: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    fallback = ""
    for path in candidate_progress_files(job):
        if not fallback:
            fallback = str(path)
        payload = read_json(path, None)
        if isinstance(payload, dict):
            return payload, str(path)
    return None, fallback


def estimated_end_time(generated_at: datetime, remaining_minutes: float) -> str:
    if remaining_minutes <= 0:
        return generated_at.isoformat()
    return datetime.fromtimestamp(
        generated_at.timestamp() + remaining_minutes * 60.0,
        tz=timezone.utc,
    ).isoformat()


def add_minutes(base: datetime, minutes: float) -> datetime:
    return datetime.fromtimestamp(base.timestamp() + minutes * 60.0, tz=timezone.utc)


def progress_for_job(
    job: dict[str, Any],
    status: str,
    elapsed_minutes: float,
    estimated_duration_minutes: float,
) -> tuple[float, str, str, str, dict[str, Any] | None]:
    if status in RUNNABLE:
        return 0.0, "queued", "not_started", "", None
    progress, path = load_progress(job)
    if progress:
        try:
            percent = float(progress.get("progress_percent"))
        except (TypeError, ValueError):
            percent = 0.0
        percent = min(100.0, max(0.0, percent))
        phase = str(progress.get("status") or "training")
        detail = str(progress.get("progress_detail") or "")
        if detail:
            detail = f"{phase}: {detail}"
        else:
            detail = phase
        return percent, "exact_sb3_callback", detail, path, progress
    if status in ACTIVE and estimated_duration_minutes > 0:
        percent = min(99.0, max(0.0, (elapsed_minutes / estimated_duration_minutes) * 100.0))
        detail = f"{elapsed_minutes:.2f}/{estimated_duration_minutes:.2f} estimated minutes elapsed"
        return percent, "elapsed_eta_estimate", detail, path, None
    return 0.0, "unknown", status, path, None


def metric_from_progress(progress: dict[str, Any] | None, key: str) -> Any:
    if not isinstance(progress, dict):
        return ""
    value = progress.get(key)
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> int:
    generated_at = datetime.now(timezone.utc)
    events = iter_ledger_events()
    register = duration_register(events)
    groups = build_duration_groups(register)
    queue_jobs = load_queue_jobs()

    pending_rows: list[dict[str, Any]] = []
    active_remaining: dict[str, float] = {}
    machine_load: dict[str, float] = defaultdict(float)
    machine_next_available: dict[str, datetime] = defaultdict(lambda: generated_at)
    for job in queue_jobs:
        estimate, method, sample_size = estimate_minutes(job, groups)
        estimate = estimate if estimate is not None else 0.0
        status = str(job.get("status") or "pending").lower()
        start_time = find_latest_start(events, str(job["machine"]), str(job.get("run_id") or ""))
        elapsed = 0.0
        if start_time:
            started = parse_ts(start_time)
            if started:
                elapsed = max(0.0, (generated_at - started).total_seconds() / 60.0)
        progress_percent, progress_source, progress_detail, progress_path, progress_payload = progress_for_job(
            job,
            status,
            elapsed,
            estimate,
        )
        if status in ACTIVE and progress_source == "exact_sb3_callback" and progress_percent > 0:
            remaining = max(0.0, elapsed * ((100.0 - progress_percent) / progress_percent))
        else:
            remaining = max(0.0, estimate - elapsed) if status in ACTIVE else estimate
        machine = str(job["machine"])
        if status in ACTIVE:
            estimated_start_dt = parse_ts(start_time) or generated_at
            estimated_end_dt = add_minutes(generated_at, remaining)
            if estimated_end_dt > machine_next_available[machine]:
                machine_next_available[machine] = estimated_end_dt
        else:
            estimated_start_dt = machine_next_available[machine]
            estimated_end_dt = add_minutes(estimated_start_dt, estimate)
            machine_next_available[machine] = estimated_end_dt
        row = {
            "machine": job.get("machine"),
            "queue_index": job.get("queue_index"),
            "status": status,
            "run_id": job.get("run_id"),
            "asset": job.get("asset"),
            "timeframe": job.get("timeframe"),
            "preset": job.get("feature_preset") or job.get("preset"),
            "algorithm": job.get("algorithm") or job.get("algo"),
            "seed": job.get("seed"),
            "timesteps": job.get("timesteps"),
            "device": job.get("device"),
            "cost_scenario": job.get("cost_scenario", ""),
            "source_family": job.get("source_family", ""),
            "feature_family": job.get("feature_family", ""),
            "start_time_utc": start_time,
            "end_time_utc": "",
            "estimated_start_time_utc": estimated_start_dt.isoformat() if estimate else "",
            "estimated_end_time_utc": estimated_end_dt.isoformat() if estimate else "",
            "estimated_duration_minutes": f"{estimate:.2f}" if estimate else "",
            "elapsed_minutes": f"{elapsed:.2f}" if elapsed else "",
            "estimated_remaining_minutes": f"{remaining:.2f}" if estimate else "",
            "progress_percent": f"{progress_percent:.2f}",
            "progress_source": progress_source,
            "progress_detail": progress_detail,
            "progress_file": progress_path,
            "trades_total": metric_from_progress(progress_payload, "trades_total"),
            "profit_percent": metric_from_progress(progress_payload, "profit_percent"),
            "total_return": metric_from_progress(progress_payload, "total_return"),
            "final_equity": metric_from_progress(progress_payload, "final_equity"),
            "action_non_hold_rate": metric_from_progress(progress_payload, "action_non_hold_rate"),
            "action_deadband_rate": metric_from_progress(progress_payload, "action_deadband_rate"),
            "action_abs_mean": metric_from_progress(progress_payload, "action_abs_mean"),
            "execution_entry_actions_seen": metric_from_progress(progress_payload, "execution_entry_actions_seen"),
            "execution_entry_orders_submitted": metric_from_progress(progress_payload, "execution_entry_orders_submitted"),
            "no_trade_diagnosis": metric_from_progress(progress_payload, "no_trade_diagnosis"),
            "eta_basis": method,
            "eta_sample_size": sample_size,
        }
        pending_rows.append(row)
        machine_load[str(job["machine"])] += remaining
        if status in ACTIVE:
            active_remaining[str(job["machine"])] = remaining

    pending_fields = [
        "machine",
        "queue_index",
        "status",
        "run_id",
        "asset",
        "timeframe",
        "preset",
        "algorithm",
        "seed",
        "timesteps",
        "device",
        "cost_scenario",
        "source_family",
        "feature_family",
        "start_time_utc",
        "end_time_utc",
        "estimated_start_time_utc",
        "estimated_end_time_utc",
        "estimated_duration_minutes",
        "elapsed_minutes",
        "estimated_remaining_minutes",
        "progress_percent",
        "progress_source",
        "progress_detail",
        "progress_file",
        "trades_total",
        "profit_percent",
        "total_return",
        "final_equity",
        "action_non_hold_rate",
        "action_deadband_rate",
        "action_abs_mean",
        "execution_entry_actions_seen",
        "execution_entry_orders_submitted",
        "no_trade_diagnosis",
        "eta_basis",
        "eta_sample_size",
    ]
    register_fields = [
        "machine",
        "run_id",
        "asset",
        "timeframe",
        "preset",
        "algorithm",
        "seed",
        "timesteps",
        "start_time_utc",
        "end_time_utc",
        "duration_minutes",
        "end_status",
        "exit_code",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(OUT_DIR / "stage31_pending_jobs_with_eta.csv", pending_rows, pending_fields)
    write_csv(OUT_DIR / "stage31_task_progress.csv", pending_rows, pending_fields)
    write_csv(OUT_DIR / "stage31_job_timing_register.csv", register, register_fields)
    (OUT_DIR / "stage31_task_progress.json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "schema_version": "project3_stage31_task_progress_v1",
                "rows": pending_rows,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    counts = defaultdict(int)
    for row in pending_rows:
        counts[(row["machine"], row["status"])] += 1

    active_machines = {row["machine"] for row in pending_rows if row["status"] in ACTIVE}
    backlog_minutes = {
        machine: sum(
            float(row["estimated_remaining_minutes"] or 0.0)
            for row in pending_rows
            if row["machine"] == machine
        )
        for machine in ("dragon", "gamma", "omega")
    }
    wall_clock_minutes = max(backlog_minutes.get(machine, 0.0) for machine in active_machines) if active_machines else 0.0

    lines = [
        "# Stage 3.1 Pending Jobs And ETA",
        "",
        f"Generated UTC: {generated_at.isoformat()}",
        "",
        "## Summary",
        "",
        f"- Pending/active rows tracked: {len(pending_rows)}",
        f"- Historical completed timing samples: {sum(1 for row in register if row['end_status'] == 'complete')}",
        f"- Estimated wall-clock to drain current active+pending GPU queues: {wall_clock_minutes / 60.0:.2f} hours",
        "",
        "| Machine | Active | Pending | Estimated remaining machine-hours |",
        "| --- | ---: | ---: | ---: |",
    ]
    for machine in ("dragon", "gamma", "omega"):
        active = sum(1 for row in pending_rows if row["machine"] == machine and row["status"] in ACTIVE)
        pending = sum(1 for row in pending_rows if row["machine"] == machine and row["status"] in RUNNABLE)
        lines.append(f"| {machine} | {active} | {pending} | {backlog_minutes.get(machine, 0.0) / 60.0:.2f} |")
    lines += [
        "",
        "## Current Active Jobs",
        "",
        "| Machine | Run ID | Asset | TF | Preset | Algo | Seed | Started UTC | Progress | Trades | Profit % | Action non-hold | Deadband | Diagnosis | Source | ETA remaining min | Basis |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | --- |",
    ]
    for row in pending_rows:
        if row["status"] not in ACTIVE:
            continue
        lines.append(
            f"| {row['machine']} | `{row['run_id']}` | {row['asset']} | {row['timeframe']} | "
            f"{row['preset']} | {row['algorithm']} | {row['seed']} | {row['start_time_utc']} | "
            f"{row['progress_percent']}% | {row.get('trades_total', '')} | {row.get('profit_percent', '')} | "
            f"{row.get('action_non_hold_rate', '')} | {row.get('action_deadband_rate', '')} | "
            f"{row.get('no_trade_diagnosis', '')} | {row['progress_source']} | {row['estimated_remaining_minutes']} | "
            f"{row['eta_basis']} n={row['eta_sample_size']} |"
        )
    lines += [
        "",
        "## Pending Jobs",
        "",
        "| # | Machine | Run ID | Asset | TF | Preset | Algo | Seed | Steps | Progress | ETA min | Est start UTC | Est end UTC | Basis |",
        "| ---: | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    idx = 1
    for row in pending_rows:
        if row["status"] not in RUNNABLE:
            continue
        lines.append(
            f"| {idx} | {row['machine']} | `{row['run_id']}` | {row['asset']} | {row['timeframe']} | "
            f"{row['preset']} | {row['algorithm']} | {row['seed']} | {row['timesteps']} | "
            f"{row['progress_percent']}% | {row['estimated_remaining_minutes']} | "
            f"{row['estimated_start_time_utc']} | {row['estimated_end_time_utc']} | "
            f"{row['eta_basis']} n={row['eta_sample_size']} |"
        )
        idx += 1
    lines += [
        "",
        "## Output Files",
        "",
        f"- Pending jobs CSV: `{OUT_DIR / 'stage31_pending_jobs_with_eta.csv'}`",
        f"- Task progress CSV: `{OUT_DIR / 'stage31_task_progress.csv'}`",
        f"- Task progress JSON: `{OUT_DIR / 'stage31_task_progress.json'}`",
        f"- Timing register CSV: `{OUT_DIR / 'stage31_job_timing_register.csv'}`",
        "",
        "Notes:",
        "- ETAs are medians from completed `training -> complete` ledger pairs.",
        "- `exact_sb3_callback` progress is measured from the PPO/SAC/DQN `model.learn()` callback.",
        "- `elapsed_eta_estimate` progress is used only for already-running jobs that started before callback instrumentation was available.",
        "- Matching priority: exact `(timeframe, preset, algo, timesteps)`, then preset+algo, timeframe+preset, preset, timeframe, global.",
        "- Active job remaining time subtracts elapsed time since the latest ledger active event.",
        "- Pending job start/end estimates are queue-aware and serialized per assigned machine.",
    ]
    (OUT_DIR / "stage31_pending_jobs_with_eta.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT_DIR / "stage31_task_progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "generated_at": generated_at.isoformat(),
        "pending_rows": len(pending_rows),
        "timing_samples": len(register),
        "completed_timing_samples": sum(1 for row in register if row["end_status"] == "complete"),
        "estimated_wall_clock_hours": round(wall_clock_minutes / 60.0, 3),
        "outputs": {
            "pending_csv": str(OUT_DIR / "stage31_pending_jobs_with_eta.csv"),
            "task_progress_csv": str(OUT_DIR / "stage31_task_progress.csv"),
            "task_progress_json": str(OUT_DIR / "stage31_task_progress.json"),
            "task_progress_md": str(OUT_DIR / "stage31_task_progress.md"),
            "timing_register_csv": str(OUT_DIR / "stage31_job_timing_register.csv"),
            "markdown": str(OUT_DIR / "stage31_pending_jobs_with_eta.md"),
        },
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
