#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
PYTHON = os.environ.get("PROJECT3_PYTHON", "/home/harveybc/anaconda3/envs/tensorflow/bin/python")
SSH_PORT = os.environ.get("PROJECT3_SSH_PORT", "22022")

MACHINES: dict[str, str | None] = {
    "omega": None,
    "dragon": "192.0.2.13",
    "gamma": "192.0.2.15",
}

REQUIRED_TRACE_COLUMNS = {
    "step",
    "reward",
    "equity",
    "step_return",
    "position",
    "price",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)


def shell(cmd: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    return run(["bash", "-lc", cmd], timeout=timeout)


def machine_shell(machine: str, cmd: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    host = MACHINES[machine]
    prefix = (
        "source ~/.bashrc >/dev/null 2>&1 || true; "
        "source /home/harveybc/anaconda3/etc/profile.d/conda.sh >/dev/null 2>&1 || true; "
        "conda activate tensorflow >/dev/null 2>&1 || true; "
        f"cd {shlex.quote(str(ROOT))} || exit 1; "
    )
    full = prefix + cmd
    if host is None:
        return shell(full, timeout=timeout)
    return run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "ConnectTimeout=8",
            "-p",
            SSH_PORT,
            f"harveybc@{host}",
            f"bash -lc {shlex.quote(full)}",
        ],
        timeout=timeout,
    )


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


def active_jobs(machine: str) -> list[dict[str, Any]]:
    queue = read_json(ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    if not isinstance(queue, list):
        return []
    active_statuses = {"training", "running", "registered", "preparing_input"}
    return [job for job in queue if str(job.get("status") or "").lower() in active_statuses]


def queue_counts(machine: str) -> dict[str, int]:
    queue = read_json(ROOT / "experiments" / "stage_a_screening" / "queues" / f"{machine}.json", [])
    if not isinstance(queue, list):
        return {"queue_error": 1}
    return dict(Counter(str(job.get("status") or "pending") for job in queue))


def remote_json_config(machine: str, config_path: str | None) -> dict[str, Any]:
    if not config_path:
        return {"exists": False, "reason": "no_config_path"}
    script = (
        f"{shlex.quote(PYTHON)} - <<'PY'\n"
        "import json\n"
        "from pathlib import Path\n"
        f"p=Path({config_path!r})\n"
        "payload={'exists': p.exists(), 'path': str(p)}\n"
        "if p.exists():\n"
        "    try:\n"
        "        data=json.loads(p.read_text())\n"
        "        payload.update({\n"
        "            'return_trace_file': data.get('return_trace_file'),\n"
        "            'return_trace_dir': data.get('return_trace_dir'),\n"
        "            'pipeline_plugin': data.get('pipeline_plugin'),\n"
        "            'agent_plugin': data.get('agent_plugin'),\n"
        "            'total_timesteps': data.get('total_timesteps'),\n"
        "        })\n"
        "    except Exception as exc:\n"
        "        payload['parse_error']=str(exc)\n"
        "print(json.dumps(payload, sort_keys=True))\n"
        "PY"
    )
    cp = machine_shell(machine, script, timeout=30)
    try:
        return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception:
        return {"exists": False, "path": config_path, "probe_error": cp.stdout.strip()[:1000]}


def process_probe(machine: str, run_id: str) -> dict[str, Any]:
    pattern = shlex.quote(f"stage31_agent_multi_run_worker.py|seed_sweep.py|agent-multi|{run_id}")
    cmd = f"ps -eo pid=,stat=,pcpu=,pmem=,etime=,args= | grep -E {pattern} | grep -v grep || true"
    cp = machine_shell(machine, cmd, timeout=30)
    lines = [line.strip() for line in cp.stdout.splitlines() if line.strip()]
    return {"lines": lines[:20], "count": len(lines), "has_process": bool(lines)}


def gpu_probe(machine: str) -> dict[str, Any]:
    cmd = "nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>/dev/null || true"
    cp = machine_shell(machine, cmd, timeout=30)
    rows = []
    for line in cp.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) == 5:
            rows.append(
                {
                    "index": parts[0],
                    "name": parts[1],
                    "gpu_util_pct": parts[2],
                    "memory_used_mib": parts[3],
                    "memory_total_mib": parts[4],
                }
            )
    return {"gpus": rows, "raw": cp.stdout.strip()}


def trace_inventory(machine: str) -> dict[str, Any]:
    script = (
        f"{shlex.quote(PYTHON)} - <<'PY'\n"
        "import csv, json\n"
        "from pathlib import Path\n"
        f"root=Path('experiments/stage_a_screening/runs') / {machine!r}\n"
        "paths=[]\n"
        "for pattern in ('*return_trace*.csv', 'return_trace.csv'):\n"
        "    paths.extend(root.glob(f'**/{pattern}'))\n"
        "seen=[]\n"
        "for p in sorted(set(paths), key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):\n"
        "    try:\n"
        "        with p.open(newline='') as handle:\n"
        "            reader=csv.reader(handle)\n"
        "            header=next(reader, [])\n"
        "            first=next(reader, None)\n"
        "        seen.append({'path': str(p), 'columns': header, 'has_rows': first is not None, 'mtime': p.stat().st_mtime})\n"
        "    except Exception as exc:\n"
        "        seen.append({'path': str(p), 'error': str(exc)})\n"
        "print(json.dumps({'count': len(seen), 'recent': seen[:10]}, sort_keys=True))\n"
        "PY"
    )
    cp = machine_shell(machine, script, timeout=60)
    try:
        return json.loads(cp.stdout.strip().splitlines()[-1])
    except Exception:
        return {"count": 0, "recent": [], "probe_error": cp.stdout.strip()[:1000]}


