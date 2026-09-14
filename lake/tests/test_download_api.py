import hashlib

from app.config import DEFAULT_VALUES
from app.main import assemble

TOKEN = "test-lake-token"
PRE_HOLDOUT = "ts,v\n2024-12-30,1\n2024-12-31,2\n"
SPANNING = "ts,v\n2024-12-30,1\n2024-12-31 23:59:59,2\n2025-01-01 00:00:00,3\n2025-01-02,4\n"


def _client(tmp_path, files=None, **overrides):
    root = tmp_path / "root" / "market_data"
    root.mkdir(parents=True, exist_ok=True)
    for name, text in (files or {"a.csv": PRE_HOLDOUT}).items():
        (root / name).write_text(text)
    config = dict(DEFAULT_VALUES)
    config.update(
        {
            "root_path": str(tmp_path / "root"),
            "include_globs": ["market_data/**/*.csv"],
            "secret_key": "t",
            "lake_service_token": TOKEN,
            "spool_dir": str(tmp_path / "var" / "spool"),
            "cuts_dir": str(tmp_path / "var" / "cuts"),
        }
    )
    config.update(overrides)
    plugins = assemble(config)
    app = plugins["web"].create_app({"config": config, "plugins": plugins})
    app.config["TESTING"] = True
    return app.test_client()


def _h():
    return {"Authorization": f"Bearer {TOKEN}"}


def _get(client, **query):
    query.setdefault("resource", "market_data/a.csv")
    return client.get("/api/v1/download", query_string=query, headers=_h())


def test_download_requires_token(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/v1/download", query_string={"resource": "market_data/a.csv"}).status_code == 401


def test_download_as_is_headers_and_body_hash(tmp_path):
    client = _client(tmp_path)
    with _get(client) as response:
        body = response.data
        assert response.status_code == 200
        assert body == PRE_HOLDOUT.encode()
        digest = hashlib.sha256(body).hexdigest()
        assert response.headers["X-Content-SHA256"] == digest
        assert response.headers["X-Source-SHA256"] == digest
        assert response.headers["X-Delivery"] == "AS_IS"
        assert response.headers["X-Time-Column"] == "ts"
        assert response.headers["Content-Length"] == str(len(body))
        assert response.headers["Content-Disposition"] == 'attachment; filename="a.csv"'
    source = tmp_path / "root" / "market_data" / "a.csv"
    assert source.exists()  # sources are persistent, never unlinked


def test_download_cut_headers_and_body_hash(tmp_path):
    client = _client(tmp_path, files={"a.csv": SPANNING})
    with _get(client, **{"from": "2024-12-30", "to": "2024-12-31"}) as response:
        body = response.data
        assert response.status_code == 200
        assert body == b"ts,v\n2024-12-30,1\n2024-12-31 23:59:59,2\n"
        assert response.headers["X-Content-SHA256"] == hashlib.sha256(body).hexdigest()
        assert response.headers["X-Source-SHA256"] == hashlib.sha256(SPANNING.encode()).hexdigest()
        assert response.headers["X-Delivery"] == "CUT"
        assert response.headers["X-Time-Column"] == "ts"
        assert response.headers["Content-Length"] == str(len(body))
        assert response.headers["Content-Disposition"] == 'attachment; filename="2024-12-30_2024-12-31.csv"'
    cut = tmp_path / "var" / "cuts" / response.headers["X-Source-SHA256"] / "2024-12-30_2024-12-31.csv"
    assert cut.read_bytes() == body  # cuts are persistent, never unlinked


def test_download_untimed_resource_as_is_with_empty_time_column(tmp_path):
    client = _client(
        tmp_path,
        files={"a.csv": "date,name\n2025-12-25,xmas\n"},
        untimed=["market_data/a.csv"],
    )
    with _get(client) as response:
        assert response.status_code == 200
        assert response.headers["X-Delivery"] == "AS_IS"
        assert response.headers["X-Time-Column"] == ""
        assert response.headers["X-Content-SHA256"] == hashlib.sha256(response.data).hexdigest()


def test_download_spanning_holdout_without_range_is_403(tmp_path):
    client = _client(tmp_path, files={"a.csv": SPANNING})
    response = _get(client)
    assert response.status_code == 403
    assert response.get_json() == {"error": "spans holdout: request a range"}
    reaching = _get(client, **{"from": "2024-12-30", "to": "2025-01-01"})
    assert reaching.status_code == 403
    assert reaching.get_json() == {"error": "holdout"}


def test_download_datetime_to_is_400(tmp_path):
    client = _client(tmp_path)
    response = _get(client, **{"from": "2024-12-30", "to": "2024-12-31T00:00:00"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "invalid from/to"}
    assert _get(client, **{"from": "2024-12-30"}).status_code == 400
    assert _get(client, **{"from": "2024-12-31", "to": "2024-12-30"}).status_code == 400


def test_download_unknown_resource_is_404(tmp_path):
    client = _client(tmp_path)
    response = _get(client, resource="market_data/nope.csv")
    assert response.status_code == 404
    assert response.get_json() == {"error": "unknown resource"}


def test_download_unsupported_csv_is_422(tmp_path):
    client = _client(tmp_path, files={"a.csv": 'ts,note\n2024-12-30,"a\nb"\n2025-01-02,c\n'})
    response = _get(client, **{"from": "2024-12-30", "to": "2024-12-31"})
    assert response.status_code == 422
    assert response.get_json() == {"error": "unsupported csv"}


def test_download_busy_slots_answer_503_retry_after(tmp_path):
    client = _client(tmp_path, max_downloads=0)
    response = _get(client)
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "30"
    assert response.get_json() == {"error": "download slots busy"}


def test_download_slot_is_returned_when_the_response_closes(tmp_path):
    client = _client(tmp_path, max_downloads=1)
    first = _get(client)
    assert first.status_code == 200
    busy = _get(client)
    assert busy.status_code == 503
    first.close()
    with _get(client) as third:
        assert third.status_code == 200
    denied = _get(client, resource="market_data/nope.csv")
    assert denied.status_code == 404  # an error path also returns its slot
    assert _get(client).status_code == 200


def test_read_adopts_day_only_range_and_strict_upper_bound(tmp_path):
    client = _client(tmp_path, files={"a.csv": SPANNING})
    bad = client.get(
        "/api/v1/read",
        query_string={"resource": "market_data/a.csv", "from": "2024-12-30T00:00:00", "to": "2024-12-31"},
        headers=_h(),
    )
    assert bad.status_code == 400
    assert bad.get_json() == {"error": "invalid from/to"}
    good = client.get(
        "/api/v1/read",
        query_string={"resource": "market_data/a.csv", "from": "2024-12-30", "to": "2024-12-31"},
        headers=_h(),
    )
    assert good.status_code == 200
    assert [row["v"] for row in good.get_json()["rows"]] == [1, 2]
