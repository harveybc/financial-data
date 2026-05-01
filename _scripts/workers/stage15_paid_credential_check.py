from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stage13_common import ROOT, load_env


OUT = ROOT / "_logs" / "supervisor_reports" / "stage15_paid_credential_check.json"
MD = ROOT / "_logs" / "supervisor_reports" / "stage15_paid_credential_check.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_json(url: str, headers: dict[str, str] | None = None, timeout: int = 25) -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def check_fxmacrodata() -> dict[str, Any]:
    key = os.environ.get("FXMACRODATA_API_KEY", "").strip()
    if not key:
        return {"provider": "FXMacroData", "status": "missing_key", "next_action": "Add FXMACRODATA_API_KEY to _metadata/.env."}
    url = "https://fxmacrodata.com/api/v1/announcements/eur/inflation?" + urllib.parse.urlencode({"api_key": key})
    try:
        status, payload = get_json(url)
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        sample = rows[-1] if rows and isinstance(rows[-1], dict) else {}
        return {
            "provider": "FXMacroData",
            "status": "validated" if status == 200 and rows else "unexpected_empty",
            "http_status": status,
            "row_count": len(rows),
            "sample_columns": sorted(sample.keys())[:20],
            "next_action": fxmacrodata_next_action(rows),
        }
    except Exception as exc:
        return {
            "provider": "FXMacroData",
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:220],
            "next_action": "Verify key in FXMacroData dashboard.",
        }


def fxmacrodata_next_action(rows: list[Any]) -> str:
    summary_path = ROOT / "_metadata" / "stage15_fxmacrodata_acquisition.json"
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception:
        summary = {}
    if summary.get("status") == "ok" and summary.get("calendar_rows", 0) and summary.get("announcement_rows", 0):
        return "Stage 1.5 FXMacroData acquisition complete; supervisor should use _logs/supervisor_reports/stage15_fxmacrodata_acquisition.md as deliverable evidence."
    return "Run Stage 1.5 FXMacroData acquisition worker." if rows else "Inspect provider account coverage."


def check_cryptoquant() -> dict[str, Any]:
    key = os.environ.get("CRYPTOQUANT_API_KEY", "").strip()
    if not key:
        return {"provider": "CryptoQuant", "status": "missing_key", "next_action": "Add CRYPTOQUANT_API_KEY to _metadata/.env."}
    checks = []
    tests = [
        {
            "method": "bearer",
            "url": "https://api.cryptoquant.com/v1/discovery/endpoints?format=json",
            "headers": {"Authorization": f"Bearer {key}"},
        },
        {
            "method": "api_key_query",
            "url": "https://api.cryptoquant.com/v1/discovery/endpoints?" + urllib.parse.urlencode({"api_key": key, "format": "json"}),
            "headers": {},
        },
    ]
    for test in tests:
        try:
            status, payload = get_json(test["url"], headers=test["headers"])
            rows = payload.get("result", {}).get("data", []) if isinstance(payload, dict) else []
            checks.append({"method": test["method"], "ok": status == 200 and bool(rows), "http_status": status, "row_count": len(rows)})
        except Exception as exc:
            checks.append({"method": test["method"], "ok": False, "error_type": type(exc).__name__, "error": str(exc)[:180]})
    ok = any(item.get("ok") for item in checks)
    return {
        "provider": "CryptoQuant",
        "status": "validated" if ok else "blocked_403_or_inactive",
        "checks": checks,
        "next_action": "Run Stage 1.5 CryptoQuant acquisition worker." if ok else "Open CryptoQuant profile API tab and confirm this exact token is active for Professional API access; if a newly generated access token exists, replace CRYPTOQUANT_API_KEY in _metadata/.env.",
    }


def main() -> None:
    load_env()
    report = {
        "generated_at": utc_now(),
        "stage": "Stage 1.5 paid provider credential validation",
        "checks": [check_fxmacrodata(), check_cryptoquant()],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Stage 1.5 Paid Credential Check",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "| Provider | Status | Next Action |",
        "| --- | --- | --- |",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['provider']} | {check['status']} | {check.get('next_action', '')} |")
    MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": [str(OUT.relative_to(ROOT)), str(MD.relative_to(ROOT))], "statuses": {c["provider"]: c["status"] for c in report["checks"]}}, sort_keys=True))


if __name__ == "__main__":
    main()
