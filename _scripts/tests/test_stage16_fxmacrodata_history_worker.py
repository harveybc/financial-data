"""stage16 FXMacroData history worker: plan, TEST boundary, dry run without key, key never stored, throttle,
consensus vintage labels, bounded retries. No network: the fetcher is injected."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "workers"))
import stage16_fxmacrodata_history_worker as W  # noqa: E402


def args(tmp, *extra):
    return W.parser().parse_args(["--out", str(tmp), *extra])


def test_plan_and_test_boundary():
    reqs = W.plan(["usd", "eur"], "2019-12-01", "2025-01-01", True)
    eps = [r["endpoint"] for r in reqs]
    assert "calendar/usd" in eps and "predictions/usd/non_farm_payrolls" in eps and "announcements/eur/inflation" in eps
    with pytest.raises(W.Refusal, match="TEST_BOUNDARY"):
        W.plan(["usd"], "2024-01-01", "2025-06-01", True)


def test_dry_run_needs_no_key_and_no_network(tmp_path, monkeypatch):
    monkeypatch.delenv("FXMACRODATA_API_KEY", raising=False)
    s = W.run(args(tmp_path, "--dry-run"), fetch=lambda *a: (_ for _ in ()).throw(AssertionError("network")))
    assert s["dry_run"] and s["planned_requests"] > 50
    assert json.loads((tmp_path / "PLAN.json").read_text())["requests"][0]["endpoint"] == "calendar/usd"


def test_refuses_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv("FXMACRODATA_API_KEY", raising=False)
    with pytest.raises(W.Refusal, match="NO_KEY_IN_ENVIRONMENT"):
        W.run(args(tmp_path, "--probe"))


class FakeClock:
    def __init__(self):
        self.t, self.slept = 0.0, []

    def clock(self):
        return self.t

    def sleep(self, d):
        self.slept.append(d)
        self.t += d


def test_key_never_stored_throttle_and_labels(tmp_path, monkeypatch):
    secret = "SECRET-KEY-123"
    monkeypatch.setenv("FXMACRODATA_API_KEY", secret)
    fc = FakeClock()
    th = W.Throttle(1.05, fc.clock, fc.sleep)
    calls = []

    def fetch(endpoint, params, key):
        assert key == secret
        calls.append(endpoint)
        if endpoint.startswith("predictions/"):
            data = [{"announcement_datetime": 1000, "prediction_datetime": 900},      # pre-release
                    {"announcement_datetime": 1000, "prediction_datetime": 1100},     # after release
                    {"announcement_datetime": 1000}]                                  # unknown
            return 200, json.dumps({"data": data}).encode()
        if endpoint.endswith("inflation"):
            return 503, f"upstream error api_key={key}".encode()
        return 200, json.dumps({"data": [{"val": 1}]}).encode()

    s = W.run(args(tmp_path, "--probe"), fetch=fetch, throttle=th)
    raw = (tmp_path / "RAW.jsonl").read_text()
    assert secret not in raw and secret not in (tmp_path / "SUMMARY.json").read_text()
    # probe = USD NFP + CPI and EUR CPI, each announcements + predictions = 6 requests; 3 prediction payloads
    assert s["planned_requests"] == 6
    assert s["consensus_labels"] == {"PRE_RELEASE": 3, "CONSENSUS_VINTAGE_AFTER_RELEASE": 3, "CONSENSUS_VINTAGE_UNKNOWN": 3}
    assert s["failed"] == 2 and s["ok"] == 4                        # the two CPI announcement calls fail after one retry
    assert calls.count("announcements/usd/inflation") == 2           # exactly one retry
    assert all(d > 0 for d in fc.slept) and 30 in fc.slept           # throttled and backed off
