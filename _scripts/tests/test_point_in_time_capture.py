"""Adversarial battery for the point-in-time store and its collector.

Each test names the specific failure the store exists to prevent. The failures are all the same shape: a record that
says something today which it did not say when it was written, and no reader able to tell. A backtest built on such a
store looks excellent for exactly that reason.

Fixtures are hermetic: a tiny two-release calendar and a tiny actuals table, so nothing here depends on the real
archives and nothing here writes inside the repository.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "_scripts" / "lib"))
sys.path.insert(0, str(REPO / "_scripts" / "workers"))

import point_in_time_store as pit  # noqa: E402
import stage13_point_in_time_capture_worker as capture  # noqa: E402


SCHEDULED = datetime(2026, 3, 4, 13, 30, tzinfo=timezone.utc)


def observation(**overrides):
    base = {"calendar_source": "fxmacrodata_release_calendar", "economy": "USD", "series": "non_farm_payrolls",
            "scheduled_at": SCHEDULED, "received_at": SCHEDULED + timedelta(minutes=7),
            "source": "fxmacrodata_announcements", "source_path": capture.ANNOUNCEMENTS_PATH,
            "source_sha256": "0" * 64, "status": pit.OBSERVED, "value": 151.0, "value_period": "2026-02-28"}
    base.update(overrides)
    return base


@pytest.fixture()
def store(tmp_path):
    return pit.PointInTimeStore(tmp_path / "point_in_time")


# --------------------------------------------------------------
# the five properties the store is for
# --------------------------------------------------------------

def test_a_changed_value_is_a_new_row_and_the_first_row_keeps_its_bytes(store):
    """The failure: a revision written over the original. The original's receipt clock is then the only evidence that
    a decision taken before the revision was taken on a different number -- and it has just been deleted."""
    first, disposition = store.append(observation())
    assert disposition == "STORED" and first["revision_index"] == 0
    path = store._path(first["row_id"])
    before = path.read_bytes()

    second, disposition = store.append(observation(value=143.0, received_at=SCHEDULED + timedelta(days=30)))
    assert disposition == "REVISION"
    assert second["revision_index"] == 1 and second["value_revision_index"] == 1
    assert second["row_id"] != first["row_id"]
    assert first["row_sha256"] in second["supersedes"]

    assert path.read_bytes() == before, "the superseded row was rewritten"
    assert store.find_row(first["row_id"])["value"] == 151.0
    assert len(store.rows()) == 2
    assert store.replay()["revisions"] == 1


def test_a_reader_asking_what_was_known_at_T_never_sees_a_later_row(store):
    """The failure: the revision leaking into a view of the past. It is not a ranking problem -- a row received after T
    must be ABSENT from the answer, because a decision at T could not use what had not arrived."""
    store.append(observation())
    store.append(observation(value=143.0, received_at=SCHEDULED + timedelta(days=30)))

    early = store.known_at(SCHEDULED + timedelta(days=1))
    assert [r["value"] for r in early] == [151.0]
    assert all(r["received_at"] <= (SCHEDULED + timedelta(days=1)).isoformat() for r in early)

    late = store.known_at(SCHEDULED + timedelta(days=60))
    assert [r["value"] for r in late] == [143.0]

    assert store.known_at(SCHEDULED - timedelta(days=1)) == []


def test_the_same_value_read_again_is_not_a_revision(store):
    """The failure: a collector that manufactures a revision every time it runs. The store would then be a log of the
    collector's cadence rather than of the number's history."""
    first, _ = store.append(observation())
    path = store._path(first["row_id"])
    before = path.read_bytes()

    again, disposition = store.append(observation(received_at=SCHEDULED + timedelta(hours=9),
                                                 source_sha256="f" * 64, source_rows_matched=99))
    assert disposition == "DUPLICATE"
    assert again["row_id"] == first["row_id"] and again["received_at"] == first["received_at"]
    assert path.read_bytes() == before
    assert len(store.rows()) == 1 and store.replay()["revisions"] == 0


def test_the_store_refuses_to_rewrite_a_row(store):
    """The failure: different facts placed under a key that already exists. Forging the key is the only way to get
    here, and it is refused by name rather than silently not happening."""
    first, _ = store.append(observation())
    forged = dict(first)
    forged["value"] = 999.0
    forged["observation_sha256"] = pit.digest({"schema": pit.SCHEMA, "observation": {"forged": True}})
    with pytest.raises(pit.PointInTimeRefusal, match="ROW_REWRITE_REFUSED"):
        store.write_row(forged)
    assert store.find_row(first["row_id"])["value"] == 151.0

    unchanged, disposition = store.write_row(dict(first))
    assert disposition == "DUPLICATE" and unchanged["value"] == 151.0


def test_the_collector_records_an_awaited_release_without_inventing_a_value(tmp_path):
    """The failure: a release with no number yet recorded as absent, or worse, with a placeholder. Both are lies; the
    truth is that we looked at a stated instant and there was nothing."""
    repo = _repo_with(tmp_path, actuals=[])
    store = pit.PointInTimeStore(tmp_path / "store")
    summary = capture.collect(repo, store, as_of=SCHEDULED + timedelta(days=1))

    assert summary["releases_past"] == 1 and summary["statuses"][pit.AWAITED] == 1
    row = store.rows()[0]
    assert row["status"] == pit.AWAITED and row["value"] is None
    assert "NO_VALUE_IN_ANY_SOURCE_WE_READ" in row["why"]
    assert row["scheduled_at"] == SCHEDULED.isoformat()
    assert row["received_at"] > row["scheduled_at"]


# --------------------------------------------------------------
# the clocks
# --------------------------------------------------------------

def test_every_row_says_its_receipt_clock_bounds_publication_from_above_only(store):
    row, _ = store.append(observation())
    assert row["publication_bound"]["upper"] == row["received_at"]
    assert row["publication_bound"]["lower"] is None
    assert "UPPER_BOUND_ONLY" in row["publication_bound"]["reading"]
    assert row["publication_clock"] == "NOT_OBSERVED"


def test_a_source_publication_instant_after_our_receipt_is_refused(store):
    with pytest.raises(pit.PointInTimeRefusal, match="RECEIVED_BEFORE_PUBLISHED"):
        store.append(observation(source_publication_at=SCHEDULED + timedelta(days=1)))


def test_a_naive_timestamp_is_refused_rather_than_localized(store):
    with pytest.raises(pit.PointInTimeRefusal, match="NAIVE_TIMESTAMP"):
        store.append(observation(received_at=datetime(2026, 3, 4, 13, 37)))


def test_the_collector_has_no_flag_that_sets_the_receipt_clock(capsys):
    """The failure: a caller backdating availability. `--scheduled-through` filters the CALENDAR; no option of this
    worker moves our clock. The test reads the parser's own help, not the docstring."""
    with pytest.raises(SystemExit):
        capture.main(["--received-at", "2020-01-01T00:00:00+00:00"])
    capsys.readouterr()

    with pytest.raises(SystemExit):
        capture.main(["--help"])
    helptext = capsys.readouterr().out
    assert "--scheduled-through" in helptext
    assert "never moves the receipt clock" in " ".join(helptext.split())
    for forbidden in ("--received-at", "--receipt", "--now"):
        assert forbidden not in helptext, f"{forbidden} would let a caller invent availability"


