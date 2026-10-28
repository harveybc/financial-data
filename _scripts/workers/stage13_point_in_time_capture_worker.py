#!/usr/bin/env python3
"""The point-in-time collector: stamp WHEN we received what we already receive.

Every macro archive on this machine says what a number turned out to be. None of them says when it reached us, and
no archive can be made to say it afterwards -- a receipt clock exists only if somebody was running when the number
arrived. This worker is that somebody. It reads the scheduled releases and the actuals already on disk, and for every
release whose scheduled instant has passed it appends one row to `m5phet.point_in_time.v1` carrying the value it found
and, above all, **our clock at the moment we found it**.

What it deliberately does NOT do:

* **No new external source, no credential, no network call.** It opens local parquet files and nothing else. The value
  of this package is not new data; it is the timestamp on data we already had.
* **No backdating.** The receipt clock is `datetime.now(timezone.utc)` inside this process. There is no flag that sets
  it, because a collector that let its receipt clock be supplied would let a caller invent availability.
* **No filling.** A release whose scheduled instant has passed and for which no source we read carries a value is
  recorded AWAITED -- a row that says "we looked and there was nothing", which is a fact. It is not recorded as
  missing, and it is never recorded with a placeholder value.
* **No guessing between sources.** A source that cannot be joined to a scheduled release without inventing a key is
  declared, named and skipped in the run summary, not joined on a proxy.

Run it with `--once` (what the timer does) or `--loop --interval N`. The summary is one JSON line on stdout and,
if `--log` is given, one line appended to a log.
"""
from __future__ import annotations

import argparse
from datetime import timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

REPO_DEFAULT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_DEFAULT / "_scripts" / "lib"))

from point_in_time_store import (  # noqa: E402
    AMBIGUOUS_SOURCE, AWAITED, OBSERVED, PointInTimeRefusal, PointInTimeStore, instant, now,
)

WORKER = "stage13_point_in_time_capture_worker"
CALENDAR_SOURCE = "fxmacrodata_release_calendar"
CALENDAR_PATH = "economic_calendar/scheduled_events/fxmacrodata/release_calendar.parquet"

#: the one actuals table on disk that can be joined to a scheduled release without inventing a key: it carries the
#: economy, the release name and an announcement instant, which is exactly the scheduled calendar's own key.
ANNOUNCEMENTS_SOURCE = "fxmacrodata_announcements"
ANNOUNCEMENTS_PATH = "economic_calendar/release_actuals/fxmacrodata/announcements.parquet"

#: sources this repository holds that are NOT joined here, each with the reason. They are reported in every summary,
#: because a source that is silently absent is indistinguishable from a source nobody thought of.
SOURCES_NOT_JOINED = {
    "fred_release_actuals": {
        "path": "economic_calendar/release_actuals/<series>/actuals.parquet",
        "reason": ("NO_RELEASE_KEY: these tables are indexed by the REFERENCE PERIOD of the statistic, not by a "
                   "release instant, and they carry no announcement timestamp. Joining them to a scheduled release "
                   "would require a period-to-release-date rule that nobody in this repository has measured, and the "
                   "rule -- not the data -- would decide which release each value belonged to."),
    },
    "fred_release_date_proxy": {
        "path": "economic_calendar/scheduled_events/fred_release_date_proxy",
        "reason": ("PROXY_NOT_AN_OBSERVATION: the date is derived from the observation date, so using it as a "
                   "publication clock would record our own derivation as if it were a fact about the world."),
    },
}

#: how a scheduled release is matched to a source row. Both rules are declared, recorded per row, and tried in order.
MATCH_EXACT = "EXACT_INSTANT"
MATCH_SAME_DAY = "SAME_UTC_DATE"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_calendar(repo_root: Path):
    import pandas as pd
    path = Path(repo_root) / CALENDAR_PATH
    if not path.is_file():
        raise PointInTimeRefusal(f"SCHEDULED_CALENDAR_MISSING: {CALENDAR_PATH}")
    frame = pd.read_parquet(path)
    for column in ("currency", "release", "announcement_datetime_utc"):
        if column not in frame.columns:
            raise PointInTimeRefusal(f"SCHEDULED_CALENDAR_COLUMN_MISSING: {column}")
    frame = frame.dropna(subset=["announcement_datetime_utc"])
    return frame, path


