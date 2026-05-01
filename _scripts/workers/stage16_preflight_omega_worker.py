from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
SCAN_ROOTS = ("market_data", "macro_economic", "alternative_data", "reference_data", "economic_calendar")
DATA_SUFFIXES = {".parquet", ".csv", ".json", ".jsonl", ".zip"}
DOC_NAMES = ("README.md", "data_dictionary.md", "provenance.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def log(message: str) -> None:
    path = ROOT / "_logs" / "omega" / "stage16_preflight_omega_worker.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def notify(event: str, title: str, message: str) -> None:
    script = ROOT / "_scripts" / "telegram_notify.py"
    if not script.exists():
        return
    try:
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--event",
                f"stage16:omega:{event}",
                "--title",
                title,
                "--message",
                message,
                "--min-interval-minutes",
                "30",
            ],
            cwd=ROOT,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except Exception as exc:
        log(f"telegram notify skipped event={event} error={type(exc).__name__}")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def file_inventory() -> dict[str, Any]:
    by_root: dict[str, Any] = {}
    data_dirs: set[Path] = set()
    total_files = 0
    total_bytes = 0
    suffixes_total: Counter[str] = Counter()

    for name in SCAN_ROOTS:
        root = ROOT / name
        suffixes: Counter[str] = Counter()
        files = 0
        bytes_ = 0
        if root.exists():
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                files += 1
                total_files += 1
                suffix = path.suffix.lower() or "<none>"
                suffixes[suffix] += 1
                suffixes_total[suffix] += 1
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                bytes_ += size
                total_bytes += size
                if path.suffix.lower() in DATA_SUFFIXES and path.name not in DOC_NAMES:
                    data_dirs.add(path.parent)
        by_root[name] = {
            "exists": root.exists(),
            "files": files,
            "bytes": bytes_,
            "suffix_counts": dict(sorted(suffixes.items())),
        }

    return {
        "roots": by_root,
        "totals": {
            "files": total_files,
            "bytes": total_bytes,
            "data_directories": len(data_dirs),
            "suffix_counts": dict(sorted(suffixes_total.items())),
        },
        "data_directories": sorted(rel(path) for path in data_dirs),
    }


def documentation_audit(data_dirs: list[str]) -> dict[str, Any]:
    missing: list[dict[str, Any]] = []
    complete = 0
    for raw in data_dirs:
        folder = ROOT / raw
        missing_docs = [name for name in DOC_NAMES if not (folder / name).exists()]
        if missing_docs:
            missing.append({"path": raw, "missing": missing_docs})
        else:
            complete += 1
    return {
        "total_data_directories": len(data_dirs),
        "complete_data_directories": complete,
        "missing_doc_directories": len(missing),
        "missing_examples": missing[:100],
    }


def acquisition_summary() -> dict[str, Any]:
    path = ROOT / "_metadata" / "acquisition_log.csv"
    if not path.exists():
        return {"exists": False, "rows": 0}
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    def normalized_status(row: dict[str, str]) -> str:
        value = (row.get("status") or "").strip()
        lower = value.lower()
        if lower in {"ok", "success", "done", "failed", "error", "skipped", "partial"}:
            return lower
        if "/" in value or value.endswith((".parquet", ".csv", ".json", ".zip")):
            return "schema_shifted_or_malformed"
        return value or "<missing>"

    statuses = Counter(normalized_status(row) for row in rows)
    sources = Counter((row.get("source") or "<missing>").strip() for row in rows)
    return {
        "exists": True,
        "rows": len(rows),
        "status_counts": dict(statuses.most_common()),
        "top_sources": dict(sources.most_common(40)),
        "recent_rows": rows[-20:],
    }


def validation_payloads() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for machine in ("dragon", "gamma"):
        path = ROOT / "_metadata" / f"stage16_preflight_validation_{machine}.json"
        if path.exists():
            payload = read_json(path, {})
            out[machine] = {
                "exists": True,
                "generated_at": payload.get("generated_at"),
                "summary": payload.get("summary", {}),
            }
        else:
            out[machine] = {"exists": False}
    return out


