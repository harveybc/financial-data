"""Flow-v3 acceptance: explicit availability and retained byte identity."""

import hashlib
import os
from pathlib import Path

import pytest

from app.config import DEFAULT_VALUES
from app.main import assemble
from inventory_plugins.fs_inventory import Plugin

TOKEN = "test-lake-token"
RESOURCE = "market_data/a.csv"
CONTRACT = {
    "event_time_column": "event_time",
    "available_time_column": "available_at",
    "timezone": "NAIVE_WALL_CLOCK",
    "time_unit": None,
    "frequency": "1d",
}
BODY = (
    "event_time,available_at,value\n"
    "2024-12-29,2024-12-30,1\n"
    "2024-12-30,2025-01-02,2\n"
)


def _inventory(tmp_path, **overrides):
    root = tmp_path / "root"
    source = root / RESOURCE
    source.parent.mkdir(parents=True)
    source.write_text(BODY)
    plugin = Plugin()
    plugin.set_params(
        root_path=str(root), include_globs=["market_data/**/*.csv"],
        holdout_start="2025-01-01", cuts_dir=str(tmp_path / "cuts"),
        spool_dir=str(tmp_path / "spool"), resource_contracts={RESOURCE: CONTRACT},
        **overrides,
    )
    return plugin, source


def _client(tmp_path, *, contracts=True):
    root = tmp_path / "root"
    source = root / RESOURCE
    source.parent.mkdir(parents=True)
    source.write_text(BODY)
    config = dict(DEFAULT_VALUES)
    config.update({
        "root_path": str(root), "include_globs": ["market_data/**/*.csv"],
        "holdout_start": "2025-01-01", "lake_service_token": TOKEN,
        "cuts_dir": str(tmp_path / "cuts"), "spool_dir": str(tmp_path / "spool"),
        "resource_contracts": {RESOURCE: CONTRACT} if contracts else {},
    })
    plugins = assemble(config)
    app = plugins["web"].create_app({"config": config, "plugins": plugins})
    app.config["TESTING"] = True
    return app.test_client()


def _headers():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_v2_refuses_resource_without_availability_contract(tmp_path):
    response = _client(tmp_path, contracts=False).get(
        "/api/v2/download", query_string={"resource": RESOURCE}, headers=_headers()
    )
    assert response.status_code == 422
    assert response.get_json() == {"error": "resource availability contract required"}


def test_v2_cuts_on_available_time_not_event_time(tmp_path):
    response = _client(tmp_path).get(
        "/api/v2/download",
        query_string={"resource": RESOURCE, "from": "2024-12-30", "to": "2024-12-31"},
        headers=_headers(),
    )
    assert response.status_code == 200
    assert response.data == (
        "event_time,available_at,value\n2024-12-29,2024-12-30,1\n"
    ).encode()
    assert response.headers["X-Time-Column"] == "available_at"
    assert response.headers["X-Availability-Contract-SHA256"]
    assert response.headers["X-Content-SHA256"] == hashlib.sha256(response.data).hexdigest()


def test_governed_download_retains_verified_inode(tmp_path):
    inventory, source = _inventory(tmp_path, holdout_start=None)
    info = inventory.governed_download(RESOURCE)
    replacement = source.with_suffix(".replacement")
    replacement.write_bytes(b"x" * source.stat().st_size)
    os.replace(replacement, source)
    try:
        assert info["handle"].read() == BODY.encode()
    finally:
        info["handle"].close()


def test_same_size_same_mtime_rewrite_is_rehashed(tmp_path):
    inventory, source = _inventory(tmp_path, holdout_start=None)
    first, _ = inventory.sha256(source)
    stamp = source.stat()
    changed = BODY.replace(",1\n", ",9\n").encode()
    assert len(changed) == source.stat().st_size
    source.write_bytes(changed)
    os.utime(source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    second, _ = inventory.sha256(source)
    assert second == hashlib.sha256(changed).hexdigest()
    assert second != first


def test_cut_publication_never_overwrites_different_bytes(tmp_path):
    target = tmp_path / "cut.csv"
    first = tmp_path / "first.part"
    second = tmp_path / "second.part"
    first.write_bytes(b"first")
    second.write_bytes(b"other")
    Plugin._commit(first, target)
    with pytest.raises(RuntimeError, match="cut identity conflict"):
        Plugin._commit(second, target)
    assert target.read_bytes() == b"first"