def load_announcements(repo_root: Path):
    import pandas as pd
    path = Path(repo_root) / ANNOUNCEMENTS_PATH
    if not path.is_file():
        return None, path
    frame = pd.read_parquet(path)
    for column in ("currency", "indicator", "announcement_datetime_utc", "val"):
        if column not in frame.columns:
            raise PointInTimeRefusal(f"ANNOUNCEMENTS_COLUMN_MISSING: {column}")
    return frame.dropna(subset=["announcement_datetime_utc"]), path


def _reading(group):
    """One source group in, one reading out. The value is the group's value only when the group agrees with itself.

    A source that carries several different numbers for one release is not a release with a value; picking one of them
    would be this worker's opinion, recorded forever as the source's fact.
    """
    import pandas as pd
    values = sorted({float(v) for v in group["val"].dropna().tolist()})
    if not values:
        return {"status": AWAITED, "value": None,
                "why": "SOURCE_ROW_WITHOUT_A_VALUE: the source carries this release and no number for it"}
    if len(values) > 1:
        return {"status": AMBIGUOUS_SOURCE, "value": None,
                "why": (f"AMBIGUOUS_SOURCE_ROWS: {len(group)} rows for this release carry {len(values)} different "
                        f"values {values[:5]}; none of them is chosen")}
    periods = sorted(str(pd.Timestamp(d).date()) if not isinstance(d, str) else str(d)
                     for d in group["date"].dropna().tolist()) if "date" in group.columns else []
    return {"status": OBSERVED, "value": values[0], "value_period": periods[0] if periods else None}


def collect(repo_root: Path, store: PointInTimeStore, *, as_of=None):
    """One pass. Returns the run summary. The receipt clock is taken here, once per release read, from our own clock."""
    import pandas as pd

    horizon = instant(as_of, "as_of") if as_of is not None else now()
    calendar, calendar_path = load_calendar(repo_root)
    announcements, announcements_path = load_announcements(repo_root)
    calendar_sha = sha256_file(calendar_path)
    summary = {"schema": "m5phet.point_in_time_capture_run.v1", "worker": WORKER,
               "started_at": now().isoformat(), "store": str(store.root),
               "calendar": {"source": CALENDAR_SOURCE, "path": CALENDAR_PATH, "sha256": calendar_sha,
                            "rows": int(len(calendar))},
               "sources_not_joined": SOURCES_NOT_JOINED,
               "releases_scheduled": int(len(calendar)), "releases_past": 0, "releases_future": 0,
               "dispositions": {"STORED": 0, "REVISION": 0, "DUPLICATE": 0, "REPLACED_INVALID": 0},
               "statuses": {OBSERVED: 0, AWAITED: 0, AMBIGUOUS_SOURCE: 0},
               "match_rules": {MATCH_EXACT: 0, MATCH_SAME_DAY: 0},
               "refusals": []}

    if announcements is None:
        summary["actuals"] = {"source": ANNOUNCEMENTS_SOURCE, "path": ANNOUNCEMENTS_PATH, "sha256": None,
                              "rows": 0, "why": "ACTUALS_SOURCE_ABSENT: every past release is recorded AWAITED"}
        by_instant, by_day, announcements_sha = {}, {}, None
    else:
        announcements_sha = sha256_file(announcements_path)
        summary["actuals"] = {"source": ANNOUNCEMENTS_SOURCE, "path": ANNOUNCEMENTS_PATH, "sha256": announcements_sha,
                              "rows": int(len(announcements)),
                              "latest_announcement_utc": str(announcements["announcement_datetime_utc"].max())}
        by_instant = {k: g for k, g in announcements.groupby(["currency", "indicator", "announcement_datetime_utc"])}
        day = announcements["announcement_datetime_utc"].dt.date
        by_day = {k: g for k, g in announcements.groupby(["currency", "indicator", day])}

    for scheduled in calendar.itertuples(index=False):
        scheduled_at = pd.Timestamp(scheduled.announcement_datetime_utc).to_pydatetime()
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)
        if scheduled_at > horizon:
            summary["releases_future"] += 1
            continue
        summary["releases_past"] += 1
        economy, series = str(scheduled.currency), str(scheduled.release)

        group, match_rule = by_instant.get((economy, series, scheduled.announcement_datetime_utc)), MATCH_EXACT
        if group is None:
            group, match_rule = by_day.get((economy, series, scheduled_at.date())), MATCH_SAME_DAY
        if group is None:
            reading, match_rule = {"status": AWAITED, "value": None,
                                   "why": ("NO_VALUE_IN_ANY_SOURCE_WE_READ: the scheduled instant has passed and no "
                                           "source on this machine carries a number for it yet. This is a record of "
                                           "having looked, not a claim that the release did not happen")}, None
            source_publication_at = None
        else:
            reading = _reading(group)
            summary["match_rules"][match_rule] += 1
            published = group["announcement_datetime_utc"].min()
            source_publication_at = pd.Timestamp(published).to_pydatetime()

        # the receipt clock: ours, taken here, never supplied and never adjusted
        received_at = now()
        if source_publication_at is not None and source_publication_at > received_at:
            # a source instant in our future is a source problem, not a licence to move our clock
            summary["refusals"].append({"economy": economy, "series": series,
                                        "scheduled_at": scheduled_at.isoformat(),
                                        "reason": "SOURCE_PUBLICATION_AFTER_RECEIPT"})
            source_publication_at = None

        observation = {"calendar_source": CALENDAR_SOURCE, "economy": economy, "series": series,
                       "scheduled_at": scheduled_at, "received_at": received_at,
                       "source": ANNOUNCEMENTS_SOURCE if group is not None else "none",
                       "source_path": ANNOUNCEMENTS_PATH if group is not None else CALENDAR_PATH,
                       "source_sha256": (announcements_sha if group is not None else calendar_sha) or "ABSENT",
                       "source_publication_at": source_publication_at,
                       "source_rows_matched": int(len(group)) if group is not None else 0,
                       "match_rule": match_rule, "unit": None,
                       "unit_reason": "SOURCE_DECLARES_NO_UNIT: this archive carries numbers without their units",
                       **reading}
        try:
            row, disposition = store.append(observation)
        except PointInTimeRefusal as exc:
            summary["refusals"].append({"economy": economy, "series": series,
                                        "scheduled_at": scheduled_at.isoformat(), "reason": str(exc)})
            continue
        summary["dispositions"][disposition] += 1
        summary["statuses"][row["status"]] += 1

    summary["finished_at"] = now().isoformat()
    summary["store_replay"] = store.replay()
    return summary


