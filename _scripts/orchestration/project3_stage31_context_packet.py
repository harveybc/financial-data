#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
LOG_DIR = ROOT / "_logs" / "supervisor_reports"
OUT_MD = LOG_DIR / "stage31_worker_context_packet.md"
OUT_JSON = LOG_DIR / "stage31_worker_context_packet.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_jsonl_tail(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit * 4 :]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"raw": line})
    except Exception as exc:
        return [{"error": f"failed_to_read:{exc}"}]
    return rows[-limit:]


def event_state_tail(path: Path, limit: int = 10) -> list[dict[str, Any]]:
    data = read_json(path, {})
    if not isinstance(data, dict):
        return []
    rows = []
    for event, payload in data.items():
        if not isinstance(payload, dict):
            continue
        rows.append(
            {
                "event": event,
                "last_sent_at": payload.get("last_sent_at"),
                "digest": str(payload.get("digest", ""))[:12],
            }
        )
    rows.sort(key=lambda item: float(item.get("last_sent_at") or 0), reverse=True)
    return rows[:limit]


def queue_snapshot(machine: str) -> dict[str, Any]:
    path = ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json"
    jobs = read_json(path, [])
    if not isinstance(jobs, list):
        return {"machine": machine, "error": "queue_not_list", "path": str(path)}
    counts = Counter(str(job.get("status") or "pending") for job in jobs)
    active_statuses = {"training", "running", "registered", "preparing_input"}
    active = [
        {
            "run_id": job.get("run_id"),
            "status": job.get("status"),
            "algorithm": job.get("algorithm"),
            "asset": job.get("asset"),
            "timeframe": job.get("timeframe"),
            "feature_preset": job.get("feature_preset"),
            "seed": job.get("seed"),
            "started_at": job.get("started_at"),
        }
        for job in jobs
        if str(job.get("status") or "").lower() in active_statuses
    ]
    pending = [
        str(job.get("run_id"))
        for job in jobs
        if str(job.get("status") or "pending").lower() in {"", "pending", "queued", "retry", "needs_retry"}
    ][:8]
    return {
        "machine": machine,
        "path": str(path),
        "counts": dict(counts),
        "active": active,
        "pending_sample": pending,
    }


def session_message_tail(limit: int = 10) -> list[dict[str, Any]]:
    sessions_dir = Path("/home/harveybc/.hermes/sessions")
    if not sessions_dir.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(sessions_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:80]:
        data = read_json(path, {})
        text = json.dumps(data, ensure_ascii=True)[:5000]
        if "telegram" not in text.lower() and "HermesAgentOrchestration" not in text:
            continue
        rows.append({"session": str(path), "mtime": path.stat().st_mtime})
        if len(rows) >= limit:
            break
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def format_event(event: dict[str, Any]) -> str:
    compact = json.dumps(event, sort_keys=True)
    return compact[:500]


def main() -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    queues = [queue_snapshot(machine) for machine in ("omega", "dragon", "gamma")]
    payload = {
        "generated_at": utc_now(),
        "project_root": str(ROOT),
        "active_stage": "Stage 3.1 Experiment Framework, Stage A screening",
        "relevant_docs": [
            "work_plan/30_PHASE_3_OVERVIEW.md",
            "work_plan/31_STAGE_3_1_EXPERIMENT_FRAMEWORK.md",
            "work_plan/32_STAGE_3_2_RESULTS_SYNTHESIS.md",
            "work_plan/PROJECT3_SOTA_CRITIQUE_AND_IMPROVEMENT_PROPOSAL.md",
            "work_plan/SOTA_INTEGRATION_DECISIONS.md",
        ],
        "source_of_truth": [
            "experiments/stage_a_screening/queues/<machine>.json",
            "artifacts/run_ledger.parquet",
            "artifacts/run_ledger.jsonl",
            "_metadata/stage31_worker_<machine>.json",
            "/tmp/gpu_busy.lock on each worker host",
            "_logs/supervisor_reports/stage31_watchdog.json",
        ],
        "telegram_rule": "Use Telegram as a human-visible event mirror. Do not use Telegram text alone to claim or start work; use queue/ledger/locks first, then consult recent Telegram-mirrored events for duplicate-awareness.",
        "queues": queues,
        "recent_stage31_watchdog_events": read_jsonl_tail(LOG_DIR / "stage31_watchdog_events.jsonl", 10),
        "recent_event_daemon_events": read_jsonl_tail(LOG_DIR / "project3_event_daemon_events.jsonl", 10),
        "recent_telegram_sent_events": event_state_tail(LOG_DIR / "telegram_notify_state.json", 10),
        "recent_telegram_gateway_sessions": session_message_tail(10),
    }
    write_json(OUT_JSON, payload)

    lines = [
        "# Project 3 Stage 3.1 Worker Context Packet",
        "",
        f"Generated: {payload['generated_at']}",
        f"Project root: `{payload['project_root']}`",
        "Active stage: Stage 3.1 Experiment Framework, Stage A screening",
        "",
        "## Worker Rule",
        "",
        "Read the work-plan docs before choosing or validating work. The queue JSON, run ledger, worker metadata, and GPU lock are the authoritative state. Telegram is a concise shared event mirror for humans and cross-agent awareness, not the source of truth.",
        "",
        "## Relevant Docs",
    ]
    lines.extend(f"- `{doc}`" for doc in payload["relevant_docs"])
    lines.extend(["", "## Source Of Truth"])
    lines.extend(f"- `{item}`" for item in payload["source_of_truth"])
    lines.extend(["", "## Queue Snapshot"])
    for item in queues:
        active = ", ".join(str(row.get("run_id")) for row in item.get("active", []) if row.get("run_id")) or "-"
        lines.append(f"- `{item['machine']}` counts={item.get('counts')} active={active} pending_sample={item.get('pending_sample', [])}")
    lines.extend(["", "## Last 10 Watchdog Events"])
    lines.extend(f"- `{format_event(event)}`" for event in payload["recent_stage31_watchdog_events"] or [{"status": "none"}])
    lines.extend(["", "## Last 10 Telegram-Mirrored Events"])
    lines.extend(f"- `{format_event(event)}`" for event in payload["recent_telegram_sent_events"] or [{"status": "none"}])
    lines.extend(
        [
            "",
            "## Duplicate Prevention",
            "",
            "Before starting work, reconcile the queue, inspect active worker/seed_sweep processes, inspect `/tmp/gpu_busy.lock`, and check the last events above. If another agent already started or finished the same run_id, do not duplicate it; reconcile or escalate.",
            "",
            "If the model is uncertain after reading the work-plan task and deliverables, write a Tier 4/Codex escalation instead of guessing.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
