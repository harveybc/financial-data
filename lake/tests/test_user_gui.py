from app.config import DEFAULT_VALUES
from app.main import assemble

TOKEN = "test-lake-token"


def _client(tmp_path):
    (tmp_path / "market_data").mkdir()
    (tmp_path / "market_data" / "a.csv").write_text("ts,v\n2020-01-01,1\n")
    config = dict(DEFAULT_VALUES)
    config.update(
        {
            "root_path": str(tmp_path),
            "include_globs": ["market_data/**/*.csv"],
            "secret_key": "t",
            "lake_service_token": TOKEN,
        }
    )
    plugins = assemble(config)
    app = plugins["web"].create_app({"config": config, "plugins": plugins})
    app.config["TESTING"] = True
    return app.test_client()


def _h():
    return {"Authorization": f"Bearer {TOKEN}"}


def test_gui_lists_inventory(tmp_path):
    client = _client(tmp_path)
    page = client.get("/")
    assert page.status_code == 200
    assert b"market_data/a.csv" in page.data
    assert b"Inventoried files" in page.data


def test_api_requires_token(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/v1/discover").status_code == 401


def test_api_discover_and_read(tmp_path):
    client = _client(tmp_path)
    disc = client.get("/api/v1/discover", headers=_h()).get_json()
    assert disc["resources"][0]["resource_id"] == "market_data/a.csv"
    missing = client.get(
        "/api/v1/read",
        query_string={"resource": "market_data/a.csv"},
        headers=_h(),
    )
    assert missing.status_code == 400
    read = client.get(
        "/api/v1/read",
        query_string={
            "resource": "market_data/a.csv",
            "from": "2020-01-01",
            "to": "2020-12-31",
        },
        headers=_h(),
    )
    assert read.status_code == 200
    assert read.get_json()["sha256"]
    denied = client.get(
        "/api/v1/read",
        query_string={
            "resource": "market_data/a.csv",
            "from": "2025-06-01",
            "to": "2025-06-30",
        },
        headers=_h(),
    )
    assert denied.status_code == 403