def quality_payloads() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for machine in ("dragon", "gamma"):
        path = ROOT / "_metadata" / f"stage16_quality_validation_{machine}.json"
        if path.exists():
            payload = read_json(path, {})
            out[machine] = {
                "exists": True,
                "generated_at": payload.get("generated_at"),
                "summary": payload.get("summary", {}),
            }
        else:
            out[machine] = {"exists": False}
    return out


def gamma_warning_classification() -> dict[str, Any]:
    return read_json(ROOT / "_metadata" / "stage16_gamma_quality_warning_classification.json", {"status": "pending"})


def known_stage13_gaps() -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    validation = read_json(ROOT / "_metadata" / "STAGE_1_3_DELIVERABLE_VALIDATION.json", {})
    for item in validation.get("tasks", []):
        status = item.get("status")
        if status in {"partial", "failed"}:
            gaps.append(
                {
                    "source": f"{item.get('task_id', 'unknown')} {item.get('title', '')}".strip(),
                    "status": str(status),
                    "evidence": str(item.get("evidence", ""))[:300],
                    "next_action": str(item.get("next_action", ""))[:300],
                }
            )
    return gaps


def update_escalation_queue(gaps: list[dict[str, str]]) -> None:
    queue_path = ROOT / "_logs" / "supervisor_reports" / "escalation_queue.json"
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue = read_json(queue_path, {"queue": []})
    existing_ids = {item.get("id") for item in queue.get("queue", [])}
    if "stage14-subscription-decision-001" not in existing_ids:
        queue.setdefault("queue", []).append(
            {
                "id": "stage14-subscription-decision-001",
                "created_at": utc_now(),
                "source_machine": "omega",
                "source_tier": "tier2_orchestrator",
                "category": "plan_decision",
                "severity": "medium",
                "summary": "Decide whether paid providers are needed for Stage 1.4/1.5 gaps after free acquisition.",
                "evidence_path": "STAGE_1.6_PREFLIGHT.md",
                "files_touched_estimate": 0,
                "assigned_tier": "tier4_human",
                "status": "open",
                "tier3_attempts": 0,
                "tier3_last_confidence": None,
                "tier3_unverified_assumptions": [],
                "tier4_handoff_path": "_logs/supervisor_reports/tier4_handoffs/stage14_subscription_decision.md",
                "resolution": None,
                "resolution_commit": None,
            }
        )
    queue_path.write_text(json.dumps(queue, indent=2) + "\n", encoding="utf-8")

    handoff = ROOT / "_logs" / "supervisor_reports" / "tier4_handoffs" / "stage14_subscription_decision.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Stage 1.4 Subscription Decision Handoff",
        "",
        f"Generated: {utc_now()}",
        "",
        "Stage 1.3 free acquisition is complete. Stage 1.6 preflight can continue, but formal Phase 1 completion waits on whether Stage 1.4/1.5 paid sources are worth adding.",
        "",
        "## Current Non-Free Or Partial Gaps",
        "",
    ]
    if not gaps:
        lines.append("- No Stage 1.3 partial gaps detected.")
    for gap in gaps:
        lines.append(f"- {gap['source']}: {gap['status']}. Evidence: {gap['evidence']} Next: {gap['next_action']}")
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- High priority if the user wants richer macro surprise data: Trading Economics or FXStreet credentials for scheduled events, consensus, and surprise fields.",
            "- High priority if the user wants richer on-chain features: advanced on-chain provider such as Glassnode/CryptoQuant-style metrics, depending on final coverage needs.",
            "- Lower priority: Etherscan Pro only if Ethereum historical API fields remain uniquely useful after CoinMetrics and advanced on-chain coverage are evaluated.",
            "",
            "This is a Tier 4 human decision. Tier 3 must not guess subscription value or sign up for services.",
        ]
    )
    handoff.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_inventory_md(
    inventory: dict[str, Any],
    validation: dict[str, Any],
    quality: dict[str, Any],
    gaps: list[dict[str, str]],
) -> None:
    path = ROOT / "INVENTORY.md"
    lines = [
        "# Financial Data Lake - Master Inventory",
        "",
        f"Generated: {utc_now()}",
        "",
        "**Status:** Stage 1.6 preflight inventory. Formal Phase 1 completion waits for Stage 1.4/1.5 subscription decisions.",
        "",
        "## Summary",
        "",
        f"- Total documented data directories: {inventory['totals']['data_directories']}",
        f"- Total files across data roots: {inventory['totals']['files']}",
        f"- Total size: {inventory['totals']['bytes'] / 1024 / 1024 / 1024:.2f} GB",
        f"- Suffix counts: {json.dumps(inventory['totals']['suffix_counts'], sort_keys=True)}",
        "",
        "## Roots",
        "",
        "| Root | Exists | Files | Size GB |",
        "| --- | --- | ---: | ---: |",
    ]
    for name, info in inventory["roots"].items():
        lines.append(f"| {name} | {info['exists']} | {info['files']} | {info['bytes'] / 1024 / 1024 / 1024:.2f} |")
    lines.extend(["", "## Validation Preflight", ""])
    for machine, payload in validation.items():
        if not payload.get("exists"):
            lines.append(f"- {machine}: pending or not synced yet")
            continue
        summary = payload.get("summary", {})
        lines.append(
            f"- {machine}: files_profiled={summary.get('files_profiled', 0)} warnings={summary.get('files_with_warnings', 0)} roots={','.join(summary.get('roots', []))}"
        )
    lines.extend(["", "## Quality Validation", ""])
    for machine, payload in quality.items():
        if not payload.get("exists"):
            lines.append(f"- {machine}: pending or not synced yet")
            continue
        summary = payload.get("summary", {})
        lines.append(
            f"- {machine}: files_checked={summary.get('files_checked', 0)} warnings={summary.get('files_with_warnings', 0)} roots={','.join(summary.get('roots', []))}"
        )
    classification = gamma_warning_classification()
    if classification.get("status") == "classified":
        summary = classification.get("summary", {})
        lines.append(
            f"- gamma warning classification: expected_panel={summary.get('expected_panel_data_files', 0)} fixed_exact_duplicate_files={summary.get('fixed_exact_duplicate_files', 0)} remaining_blockers={summary.get('remaining_blockers', 0)}"
        )
    lines.extend(["", "## Known Gaps Pending Stage 1.4/1.5", ""])
    if not gaps:
        lines.append("- No Stage 1.3 partial gaps detected.")
    for gap in gaps:
        lines.append(f"- {gap['source']}: {gap['status']} - {gap['next_action'] or gap['evidence']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_preflight_report(payload: dict[str, Any]) -> None:
    path = ROOT / "STAGE_1.6_PREFLIGHT.md"
    lines = [
        "# Stage 1.6 Preflight - Validation and Documentation Audit",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "**Status:** IN PROGRESS / PREFLIGHT ONLY.",
        "",
        "Formal Stage 1.6 requires Stage 1.4 and Stage 1.5 completion. This preflight keeps idle machines productive by auditing the Stage 1.3 lake now.",
        "",
        "## Documentation Audit",
        "",
        f"- Data directories checked: {payload['documentation']['total_data_directories']}",
        f"- Complete directories: {payload['documentation']['complete_data_directories']}",
        f"- Missing-doc directories: {payload['documentation']['missing_doc_directories']}",
        "",
        "## Validation Workers",
        "",
    ]
    for machine, info in payload["validation"].items():
        if not info.get("exists"):
            lines.append(f"- {machine}: pending or not synced yet")
            continue
        summary = info.get("summary", {})
        lines.append(
            f"- {machine}: {summary.get('files_profiled', 0)} files profiled; {summary.get('files_with_warnings', 0)} files with warnings"
        )
    lines.extend(["", "## Quality Workers", ""])
    for machine, info in payload["quality"].items():
        if not info.get("exists"):
            lines.append(f"- {machine}: pending or not synced yet")
            continue
        summary = info.get("summary", {})
        lines.append(
            f"- {machine}: {summary.get('files_checked', 0)} files checked; {summary.get('files_with_warnings', 0)} files with warnings"
        )
    classification = payload.get("gamma_warning_classification", {})
    if classification.get("status") == "classified":
        summary = classification.get("summary", {})
        lines.extend(
            [
                "",
                "## Gamma Warning Classification",
                "",
                f"- Expected panel-data warnings: {summary.get('expected_panel_data_files', 0)} files",
                f"- Exact duplicate files fixed: {summary.get('fixed_exact_duplicate_files', 0)} files",
                f"- Remaining blockers: {summary.get('remaining_blockers', 0)}",
                "- Detail: `_logs/supervisor_reports/stage16_gamma_quality_warning_classification.md`",
            ]
        )
    lines.extend(["", "## Acquisition Log", ""])
    acq = payload["acquisition_log"]
    lines.append(f"- Rows: {acq.get('rows', 0)}")
    lines.append(f"- Status counts: {json.dumps(acq.get('status_counts', {}), sort_keys=True)}")
    lines.extend(["", "## Stage 1.4/1.5 Decision Gaps", ""])
    if not payload["known_gaps"]:
        lines.append("- No Stage 1.3 partial gaps detected.")
    for gap in payload["known_gaps"]:
        lines.append(f"- {gap['source']}: {gap['status']}. {gap['next_action'] or gap['evidence']}")
    lines.extend(
        [
            "",
            "## Next Autonomous Work",
            "",
            "- Preserve Gamma warning classification and improve the generic quality worker's panel-key logic later.",
            "- Keep Tier 2 cron monitoring sync/status and dispatch only evidence-backed follow-up checks.",
            "- Keep Telegram to concise start/finish/blocker/anomaly events with deliverable paths.",
            "- Route subscription decisions to Tier 4/Codex; do not let local agents guess paid-provider value.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    log("START stage16 omega preflight worker")
    notify(
        "start",
        "Project 3 Omega Stage 1.6 preflight started",
        "machine: omega\nwork_plan_stage: Stage 1.6 preflight\nstatus: started\ntask: documentation audit, inventory, gap handoff aggregation",
    )
    inventory = file_inventory()
    docs = documentation_audit(inventory["data_directories"])
    acq = acquisition_summary()
    validation = validation_payloads()
    quality = quality_payloads()
    gamma_classification = gamma_warning_classification()
    gaps = known_stage13_gaps()
    update_escalation_queue(gaps)

    payload = {
        "generated_at": utc_now(),
        "stage": "Stage 1.6 preflight",
        "formal_stage_status": "preflight_only_waiting_for_stage_1_4_and_1_5",
        "inventory": inventory,
        "documentation": docs,
        "acquisition_log": acq,
        "validation": validation,
        "quality": quality,
        "gamma_warning_classification": gamma_classification,
        "known_gaps": gaps,
    }
    out = ROOT / "_metadata" / "stage16_preflight_omega.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (ROOT / "_metadata" / "audit_documentation_preflight.json").write_text(
        json.dumps(docs, indent=2) + "\n", encoding="utf-8"
    )
    write_inventory_md(inventory, validation, quality, gaps)
    write_preflight_report(payload)
    notify(
        "finish",
        "Project 3 Omega Stage 1.6 preflight finished",
        "\n".join(
            [
                "machine: omega",
                "work_plan_stage: Stage 1.6 preflight",
                "status: finished",
                "deliverable_path: STAGE_1.6_PREFLIGHT.md; INVENTORY.md; _metadata/stage16_preflight_omega.json",
                f"validation_evidence: data_dirs={docs['total_data_directories']} missing_doc_dirs={docs['missing_doc_directories']} gaps={len(gaps)}",
                "recommended_next_action: keep Dragon/Gamma validation scans running and resolve Stage 1.4 subscription decision",
            ]
        ),
    )
    log(
        "DONE stage16 omega preflight worker "
        f"data_dirs={docs['total_data_directories']} missing_doc_dirs={docs['missing_doc_directories']} gaps={len(gaps)}"
    )


if __name__ == "__main__":
    main()
