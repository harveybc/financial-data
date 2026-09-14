"""Governed v2 downloads must survive the real threaded server.

pandas 3.0.3 with pyarrow 25 segfaults in string_arrow._from_sequence on the
second read_csv issued from a werkzeug worker thread after a streamed delivery
(observed 2026-09-13 on the second `/api/v2/download`). The Flask test client
never shows it because it runs requests in the calling thread, so this test
starts the real server in a subprocess and drives it over HTTP. With pyarrow
string storage the process dies on the second request; with
`inventory_plugins.fs_inventory` pinning python storage it answers.
"""

import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

LAKE = Path(__file__).resolve().parents[1]
TOKEN = "threaded-test-token"
CONTRACT = {
    "event_time_column": "DATE_TIME",
    "available_time_column": "DATE_TIME",
    "timezone": "NAIVE_WALL_CLOCK",
    "time_unit": None,
    "frequency": "4h",
}


def _port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_repeated_v2_downloads_in_worker_threads_do_not_kill_the_server(tmp_path):
    root = tmp_path / "root" / "features"
    root.mkdir(parents=True)
    rows = ["DATE_TIME,typical_price"]
    rows += [f"2013-01-{d:02d} {h:02d}:00:00,{d + h / 100:.4f}" for d in range(1, 29) for h in (0, 4, 8, 12, 16, 20)]
    for name in ("a.csv", "b.csv"):
        (root / name).write_text("\n".join(rows) + "\n", encoding="ascii")
    port = _port()
    config = {
        "pipeline_plugin": "default_pipeline", "web_plugin": "default_web",
        "inventory_plugin": "fs_inventory", "web_host": "127.0.0.1", "web_port": port,
        "root_path": str(tmp_path / "root"), "include_globs": ["features/**/*.csv"],
        "holdout_start": "2025-01-01",
        "resource_contracts": {"features/a.csv": CONTRACT, "features/b.csv": CONTRACT},
        "spool_dir": str(tmp_path / "spool"), "cuts_dir": str(tmp_path / "cuts"),
    }
    config_path = tmp_path / "lake.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    log = open(tmp_path / "server.log", "wb")
    server = subprocess.Popen(
        [sys.executable, "-X", "faulthandler", "app/main.py", "--load_config", str(config_path)],
        cwd=LAKE, env=dict(os.environ, PYTHONPATH=str(LAKE), DATA_GOV_LAKE_TOKEN=TOKEN),
        stdout=log, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    expected = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in ("a.csv", "b.csv")}
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            assert server.poll() is None, "server exited during start-up"
            try:
                urllib.request.urlopen(base + "/healthz", timeout=1)
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        requests = [
            ("features/a.csv", None), ("features/b.csv", None),
            ("features/a.csv", ("2013-01-10", "2013-01-20")), ("features/a.csv", None),
        ]
        for resource, cut in requests:
            query = f"resource={resource}" + (f"&from={cut[0]}&to={cut[1]}" if cut else "")
            request = urllib.request.Request(
                base + "/api/v2/download?" + query, headers={"Authorization": f"Bearer {TOKEN}"}
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status, headers, body = response.status, dict(response.headers), response.read()
            except urllib.error.HTTPError as exc:
                raise AssertionError(f"http {exc.code} on {query}: {exc.read()[:200]!r}")
            except (OSError, urllib.error.URLError) as exc:
                raise AssertionError(f"server died on {query}: {exc}; exit={server.poll()}")
            assert status == 200, query
            assert hashlib.sha256(body).hexdigest() == headers["X-Content-SHA256"]
            if cut is None:
                assert headers["X-Content-SHA256"] == expected[Path(resource).name]
            assert server.poll() is None, f"server exited after {query}"
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
        log.close()
    text = (tmp_path / "server.log").read_text(encoding="utf-8", errors="replace")
    assert "Fatal Python error" not in text, text[-2000:]