def classify_job(job: dict[str, Any], config: dict[str, Any], process: dict[str, Any]) -> str:
    status = str(job.get("status") or "").lower()
    if not config.get("exists"):
        return "ACTIVE_CONFIG_MISSING"
    if not config.get("return_trace_file") and not config.get("return_trace_dir"):
        return "ACTIVE_TRACE_CONTRACT_MISSING"
    if status in {"training", "running"} and process.get("has_process"):
        return "ACTIVE_TRACE_CONTRACT_READY"
    if status in {"training", "running"}:
        return "ACTIVE_STATUS_NO_PROCESS"
    return "ACTIVE_UNKNOWN"


def validate_trace_columns(inventory: dict[str, Any]) -> dict[str, Any]:
    invalid = []
    valid = []
    for item in inventory.get("recent", []):
        columns = set(item.get("columns") or [])
        missing = sorted(REQUIRED_TRACE_COLUMNS - columns)
        if missing or not item.get("has_rows"):
            invalid.append({"path": item.get("path"), "missing_columns": missing, "has_rows": item.get("has_rows")})
        else:
            valid.append(item.get("path"))
    return {"valid_recent": valid, "invalid_recent": invalid}


def build_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3.1 Trace Coverage And Liveness Audit",
        "",
        f"Generated: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
        "| Machine | Queue Counts | Active Classifications | Trace Files | GPU |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for machine in payload["machines"]:
        classifications = Counter(job["classification"] for job in machine["active_jobs"])
        gpu_bits = []
        for gpu in machine["gpu"].get("gpus", []):
            gpu_bits.append(
                f"{gpu['name']} util={gpu['gpu_util_pct']}% mem={gpu['memory_used_mib']}/{gpu['memory_total_mib']} MiB"
            )
        lines.append(
            "| {machine} | `{counts}` | `{classes}` | {trace_count} | {gpu} |".format(
                machine=machine["machine"],
                counts=machine["queue_counts"],
                classes=dict(classifications),
                trace_count=machine["trace_inventory"].get("count", 0),
                gpu="; ".join(gpu_bits) or "-",
            )
        )
    lines.extend(["", "## Active Jobs", ""])
    for machine in payload["machines"]:
        lines.append(f"### {machine['machine']}")
        if not machine["active_jobs"]:
            lines.append("- No active Stage 3.1 training jobs in the mirrored queue.")
            lines.append("")
            continue
        for job in machine["active_jobs"]:
            lines.append(
                "- `{run_id}`: `{classification}`; config_trace=`{trace}`; process_count={process_count}".format(
                    run_id=job["run_id"],
                    classification=job["classification"],
                    trace=job["config"].get("return_trace_file") or job["config"].get("return_trace_dir"),
                    process_count=job["process"].get("count", 0),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "- `ACTIVE_TRACE_CONTRACT_READY` means a current/active job has both a process and a trace destination in config.",
            "- `ACTIVE_TRACE_CONTRACT_MISSING` means the run can finish Stage A, but it will not create return traces for rigorous B3/B4 analysis.",
            "- `ACTIVE_STATUS_NO_PROCESS` means the queue mirror says active but the target machine does not show a matching process.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-json", default=str(ROOT / "_metadata" / "stage31_trace_coverage_audit.json"))
    parser.add_argument("--out-md", default=str(ROOT / "_logs" / "supervisor_reports" / "stage31_trace_coverage_audit.md"))
    args = parser.parse_args()

    machines = []
    for machine in MACHINES:
        active = active_jobs(machine)
        machine_payload: dict[str, Any] = {
            "machine": machine,
            "queue_counts": queue_counts(machine),
            "gpu": gpu_probe(machine),
            "trace_inventory": trace_inventory(machine),
            "active_jobs": [],
        }
        machine_payload["trace_validation"] = validate_trace_columns(machine_payload["trace_inventory"])
        for job in active:
            config = remote_json_config(machine, job.get("config"))
            process = process_probe(machine, str(job.get("run_id") or ""))
            machine_payload["active_jobs"].append(
                {
                    "run_id": job.get("run_id"),
                    "status": job.get("status"),
                    "config_path": job.get("config"),
                    "config": config,
                    "process": process,
                    "classification": classify_job(job, config, process),
                }
            )
        machines.append(machine_payload)

    payload = {"generated_at": utc_now(), "machines": machines}
    write_json(Path(args.out_json), payload)
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text(build_report(payload), encoding="utf-8")
    print(json.dumps({"out_json": args.out_json, "out_md": args.out_md}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