# --------------------------------------------------------------
# what may never enter the store
# --------------------------------------------------------------

def test_an_awaited_row_carrying_a_value_is_refused(store):
    with pytest.raises(pit.PointInTimeRefusal, match="AWAITED_WITH_A_VALUE"):
        store.append(observation(status=pit.AWAITED))


def test_an_observed_row_without_a_value_is_refused(store):
    with pytest.raises(pit.PointInTimeRefusal, match="OBSERVED_WITHOUT_A_VALUE"):
        store.append(observation(value=None))


def test_a_supplied_name_is_never_a_store_key(store):
    with pytest.raises(pit.PointInTimeRefusal, match="INVALID_ROW_KEY"):
        store._path("../../escaped")


def test_two_releases_of_one_series_are_two_releases(store):
    store.append(observation())
    later, disposition = store.append(observation(scheduled_at=SCHEDULED + timedelta(days=28),
                                                  received_at=SCHEDULED + timedelta(days=28, minutes=5), value=160.0))
    assert disposition == "STORED" and later["revision_index"] == 0
    assert len({r["release_key"] for r in store.rows()}) == 2


# --------------------------------------------------------------
# integrity: a corrupted row is quarantined, never re-signed
# --------------------------------------------------------------

def test_a_tampered_row_fails_its_own_digest_and_is_quarantined_by_its_bytes(store):
    first, _ = store.append(observation())
    path = store._path(first["row_id"])
    tampered = json.loads(path.read_text())
    tampered["value"] = 999.0
    path.write_text(json.dumps(tampered, indent=1, sort_keys=True))

    store.refresh()
    assert store.rows()[0]["integrity"] == "FAILED"
    replaced, disposition = store.append(observation())
    assert disposition == "REPLACED_INVALID"
    quarantined = list((store.root / pit.QUARANTINE).glob("*.json"))
    assert len(quarantined) == 1 and first["row_id"] in quarantined[0].name
    assert json.loads(quarantined[0].read_text())["value"] == 999.0, "the corrupted bytes were not preserved"
    assert replaced["value"] == 151.0
    assert store.replay()["quarantined"] == 1


