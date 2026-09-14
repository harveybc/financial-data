"""N2: the availability scope of a contract is executed on /api/v2/download."""

import hashlib
import json

import pytest

from app.config import DEFAULT_VALUES
from app.main import assemble
from inventory_plugins.fs_inventory import Plugin, UnsupportedError, availability_scope, scope_of

TOKEN = "test-lake-token"
RESOURCE = "market_data/bars.csv"
BASE = {"event_time_column": "DATE_TIME", "available_time_column": "DATE_TIME",
        "timezone": "NAIVE_WALL_CLOCK", "time_unit": None, "frequency": "4h"}
OFFLINE = {"label": "WINDOW_END", "completion_lag_max": "1h",
           "timezone_evidence": "UNKNOWN", "use_class": "OFFLINE_DAY_GRANULAR"}
LINES = [f"2013-01-{d:02d} {h:02d}:00:00,{d + h / 100:.2f}" for d in (2, 3) for h in (0, 4, 8, 12, 16, 20)]
LINES.insert(12, "2013-01-03 23:30:00,9.99")  # completes at 00:30 of day 4 under a 1h bound


def _root(tmp_path):
    root = tmp_path / "root"
    (root / "market_data").mkdir(parents=True)
    (root / RESOURCE).write_text("DATE_TIME,typical_price\n" + "\n".join(LINES) + "\n", encoding="ascii")
    return root


def _plugin(tmp_path, contract):
    plugin = Plugin()
    plugin.set_params(root_path=str(_root(tmp_path)), include_globs=["market_data/**/*.csv"], holdout_start="2025-01-01",
                      cuts_dir=str(tmp_path / "cuts"), spool_dir=str(tmp_path / "spool"),
                      resource_contracts={RESOURCE: contract})
    return plugin


def _times(data):
    return [line.split(",")[0] for line in data.decode().splitlines()[1:]]


def test_scope_is_validated_and_published_separately_from_the_digest(tmp_path):
    assert availability_scope(OFFLINE)["completion_lag"].total_seconds() == 3600
    with pytest.raises(UnsupportedError):
        availability_scope({**OFFLINE, "use_class": "LIVE_EQUIVALENT"})
    assert scope_of(BASE)["use_class"] == "UNDECLARED"
    plugin = _plugin(tmp_path, {**BASE, "availability": OFFLINE})
    info = plugin.governed_download(RESOURCE, "2013-01-02", "2013-01-03")
    data = info["handle"].read()
    info["handle"].close()
    assert info["availability"] == OFFLINE
    assert info["availability_contract_sha256"] == hashlib.sha256(json.dumps(
        {**BASE, "availability": OFFLINE}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    times = _times(data)
    assert "2013-01-03 23:30:00" not in times and "2013-01-03 20:00:00" in times and len(times) == 12
    plain = _plugin(tmp_path / "plain", {**BASE, "availability": {**OFFLINE, "completion_lag_max": "0s"}})
    info = plain.governed_download(RESOURCE, "2013-01-02", "2013-01-03")
    assert "2013-01-03 23:30:00" in _times(info["handle"].read())
    info["handle"].close()


def test_v2_download_headers_carry_the_scope(tmp_path):
    config = dict(DEFAULT_VALUES)
    config.update({
        "root_path": str(_root(tmp_path)), "include_globs": ["market_data/**/*.csv"],
        "holdout_start": "2025-01-01", "lake_service_token": TOKEN,
        "cuts_dir": str(tmp_path / "cuts"), "spool_dir": str(tmp_path / "spool"),
        "resource_contracts": {RESOURCE: {**BASE, "availability": OFFLINE}},
    })
    plugins = assemble(config)
    app = plugins["web"].create_app({"config": config, "plugins": plugins})
    app.config["TESTING"] = True
    response = app.test_client().get(
        "/api/v2/download", query_string={"resource": RESOURCE, "from": "2013-01-02", "to": "2013-01-03"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    assert response.status_code == 200
    assert response.headers["X-Availability-Use"] == "OFFLINE_DAY_GRANULAR"
    assert response.headers["X-Availability-Label"] == "WINDOW_END"
    assert response.headers["X-Availability-Completion-Lag-Max"] == "1h"
    assert response.headers["X-Timezone-Evidence"] == "UNKNOWN"
    assert "2013-01-03 23:30:00" not in response.data.decode()
    with pytest.raises(ValueError):
        plugins["inventory"].governed_download(RESOURCE, "2013-01-02T04:00", "2013-01-02T12:00")
