"""The point-in-time store: what we knew about a macro release, and WHEN we knew it.

Every archive on this machine records what a number turned out to be. None of them records when it reached us, and
that is the fact an availability-correct backtest needs and cannot reconstruct afterwards. This store exists to write
that fact down from now on, one row at a time, and never to touch a row again.

Three clocks, kept apart, because merging any two of them invents information:

* `scheduled_at` -- when the calendar said the release would happen. It is a schedule, not an event.
* `source_publication_at` -- when the SOURCE says the number was announced. It is the source's claim; we did not
  witness it. It is null for every source that declares none, and nothing here substitutes one.
* `received_at` -- when THIS system first held the value. Our own clock, stamped here and nowhere else.

`received_at` bounds the publication instant **from above and never from below**: the number existed no later than the
moment we read it, and may have existed for hours before. Every row carries that reading in `publication_bound` so a
consumer cannot quietly promote a receipt into a publication.

**A row is never rewritten.** A value that changes is a NEW row with a higher `revision_index`; the earlier row keeps
its bytes, its digest and its receipt clock. A reader reconstructs "what was known at time T" by discarding every row
whose `received_at` is after T -- which only works because no row was ever edited to say something it did not say.

The identity, containment, exclusive-create and quarantine-by-bytes rules are the ones `news_signal.shadow` and
`news_signal.collector` already enforce in this fleet, restated here because a cross-repository import is not
available: a key is a digest this store computes from what the row IS, never a name that arrived from outside; a row
is validated against the key it was found under as well as against its own digest, because a whole, self-consistent
row for another release answers the self-hash question perfectly; a row that fails validation is quarantined under a
name carrying its own bytes rather than deleted or re-signed, because re-signing launders corruption into something a
consumer will trust.

Nothing here reads the network, holds a credential, or authorizes anything. `execution_authorized` is False in every
row it writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

SCHEMA = "m5phet.point_in_time.v1"

#: an observation is in exactly one of these. They are different facts, not versions of one field.
OBSERVED = "OBSERVED"            # the source carried a value for this release when we read it
AWAITED = "AWAITED"              # the scheduled instant has passed and no source we read carries a value yet
AMBIGUOUS_SOURCE = "AMBIGUOUS_SOURCE"   # the source carried more than one value for this release; none is chosen
STATUSES = (OBSERVED, AWAITED, AMBIGUOUS_SOURCE)

#: what identifies WHICH RELEASE a row is about. The scheduled instant is part of it: two releases of one series are
#: two releases, and a store keyed only by series would overwrite January with February.
RELEASE_IDENTITY = ("calendar_source", "economy", "series", "scheduled_at")

#: what identifies WHICH OBSERVATION it is. Our clock is deliberately absent: reading the same value twice is one
#: observation seen twice, not two observations, and a receipt clock inside the key would make every run a revision.
OBSERVATION_IDENTITY = ("source", "status", "value", "value_period", "unit")

REQUIRED = ("calendar_source", "economy", "series", "scheduled_at", "status", "received_at", "source", "source_path",
            "source_sha256")

QUARANTINE = "quarantine"

PUBLICATION_BOUND_READING = (
    "UPPER_BOUND_ONLY: this release was public no later than `received_at`, which is our clock, not the source's. It "
    "may have been public for hours before. A receipt clock bounds a publication instant from above and never from "
    "below, and substituting one for the other would place a release inside or outside an event window by guesswork.")


class PointInTimeRefusal(ValueError):
    """A refusal that names its own reason. No point-in-time fact is ever invented to avoid one."""


# --- primitives -------------------------------------------------------------------------------------------------

def canonical(value):
    """Strict canonical JSON. `default=str` is deliberately NOT used: an object this cannot serialize is a field whose
    identity nobody defined, and stringifying it would give two different objects one digest."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def instant(value, field):
    """An unambiguous instant, as UTC. A naive timestamp is refused, never localized for you: during a daylight-saving
    fold one wall clock names two instants, and choosing one is a guess about when something was knowable."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise PointInTimeRefusal(f"NAIVE_TIMESTAMP: {field} carries no offset, so it names no instant")
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise PointInTimeRefusal(f"TIMESTAMP_REQUIRED: {field} is not a timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise PointInTimeRefusal(f"UNREADABLE_TIMESTAMP: {field}={value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PointInTimeRefusal(f"AMBIGUOUS_LOCAL_TIME: {field}={value!r} carries no offset")
    return parsed.astimezone(timezone.utc)


def now():
    return datetime.now(timezone.utc)


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise PointInTimeRefusal(f"NON_FINITE_VALUE: {field}={value!r}")
    return float(value)


def release_identity(row):
    return {field: row.get(field) for field in RELEASE_IDENTITY}


def release_key(row):
    """The opaque key of a release. Computed here from the release's own fields; never a provider's identifier, which
    means nothing outside the provider that issued it and is not a safe path component."""
    return digest({"schema": SCHEMA, "release": release_identity(row)})


def observation_identity(row):
    return {field: row.get(field) for field in OBSERVATION_IDENTITY}


def row_identity(row):
    """The store key: this release, observed to be this. Two readings of the same value collide on it by construction,
    which is exactly why re-reading an unchanged archive does not manufacture revisions."""
    return digest({"schema": SCHEMA, "release_key": release_key(row), "observation": observation_identity(row)})


def validate_observation(observation):
    """One observation, checked before it can enter the store. Returns a normalized copy; refuses rather than repairs."""
    if not isinstance(observation, dict):
        raise PointInTimeRefusal("OBSERVATION_MUST_BE_A_MAPPING")
    missing = [f for f in REQUIRED if observation.get(f) in (None, "")]
    if missing:
        raise PointInTimeRefusal(f"OBSERVATION_FIELDS_MISSING: {', '.join(missing)}")
    if observation["status"] not in STATUSES:
        raise PointInTimeRefusal(f"UNKNOWN_OBSERVATION_STATUS: {observation['status']!r} is not one of {list(STATUSES)}")
    out = dict(observation)
    out["schema"] = SCHEMA
    out["scheduled_at"] = instant(observation["scheduled_at"], "scheduled_at").isoformat()
    out["received_at"] = instant(observation["received_at"], "received_at").isoformat()
    if observation.get("source_publication_at"):
        out["source_publication_at"] = instant(observation["source_publication_at"], "source_publication_at").isoformat()
        if out["source_publication_at"] > out["received_at"]:
            raise PointInTimeRefusal(
                f"RECEIVED_BEFORE_PUBLISHED: {observation['series']} claims a source publication instant after the "
                f"moment we read it; one of the two clocks is wrong and guessing which would corrupt both")
    else:
        out["source_publication_at"] = None
    if out["status"] == OBSERVED:
        if observation.get("value") is None:
            raise PointInTimeRefusal(f"OBSERVED_WITHOUT_A_VALUE: {observation['series']} at {out['scheduled_at']}")
        out["value"] = _number(observation["value"], "value")
    else:
        if observation.get("value") is not None:
            raise PointInTimeRefusal(
                f"{out['status']}_WITH_A_VALUE: a release we have not seen a value for must not carry one; recording "
                f"a placeholder is how an invented number enters an archive that looks complete")
        out["value"] = None
    out["value_period"] = observation.get("value_period")
    out["unit"] = observation.get("unit")
    out["unit_reason"] = observation.get("unit_reason") or (None if out["unit"] else "SOURCE_DECLARES_NO_UNIT")
    out["why"] = observation.get("why")
    return out


# --- the store --------------------------------------------------------------------------------------------------

class PointInTimeStore:
    """A directory of rows. Append-only by construction: the only write is an exclusive create."""

    def __init__(self, directory):
        self.root = Path(directory)
        self._index = None

    def refresh(self):
        """Drop the in-process index of what is on disk. The index only ever serves the WRITE path (it is how a new
        observation learns which observations of its release preceded it); every reader re-reads and re-validates the
        files, so a stale index can never turn into a stale answer. Correctness under a second writer does not depend
        on it either: the write is an exclusive create, so a key another process already owns is read back, never
        overwritten."""
        self._index = None
        return self

    def _release_index(self):
        if self._index is None:
            index = {}
            for row in self.rows():
                index.setdefault(row.get("release_key"), []).append(row)
            self._index = index
        return self._index

    # --- containment ---------------------------------------------------------------------------------------------
    def _resolved_root(self):
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root.resolve(strict=True)

    def _path(self, row_id):
        if not isinstance(row_id, str) or len(row_id) != 64 or any(c not in "0123456789abcdef" for c in row_id):
            raise PointInTimeRefusal("INVALID_ROW_KEY: a store key is a digest this store computed, never a supplied name")
        root = self._resolved_root()
        path = root / row_id[:2] / f"{row_id}.json"
        self._contained(root, path)
        return path

    @staticmethod
    def _contained(root, path):
        probe = path
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        resolved = probe.resolve()
        if resolved != root and root not in resolved.parents:
            raise PointInTimeRefusal(f"STORE_ESCAPE_REFUSED: {path.name} resolves outside the store root")

    # --- reading -------------------------------------------------------------------------------------------------
    def _read(self, path, *, expected_key=None):
        """A torn row is reported as a failure of THAT key. It must not make the store unreadable, and it must never be
        mistaken for an absent row."""
        if expected_key is None and path.parent.name != QUARANTINE:
            expected_key = path.stem
        try:
            row = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            return {"row_sha256": None, "row_id": expected_key, "integrity": "FAILED", "unreadable": True,
                    "integrity_problems": [f"UNREADABLE_ROW: {path.name}: {exc.__class__.__name__}"],
                    "release_key": None, "status": None, "received_at": None}
        if not isinstance(row, dict):
            return {"row_sha256": None, "row_id": expected_key, "integrity": "FAILED", "unreadable": True,
                    "integrity_problems": ["ROW_NOT_A_MAPPING"], "release_key": None, "status": None,
                    "received_at": None}
        return self._checked(row, expected_key=expected_key)

    @staticmethod
    def _checked(row, expected_key=None):
        """Three questions, not one. Does the row hash to its own digest? Do its own fields derive the key it carries?
        And is that the key it was found under? The last is the one a copied file answers wrongly and silently."""
        row = dict(row)
        recomputed = digest({k: v for k, v in row.items() if k != "row_sha256"})
        problems = []
        if row.get("row_sha256") != recomputed:
            problems.append("CONTENT_DIGEST_MISMATCH: the row does not hash to its own recorded digest")
        try:
            derived = row_identity(row)
        except (TypeError, ValueError):
            derived = None
            problems.append("IDENTITY_NOT_DERIVABLE: this row's fields do not form an identity")
        if derived is not None and row.get("row_id") != derived:
            problems.append(f"IDENTITY_MISMATCH: the row's own fields derive key {derived[:12]} and it carries "
                            f"{str(row.get('row_id'))[:12]}")
        if expected_key is not None and derived is not None and derived != expected_key:
            problems.append(f"MISPLACED_ROW: this row belongs under key {derived[:12]} and was found under "
                            f"{expected_key[:12]}; a true fact about another release is not this release's record")
        row["integrity"] = "OK" if not problems else "FAILED"
        row["integrity_problems"] = problems
        row["recomputed_sha256"] = recomputed
        row["derived_row_id"] = derived
        return row

    def rows(self, *, include_quarantine=False):
        """Every live row, oldest receipt first. Quarantined rows stay out of every count unless asked for."""
        if not self.root.is_dir():
            return []
        out = []
        for path in sorted(self.root.rglob("*.json")):
            if path.is_symlink():
                continue
            quarantined = path.parent.name == QUARANTINE
            if quarantined and not include_quarantine:
                continue
            row = self._read(path)
            row["quarantined"] = quarantined
            out.append(row)
        return sorted(out, key=lambda r: (r.get("received_at") or "", r.get("row_sha256") or ""))

    def rows_for(self, key):
        """Every retained observation of one release, whatever it said."""
        return [r for r in self.rows() if r.get("release_key") == key]

    def known_at(self, as_of, *, release=None):
        """What was known at T: for each release, the last VALID row received no later than T.

        A row received after T is not merely ranked lower here -- it is absent, because the question is what a decision
        made at T could have used, and a decision cannot use what had not arrived.
        """
        cutoff = instant(as_of, "as_of").isoformat()
        latest = {}
        for row in self.rows():
            if row.get("integrity") != "OK":
                continue
            received = row.get("received_at")
            if received is None or received > cutoff:
                continue
            if release is not None and row.get("release_key") != release:
                continue
            key = row.get("release_key")
            current = latest.get(key)
            if current is None or (received, row.get("row_sha256") or "") > (current["received_at"],
                                                                             current.get("row_sha256") or ""):
                latest[key] = row
        return [latest[k] for k in sorted(latest)]

    def find_row(self, reference):
        path = self._path(reference)
        if path.is_file():
            return self._read(path)
        for row in self.rows(include_quarantine=True):
            if row.get("row_sha256") == reference or row.get("row_id") == reference:
                return row
        return None

    # --- writing -------------------------------------------------------------------------------------------------
    def append(self, observation):
        """Record one observation. Returns (row, disposition): STORED, REVISION, DUPLICATE or REPLACED_INVALID.

        DUPLICATE is returned only when this exact observation is already on disk AND that stored row still validates.
        Its bytes are returned unchanged -- re-reading an archive that has not moved adds nothing and rewrites nothing.
        """
        observation = validate_observation(observation)
        key = release_key(observation)
        row_id = row_identity(observation)
        path = self._path(row_id)
        prior = list(self._release_index().get(key, []))
        existing = self._read(path, expected_key=row_id) if path.is_file() else None
        if existing is not None and existing.get("integrity") == "OK":
            return existing, "DUPLICATE"
        invalid_existing = existing is not None

        row = dict(observation)
        row["row_id"] = row_id
        row["release_key"] = key
        row["release_identity"] = release_identity(observation)
        row["observation_identity"] = observation_identity(observation)
        row["series_key"] = digest({"schema": SCHEMA, "economy": observation.get("economy"),
                                    "series": observation.get("series")})
        row["execution_authorized"] = False
        row["publication_clock"] = "SOURCE_DECLARED" if observation.get("source_publication_at") else "NOT_OBSERVED"
        row["publication_bound"] = {"upper": observation["received_at"], "lower": None,
                                    "reading": PUBLICATION_BOUND_READING}
        # the revision index counts the DISTINCT observations of this release that preceded this one. A row that only
        # repeats what we already recorded never reaches this line, so the index moves when the fact moves and not when
        # the collector runs.
        seen = {p.get("observation_sha256") for p in prior}
        row["observation_sha256"] = digest({"schema": SCHEMA, "observation": observation_identity(observation)})
        row["revision_index"] = len(seen - {row["observation_sha256"]})
        values_before = [p for p in prior if p.get("status") == OBSERVED]
        row["value_revision_index"] = (len({p.get("observation_sha256") for p in values_before}
                                           - {row["observation_sha256"]}) if observation["status"] == OBSERVED else None)
        row["supersedes"] = sorted(p["row_sha256"] for p in prior
                                   if p.get("observation_sha256") != row["observation_sha256"] and p.get("row_sha256"))
        row["supersedes_reading"] = ("later information about the same release. The superseded rows are retained and "
                                     "stay true of the moment they were received")
        if invalid_existing:
            row["replaces_invalid_row"] = row_id
            row["quarantined_predecessor"] = self._quarantine(path, row_id)
        row["row_sha256"] = digest({k: v for k, v in row.items() if k != "row_sha256"})

        created = self._write(path, row)
        if not created:
            # another writer won the race for this key. Their row is the row: two callers must not walk away holding
            # different digests for one observation.
            raced = self._read(path, expected_key=row_id)
            if raced.get("integrity") == "OK":
                return raced, "DUPLICATE"
            self._quarantine(path, row_id)
            self._write(path, row)
        self._release_index().setdefault(key, []).append(self._checked(row, expected_key=row_id))
        if invalid_existing:
            return row, "REPLACED_INVALID"
        return row, ("STORED" if not prior else "REVISION")

    def write_row(self, row):
        """The low-level write, exposed so that an attempt to change a past row is REFUSED BY NAME rather than merely
        failing to happen. A caller that has forged a key and wants to put different facts under it is the case this
        store exists to make impossible."""
        row_id = row.get("row_id")
        path = self._path(row_id)
        if path.is_file():
            stored = self._read(path, expected_key=row_id)
            if stored.get("observation_sha256") != row.get("observation_sha256"):
                raise PointInTimeRefusal(
                    f"ROW_REWRITE_REFUSED: {row_id[:12]} already records observation "
                    f"{str(stored.get('observation_sha256'))[:12]}. A value that changed is a NEW row with a higher "
                    f"revision; rewriting this one would delete what we knew at "
                    f"{stored.get('received_at')} and no reader could ever tell")
            return stored, "DUPLICATE"
        return (row, "STORED") if self._write(path, row) else (self._read(path, expected_key=row_id), "DUPLICATE")

    def _quarantine(self, path, row_id):
        """A row that failed a check is moved aside, not deleted and never re-signed: deleting it erases what went
        wrong, and re-signing it would recompute the digest over corrupted content and make the corruption credible.
        The quarantine name carries the quarantined BYTES, so a second bad version cannot overwrite the first."""
        root = self._resolved_root()
        try:
            content = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
        except OSError:
            content = "unreadable"
        target = root / QUARANTINE / f"{row_id}.{content}.json"
        self._contained(root, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return target.relative_to(root).as_posix()          # these exact bytes are already preserved
        os.replace(path, target)
        return target.relative_to(root).as_posix()

    def _write(self, path, row) -> bool:
        """Exclusive create, never a replace. `os.link` fails if the key exists, so the first writer owns it and every
        later one reads it back. There is no code path in this module that replaces a live row."""
        path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=str(path.parent), prefix=".writing-", suffix=".json.tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, indent=1, sort_keys=True))
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
                return True
            except FileExistsError:
                return False
        finally:
            Path(temporary).unlink(missing_ok=True)

    # --- replay --------------------------------------------------------------------------------------------------
    def replay(self):
        """Read every row back and re-derive its identity. A row that fails is REPORTED, never repaired."""
        report = {"schema": SCHEMA, "rows": 0, "releases": 0, "revisions": 0, "observed": 0, "awaited": 0,
                  "ambiguous": 0, "quarantined": 0, "unfinished_writes": 0, "integrity_failures": [],
                  "series": [], "earliest_received_at": None, "latest_received_at": None,
                  "earliest_scheduled_at": None, "latest_scheduled_at": None}
        if not self.root.is_dir():
            return report
        for row in self.rows(include_quarantine=True):
            if not row.get("quarantined"):
                continue
            report["quarantined"] += 1
            report["integrity_failures"].append({"row_id": row.get("row_id"), "quarantined": True,
                                                 "problems": row.get("integrity_problems")})
        report["unfinished_writes"] = len(list(self.root.rglob("*.tmp")))
        by_release, series, received, scheduled = {}, set(), [], []
        for row in self.rows():
            report["rows"] += 1
            by_release.setdefault(row.get("release_key"), []).append(row)
            if row.get("integrity") != "OK":
                report["integrity_failures"].append({"row_id": row.get("row_id"),
                                                     "problems": row.get("integrity_problems")})
                continue
            if row.get("execution_authorized") is not False:
                report["integrity_failures"].append({"row_id": row.get("row_id"),
                                                     "problems": ["EXECUTION_AUTHORIZED_IN_STORE"]})
            identity = row.get("release_identity") or {}
            series.add(f"{identity.get('economy')}:{identity.get('series')}")
            received.append(row.get("received_at"))
            scheduled.append(row.get("scheduled_at"))
            report[{OBSERVED: "observed", AWAITED: "awaited", AMBIGUOUS_SOURCE: "ambiguous"}[row["status"]]] += 1
        report["releases"] = len(by_release)
        report["revisions"] = sum(max(0, len({r.get("observation_sha256") for r in rows}) - 1)
                                  for rows in by_release.values())
        report["series"] = sorted(series)
        received, scheduled = sorted(x for x in received if x), sorted(x for x in scheduled if x)
        if received:
            report["earliest_received_at"], report["latest_received_at"] = received[0], received[-1]
        if scheduled:
            report["earliest_scheduled_at"], report["latest_scheduled_at"] = scheduled[0], scheduled[-1]
        report["publication_bound_reading"] = PUBLICATION_BOUND_READING
        return report