def test_a_true_row_for_another_release_copied_onto_this_key_is_detected(store):
    first, _ = store.append(observation())
    other, _ = store.append(observation(scheduled_at=SCHEDULED + timedelta(days=28),
                                        received_at=SCHEDULED + timedelta(days=28), value=160.0))
    store._path(first["row_id"]).write_text(store._path(other["row_id"]).read_text())
    store.refresh()
    misplaced = [r for r in store.rows() if r["integrity"] == "FAILED"]
    assert misplaced and any("MISPLACED_ROW" in p for p in misplaced[0]["integrity_problems"])
    known = store.known_at(SCHEDULED + timedelta(days=90))
    assert all(r["integrity"] == "OK" for r in known)
    assert first["row_id"] not in [r["row_id"] for r in known], "a fact about another release was served as this one"


# --------------------------------------------------------------
# the collector against a tiny archive
# --------------------------------------------------------------

def _repo_with(tmp_path, actuals):
    """A miniature financial-data tree: one scheduled release, and whatever actuals the test wants."""
    import pandas as pd
    repo = tmp_path / "repo"
    (repo / capture.CALENDAR_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo / capture.ANNOUNCEMENTS_PATH).parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"currency": "USD", "release": "non_farm_payrolls",
                   "announcement_datetime_utc": pd.Timestamp(SCHEDULED)}]).to_parquet(repo / capture.CALENDAR_PATH)
    frame = pd.DataFrame(actuals or [], columns=["currency", "indicator", "date", "val",
                                                 "announcement_datetime_utc"])
    frame["announcement_datetime_utc"] = pd.to_datetime(frame["announcement_datetime_utc"], utc=True)
    frame.to_parquet(repo / capture.ANNOUNCEMENTS_PATH)
    return repo


def test_the_collector_records_a_value_with_our_clock_and_the_sources_identity(tmp_path):
    repo = _repo_with(tmp_path, [{"currency": "USD", "indicator": "non_farm_payrolls", "date": "2026-02-28",
                                  "val": 151.0, "announcement_datetime_utc": SCHEDULED}])
    store = pit.PointInTimeStore(tmp_path / "store")
    before = pit.now()
    summary = capture.collect(repo, store, as_of=SCHEDULED + timedelta(days=1))
    after = pit.now()

    assert summary["statuses"][pit.OBSERVED] == 1
    row = store.rows()[0]
    assert row["value"] == 151.0 and row["match_rule"] == capture.MATCH_EXACT
    assert before.isoformat() <= row["received_at"] <= after.isoformat(), "the receipt clock was not ours"
    assert row["source"] == capture.ANNOUNCEMENTS_SOURCE and len(row["source_sha256"]) == 64
    assert row["source_publication_at"] == SCHEDULED.isoformat() and row["publication_clock"] == "SOURCE_DECLARED"
    assert row["unit"] is None and "SOURCE_DECLARES_NO_UNIT" in row["unit_reason"]
    assert row["execution_authorized"] is False


