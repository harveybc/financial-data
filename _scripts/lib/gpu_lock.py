from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path


LOCKFILE = Path("/tmp/gpu_busy.lock")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def acquire_gpu_lock(command: str, expected_duration_minutes: int, stage: str) -> None:
    if LOCKFILE.exists():
        try:
            current = json.loads(LOCKFILE.read_text(encoding="utf-8"))
        except Exception:
            current = {"raw": LOCKFILE.read_text(encoding="utf-8", errors="ignore")}
        raise RuntimeError(f"GPU lock already present at {LOCKFILE}: {current}")
    payload = {
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "stage": stage,
        "command": command,
        "started_at": _now(),
        "expected_duration_minutes": expected_duration_minutes,
    }
    LOCKFILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def release_gpu_lock() -> None:
    if not LOCKFILE.exists():
        return
    try:
        current = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    except Exception:
        current = {}
    owner_pid = current.get("pid")
    if owner_pid not in (None, os.getpid()):
        raise RuntimeError(f"Refusing to release GPU lock owned by pid={owner_pid}; current pid={os.getpid()}")
    LOCKFILE.unlink()