def default_store_root() -> Path:
    env = os.environ.get("FD_PIT_STORE")
    if env:
        return Path(env).expanduser()
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "financial-data" / "point_in_time"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=str(REPO_DEFAULT), help="the financial-data checkout to read")
    parser.add_argument("--store", default=None, help="point-in-time store root (default: $FD_PIT_STORE)")
    parser.add_argument("--once", action="store_true", help="one pass and exit (the default, and what the timer does)")
    parser.add_argument("--loop", action="store_true", help="keep running, one pass every --interval seconds")
    parser.add_argument("--interval", type=float, default=10800.0, help="seconds between passes under --loop")
    parser.add_argument("--iterations", type=int, default=0, help="stop after N passes under --loop (0 = never)")
    parser.add_argument("--log", default=None, help="append one summary line per pass to this file")
    parser.add_argument("--json", dest="json_out", default=None, help="write the last summary to this file")
    parser.add_argument("--scheduled-through", default=None,
                        help="treat releases scheduled up to this instant as past (a filter on the CALENDAR; it never "
                             "moves the receipt clock, which is always this process's own)")
    args = parser.parse_args(argv)

    store = PointInTimeStore(Path(args.store).expanduser() if args.store else default_store_root())
    passes = 0
    summary = None
    while True:
        summary = collect(Path(args.repo_root), store, as_of=args.scheduled_through)
        line = json.dumps(summary, ensure_ascii=False, sort_keys=True)
        print(line, flush=True)
        if args.log:
            log = Path(args.log).expanduser()
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if args.json_out:
            out = Path(args.json_out).expanduser()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True))
        passes += 1
        if not args.loop or (args.iterations and passes >= args.iterations):
            break
        time.sleep(args.interval)
    return 0 if summary is not None and not summary["store_replay"]["integrity_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