def test_the_collector_does_not_look_at_a_release_that_has_not_happened(tmp_path):
    repo = _repo_with(tmp_path, [])
    store = pit.PointInTimeStore(tmp_path / "store")
    summary = capture.collect(repo, store, as_of=SCHEDULED - timedelta(days=1))
    assert summary["releases_past"] == 0 and summary["releases_future"] == 1 and store.rows() == []


def test_a_source_that_carries_two_different_values_for_one_release_yields_no_value(tmp_path):
    repo = _repo_with(tmp_path, [{"currency": "USD", "indicator": "non_farm_payrolls", "date": "2026-02-28",
                                  "val": 151.0, "announcement_datetime_utc": SCHEDULED},
                                 {"currency": "USD", "indicator": "non_farm_payrolls", "date": "2026-02-28",
                                  "val": 143.0, "announcement_datetime_utc": SCHEDULED}])
    store = pit.PointInTimeStore(tmp_path / "store")
    summary = capture.collect(repo, store, as_of=SCHEDULED + timedelta(days=1))
    assert summary["statuses"][pit.AMBIGUOUS_SOURCE] == 1
    row = store.rows()[0]
    assert row["status"] == pit.AMBIGUOUS_SOURCE and row["value"] is None
    assert "AMBIGUOUS_SOURCE_ROWS" in row["why"]


def test_running_the_collector_twice_over_an_unchanged_archive_adds_nothing(tmp_path):
    repo = _repo_with(tmp_path, [{"currency": "USD", "indicator": "non_farm_payrolls", "date": "2026-02-28",
                                  "val": 151.0, "announcement_datetime_utc": SCHEDULED}])
    store = pit.PointInTimeStore(tmp_path / "store")
    capture.collect(repo, store, as_of=SCHEDULED + timedelta(days=1))
    fingerprint = {p.name: p.read_bytes() for p in sorted(store.root.rglob("*.json"))}
    summary = capture.collect(repo, store.refresh(), as_of=SCHEDULED + timedelta(days=1))
    assert summary["dispositions"] == {"STORED": 0, "REVISION": 0, "DUPLICATE": 1, "REPLACED_INVALID": 0}
    assert {p.name: p.read_bytes() for p in sorted(store.root.rglob("*.json"))} == fingerprint


def test_a_revised_value_in_the_archive_becomes_a_revision_and_the_old_view_is_unchanged(tmp_path):
    repo = _repo_with(tmp_path, [{"currency": "USD", "indicator": "non_farm_payrolls", "date": "2026-02-28",
                                  "val": 151.0, "announcement_datetime_utc": SCHEDULED}])
    store = pit.PointInTimeStore(tmp_path / "store")
    capture.collect(repo, store, as_of=SCHEDULED + timedelta(days=1))
    first_row = store.rows()[0]

    _repo_with(tmp_path, [{"currency": "USD", "indicator": "non_farm_payrolls", "date": "2026-02-28",
                           "val": 143.0, "announcement_datetime_utc": SCHEDULED}])
    summary = capture.collect(repo, store.refresh(), as_of=SCHEDULED + timedelta(days=1))

    assert summary["dispositions"]["REVISION"] == 1
    assert [r["value"] for r in store.known_at(first_row["received_at"])] == [151.0]
    assert [r["value"] for r in store.known_at(pit.now())] == [143.0]
    assert store.replay()["integrity_failures"] == []


def test_the_run_summary_names_the_sources_it_did_not_join(tmp_path):
    """The failure: a source quietly absent. A reader cannot distinguish that from a source nobody thought of."""
    repo = _repo_with(tmp_path, [])
    summary = capture.collect(repo, pit.PointInTimeStore(tmp_path / "store"), as_of=SCHEDULED + timedelta(days=1))
    assert set(summary["sources_not_joined"]) == {"fred_release_actuals", "fred_release_date_proxy"}
    for entry in summary["sources_not_joined"].values():
        assert entry["reason"].split(":")[0].isupper()
