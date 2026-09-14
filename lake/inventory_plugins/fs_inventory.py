"""Walk data roots with stat() only. Hash and cut on download, never on discover."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

CHUNK_ROWS = 100_000
HASH_CHUNK = 1024 * 1024
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# A trailing ISO 8601 zone designator is dropped before parsing so that the
# column's own wall clock is compared, whatever offset each row carries.
ZONE_RE = r"(Z|[+-]\d{2}:?\d{2})$"
TIME_NAMES = {"ts", "time", "date", "datetime", "timestamp"}
# Pinned so a cut's bytes come from this configuration alone; the cut is then
# materialised once and never rewritten.
PARQUET_WRITER = {
    "compression": "snappy",
    "version": "2.6",
    "use_dictionary": True,
    "write_statistics": True,
}
CUT_MATERIALIZER = "finlake-causal-cut.v2"
_LAKE = Path(__file__).resolve().parents[1]


class LakeError(Exception):
    """Base of the answers the HTTP layer maps to 403/422."""


class HoldoutError(LakeError):
    """403: the request or the resource reaches the holdout."""


class UnsupportedError(LakeError):
    """422: the byte-subset cut cannot handle this file."""


class UnparseableError(LakeError):
    """422: the time column does not parse."""


def day_range(start, end):
    """Validate a day-only range; return (from 00:00, (to + 1 day) 00:00) as naive Timestamps."""
    import pandas as pd

    for value in (start, end):
        if not isinstance(value, str) or not DAY_RE.match(value):
            raise ValueError("invalid from/to")
    try:
        lo, hi = date.fromisoformat(start), date.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("invalid from/to") from exc
    if lo > hi:
        raise ValueError("invalid from/to")
    return pd.Timestamp(lo), pd.Timestamp(hi) + pd.Timedelta(days=1)


def wall_clock(series):
    """Parse a time column into naive wall-clock timestamps or raise UnparseableError."""
    import pandas as pd

    if pd.api.types.is_datetime64_any_dtype(series):
        out = series.dt.tz_localize(None) if series.dt.tz is not None else series
    elif pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        # epoch numbers without a declared unit
        raise UnparseableError("unparseable time column")
    else:
        text = series.astype("string").str.replace(ZONE_RE, "", regex=True)
        try:
            out = pd.to_datetime(text, format="ISO8601")
        except (ValueError, TypeError) as exc:
            raise UnparseableError("unparseable time column") from exc
        if out.dt.tz is not None:
            out = out.dt.tz_localize(None)
    if out.isna().any():
        raise UnparseableError("unparseable time column")
    return out.reset_index(drop=True)


def _arrow_wall_clock(column):
    import pyarrow as pa
    import pyarrow.compute as pc

    kind = column.type
    if pa.types.is_timestamp(kind):
        if kind.tz is not None:
            column = pc.local_timestamp(column)
    elif pa.types.is_date(kind):
        column = pc.cast(column, pa.timestamp("us"))
    elif not (pa.types.is_string(kind) or pa.types.is_large_string(kind)):
        raise UnparseableError("unparseable time column")
    return wall_clock(column.to_pandas())


def _cut_csv(source: Path, dest: Path, mask):
    """Pass two: copy the header and the kept lines byte for byte."""
    n = len(mask)
    i = 0
    owns_source = not hasattr(source, "read")
    src = open(source, "rb") if owns_source else source
    try:
        src.seek(0)
        out = open(dest, "wb")
        try:
            header = src.readline()
            if not header:
                raise UnsupportedError("unsupported csv")
            out.write(header)
            for line in src:
                if line.strip(b"\r\n") == b"":
                    continue  # pandas skips blank lines; the parsed count does not include them
                if i < n and mask[i]:
                    out.write(line)
                i += 1
        finally:
            out.close()
    finally:
        if owns_source:
            src.close()
    if i != n:
        # multi-line quoted records: the physical lines do not map 1:1 to rows
        raise UnsupportedError("unsupported csv")


def _cut_parquet(source: Path, dest: Path, mask):
    import pyarrow as pa
    import pyarrow.parquet as pq

    reader = pq.ParquetFile(source)
    offset = 0
    with pq.ParquetWriter(dest, reader.schema_arrow, **PARQUET_WRITER) as writer:
        for batch in reader.iter_batches(batch_size=CHUNK_ROWS):
            n = batch.num_rows
            keep = mask[offset : offset + n]
            offset += n
            if not keep.any():
                continue
            table = pa.Table.from_batches([batch])
            if not keep.all():
                table = table.filter(pa.array(keep))
            writer.write_table(table, row_group_size=CHUNK_ROWS)
    if offset != len(mask):
        raise RuntimeError("parquet row count changed while materialising cut")


class Plugin:
    plugin_params = {
        "root_path": ".",
        "include_globs": ["**/*.parquet", "**/*.csv"],
        "holdout_start": "2025-01-01",
        "time_column": None,
        "time_columns": {},
        "resource_contracts": {},
        "untimed": [],
        "spool_dir": None,
        "cuts_dir": None,
        "max_downloads": 2,
        "lake_id": "financial_files",
        "title": "financial-data",
        "description": "",
        "kind": "files_inventory",
    }

    def __init__(self):
        self.params = dict(self.plugin_params)
        self._cache = None
        self._memo = None
        self._lock = threading.Lock()

    def set_params(self, **kwargs):
        self.params.update(kwargs)
        self._cache = None
        self._memo = None

    def _root(self) -> Path:
        return Path(self.params.get("root_path") or ".").resolve()

    def spool_dir(self) -> Path:
        return Path(self.params.get("spool_dir") or _LAKE / "var" / "spool")

    def cuts_dir(self) -> Path:
        return Path(self.params.get("cuts_dir") or _LAKE / "var" / "cuts")

    def is_spool(self, path) -> bool:
        return Path(path).resolve().is_relative_to(self.spool_dir().resolve())

    def sweep(self):
        """Process start: nothing intermediate survives a crash."""
        spool = self.spool_dir()
        spool.mkdir(parents=True, exist_ok=True)
        for item in spool.iterdir():
            if item.is_file():
                item.unlink()
        cuts = self.cuts_dir()
        cuts.mkdir(parents=True, exist_ok=True)
        for item in cuts.rglob("*.part"):
            item.unlink()

    def discover(self, refresh=False):
        if self._cache is not None and not refresh:
            return self._cache
        root = self._root()
        items = []
        seen = set()
        for pattern in self.params.get("include_globs") or []:
            for path in root.glob(pattern):
                if not path.is_file():
                    continue
                rel = path.relative_to(root).as_posix()
                if rel in seen:
                    continue
                seen.add(rel)
                st = path.stat()
                items.append(
                    {
                        "resource_id": rel,
                        "bytes": st.st_size,
                        "mtime": datetime.fromtimestamp(
                            st.st_mtime, tz=timezone.utc
                        ).isoformat(),
                        "kind": "file",
                    }
                )
        items.sort(key=lambda row: row["resource_id"])
        self._cache = items
        return items

    def list_resources(self):
        return self.discover()

    def _path(self, resource_id: str) -> Path:
        # A resource id is a relative path inside the lake: no absolute ids, no '..', no escape by symlink.
        rid = str(resource_id or "")
        if not rid or rid.startswith(("/", "\\")) or "\\" in rid or any(p in ("", ".", "..") for p in rid.split("/")):
            raise FileNotFoundError(rid)
        root = self._root().resolve()
        path = (root / rid).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise FileNotFoundError(rid)
        return path

    def _frame(self, resource_id: str):
        import pandas as pd

        path = self._path(resource_id)
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    def _columns(self, path: Path):
        if path.suffix.lower() == ".parquet":
            import pyarrow.parquet as pq

            return list(pq.read_schema(path).names)
        import pandas as pd

        return list(pd.read_csv(path, nrows=0).columns)

    def _time_col(self, resource_id: str, path: Path):
        if resource_id in (self.params.get("untimed") or []):
            return None
        columns = self._columns(path)
        declared = (self.params.get("time_columns") or {}).get(resource_id)
        for named in (declared, self.params.get("time_column")):
            if named and named in columns:
                return named
        for col in columns:
            lower = str(col).lower()
            if lower in TIME_NAMES or "time" in lower or "date" in lower:
                return col
        return None

    def _time_blocks(self, path: Path, col):
        """Yield the time column only, as wall-clock Series, one block at a time."""
        if path.suffix.lower() == ".parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq

            try:
                reader = pq.ParquetFile(path)
                for batch in reader.iter_batches(batch_size=CHUNK_ROWS, columns=[col]):
                    yield _arrow_wall_clock(batch.column(0))
            except pa.ArrowException as exc:
                raise UnsupportedError("unsupported parquet") from exc
            return
        import pandas as pd

        try:
            with pd.read_csv(path, usecols=[col], chunksize=CHUNK_ROWS) as chunks:
                for chunk in chunks:
                    yield wall_clock(chunk[col])
        except pd.errors.ParserError as exc:
            raise UnsupportedError("unsupported csv") from exc

    def _count_rows(self, path: Path) -> int:
        if path.suffix.lower() == ".parquet":
            import pyarrow.parquet as pq

            return int(pq.read_metadata(path).num_rows)
        import pandas as pd

        with pd.read_csv(path, usecols=[0], chunksize=CHUNK_ROWS) as chunks:
            return sum(len(chunk) for chunk in chunks)

    def _scan(self, path: Path, col):
        rows, t_min, t_max = 0, None, None
        for block in self._time_blocks(path, col):
            rows += len(block)
            if len(block):
                lo, hi = block.min(), block.max()
                t_min = lo if t_min is None or lo < t_min else t_min
                t_max = hi if t_max is None or hi > t_max else t_max
        return rows, t_min, t_max

    def _keep_mask(self, path: Path, col, lo, hi):
        """Rows with lo <= t < hi on the wall clock, and max(t) over the kept rows."""
        import numpy as np

        parts, kept_max = [], None
        for block in self._time_blocks(path, col):
            keep = (block >= lo) & (block < hi)
            parts.append(keep.to_numpy())
            if keep.any():
                top = block[keep].max()
                kept_max = top if kept_max is None or top > kept_max else kept_max
        mask = np.concatenate(parts) if parts else np.zeros(0, dtype=bool)
        return mask, kept_max

    def _holdout(self):
        value = self.params.get("holdout_start")
        if not value:
            return None
        import pandas as pd

        return pd.Timestamp(value)

    def _memo_path(self) -> Path:
        return self.cuts_dir().parent / "source_sha256.json"

    def _load_memo(self):
        if self._memo is None:
            try:
                self._memo = json.loads(self._memo_path().read_text(encoding="utf-8"))
            except (OSError, ValueError):
                self._memo = {}
        return self._memo

    def sha256(self, path) -> tuple[str, int]:
        """Hash one stable file identity; cache hits bind all mutable stat facts."""
        path = Path(path)
        key = str(path)
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before = os.fstat(fd)
        named = path.stat(follow_symlinks=False)
        if (before.st_dev, before.st_ino) != (named.st_dev, named.st_ino):
            os.close(fd)
            raise RuntimeError("source identity changed")
        with self._lock:
            hit = self._load_memo().get(key)
        facts = {
            "dev": before.st_dev,
            "ino": before.st_ino,
            "size": before.st_size,
            "mtime_ns": before.st_mtime_ns,
            "ctime_ns": before.st_ctime_ns,
        }
        if hit and all(hit.get(name) == value for name, value in facts.items()):
            os.close(fd)
            return hit["sha256"], before.st_size
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "rb", closefd=False) as handle:
                for block in iter(lambda: handle.read(HASH_CHUNK), b""):
                    digest.update(block)
            after = os.fstat(fd)
            named_after = path.stat(follow_symlinks=False)
        finally:
            os.close(fd)
        after_facts = {
            "dev": after.st_dev,
            "ino": after.st_ino,
            "size": after.st_size,
            "mtime_ns": after.st_mtime_ns,
            "ctime_ns": after.st_ctime_ns,
        }
        if facts != after_facts or (after.st_dev, after.st_ino) != (
            named_after.st_dev, named_after.st_ino
        ):
            raise RuntimeError("source identity changed")
        value = digest.hexdigest()
        with self._lock:
            memo = self._load_memo()
            memo[key] = {**after_facts, "sha256": value}
            target = self._memo_path()
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            tmp.write_text(json.dumps(memo, indent=1, sort_keys=True), encoding="utf-8")
            os.replace(tmp, target)
        return value, after.st_size

    def _resource_contract(self, resource_id):
        contract = (self.params.get("resource_contracts") or {}).get(resource_id)
        required = {
            "event_time_column", "available_time_column", "timezone", "time_unit",
            "frequency",
        }
        if not isinstance(contract, dict) or set(contract) != required:
            raise UnsupportedError("resource availability contract required")
        for name in ("event_time_column", "available_time_column", "timezone", "frequency"):
            if not isinstance(contract[name], str) or not contract[name]:
                raise UnsupportedError(f"invalid resource contract {name}")
        if contract["timezone"] not in {"UTC", "NAIVE_WALL_CLOCK"}:
            raise UnsupportedError("invalid resource contract timezone")
        if contract["time_unit"] not in {None, "s", "ms", "us", "ns"}:
            raise UnsupportedError("invalid resource contract time_unit")
        return contract

    def _open_resource(self, resource_id):
        parts = str(resource_id or "").split("/")
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise FileNotFoundError(str(resource_id or ""))
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        directory = os.open(self._root(), flags | getattr(os, "O_DIRECTORY", 0))
        try:
            for part in parts[:-1]:
                child = os.open(
                    part, flags | getattr(os, "O_DIRECTORY", 0), dir_fd=directory
                )
                os.close(directory)
                directory = child
            fd = os.open(parts[-1], flags, dir_fd=directory)
        except (FileNotFoundError, NotADirectoryError, OSError) as exc:
            raise FileNotFoundError(str(resource_id or "")) from exc
        finally:
            os.close(directory)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise FileNotFoundError(str(resource_id or ""))
        return fd

    @staticmethod
    def _contract_time(series, *, time_unit, timezone_mode):
        import pandas as pd

        try:
            if pd.api.types.is_datetime64_any_dtype(series):
                out = series
            elif pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                if time_unit is None:
                    raise UnparseableError("unparseable time column")
                out = pd.to_datetime(series, unit=time_unit, utc=(timezone_mode == "UTC"))
            else:
                out = pd.to_datetime(series, format="ISO8601", utc=(timezone_mode == "UTC"))
        except (ValueError, TypeError, OverflowError) as exc:
            raise UnparseableError("unparseable time column") from exc
        if out.isna().any():
            raise UnparseableError("unparseable time column")
        if out.dt.tz is not None:
            out = (
                out.dt.tz_convert("UTC").dt.tz_localize(None)
                if timezone_mode == "UTC"
                else out.dt.tz_localize(None)
            )
        return out.reset_index(drop=True)

    def _contract_blocks(self, fd, suffix, column, contract):
        handle = os.fdopen(os.dup(fd), "rb")
        if suffix == ".parquet":
            import pyarrow.parquet as pq

            reader = pq.ParquetFile(handle)
            if column not in reader.schema_arrow.names:
                handle.close()
                raise UnsupportedError("available_time column missing")
            try:
                for batch in reader.iter_batches(
                    batch_size=CHUNK_ROWS, columns=[column]
                ):
                    values = batch.column(0).to_pandas()
                    yield self._contract_time(
                        values, time_unit=contract["time_unit"],
                        timezone_mode=contract["timezone"],
                    )
            finally:
                handle.close()
            return
        import pandas as pd

        try:
            with handle:
                with pd.read_csv(handle, usecols=[column], chunksize=CHUNK_ROWS) as chunks:
                    for chunk in chunks:
                        yield self._contract_time(
                            chunk[column], time_unit=contract["time_unit"],
                            timezone_mode=contract["timezone"],
                        )
        except ValueError as exc:
            raise UnsupportedError("available_time column missing") from exc

    def _contract_mask(self, fd, suffix, column, contract, lo=None, hi=None):
        import numpy as np

        masks, maximum = [], None
        for block in self._contract_blocks(fd, suffix, column, contract):
            keep = np.ones(len(block), dtype=bool) if lo is None else (
                (block >= lo) & (block < hi)
            ).to_numpy()
            masks.append(keep)
            if len(block):
                top = block.max()
                maximum = top if maximum is None or top > maximum else maximum
        return (np.concatenate(masks) if masks else np.zeros(0, dtype=bool)), maximum

    @staticmethod
    def _sha256_fd(fd):
        digest = hashlib.sha256()
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            block = os.read(fd, HASH_CHUNK)
            if not block:
                break
            digest.update(block)
        os.lseek(fd, 0, os.SEEK_SET)
        return digest.hexdigest()

    @staticmethod
    def _commit(part, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(part, target)
        except FileExistsError:
            def digest(path):
                out = hashlib.sha256()
                with open(path, "rb") as handle:
                    for block in iter(lambda: handle.read(HASH_CHUNK), b""):
                        out.update(block)
                return out.digest()

            if digest(part) != digest(target):
                raise RuntimeError("cut identity conflict")
        finally:
            part.unlink(missing_ok=True)

    def governed_download(self, resource_id, start=None, end=None):
        """Deliver bytes selected only by the declared availability timestamp."""
        contract = self._resource_contract(resource_id)
        suffix = Path(resource_id).suffix.lower()
        if suffix not in {".csv", ".parquet"}:
            raise UnsupportedError("unsupported file type")
        fd = self._open_resource(resource_id)
        try:
            source_sha = self._sha256_fd(fd)
            size = os.fstat(fd).st_size
            holdout = self._holdout()
            column = contract["available_time_column"]
            if (start is None) != (end is None):
                raise ValueError("invalid from/to")
            if start is None:
                _, available_max = self._contract_mask(
                    fd, suffix, column, contract
                )
                if holdout is not None and (
                    available_max is None or not available_max < holdout
                ):
                    raise HoldoutError("spans holdout: request a range")
                os.lseek(fd, 0, os.SEEK_SET)
                return {
                    "filename": Path(resource_id).name,
                    "sha256": source_sha,
                    "bytes": size,
                    "source_sha256": source_sha,
                    "delivery": "AS_IS",
                    "time_column": column,
                    "availability_contract_sha256": hashlib.sha256(
                        json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                    "handle": os.fdopen(fd, "rb"),
                }
            lo, hi = day_range(start, end)
            import pandas as pd

            if holdout is not None and hi - pd.Timedelta(days=1) >= holdout:
                raise HoldoutError("holdout")
            mask, _ = self._contract_mask(fd, suffix, column, contract, lo, hi)
            contract_sha = hashlib.sha256(
                json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            materializer_sha = hashlib.sha256(json.dumps({
                "schema": CUT_MATERIALIZER,
                "writer": PARQUET_WRITER if suffix == ".parquet" else "byte-line-subset.v1",
            }, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()
            target = (
                self.cuts_dir() / source_sha / contract_sha / materializer_sha
                / f"{start}_{end}{suffix}"
            )
            if not mask.all():
                part = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
                part.parent.mkdir(parents=True, exist_ok=True)
                try:
                    source = os.fdopen(os.dup(fd), "rb")
                    if suffix == ".parquet":
                        _cut_parquet(source, part, mask)
                    else:
                        _cut_csv(source, part, mask)
                    source.close()
                    self._commit(part, target)
                except BaseException:
                    part.unlink(missing_ok=True)
                    raise
            else:
                os.lseek(fd, 0, os.SEEK_SET)
                return {
                    "filename": Path(resource_id).name, "sha256": source_sha,
                    "bytes": size, "source_sha256": source_sha, "delivery": "AS_IS",
                    "time_column": column, "availability_contract_sha256": contract_sha,
                    "handle": os.fdopen(fd, "rb"),
                }
        except BaseException:
            os.close(fd)
            raise
        os.close(fd)
        out_fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        cut_sha = self._sha256_fd(out_fd)
        return {
            "filename": target.name, "sha256": cut_sha,
            "bytes": os.fstat(out_fd).st_size, "source_sha256": source_sha,
            "delivery": "CUT", "time_column": column,
            "availability_contract_sha256": contract_sha,
            "handle": os.fdopen(out_fd, "rb"),
        }

    def coverage(self, resource_id: str):
        path = self._path(resource_id)
        col = self._time_col(resource_id, path)
        if col is None:
            return {
                "resource_id": resource_id,
                "rows": self._count_rows(path),
                "t_min": None,
                "t_max": None,
            }
        rows, t_min, t_max = self._scan(path, col)
        return {
            "resource_id": resource_id,
            "rows": int(rows),
            "t_min": None if t_min is None else str(t_min),
            "t_max": None if t_max is None else str(t_max),
            "time_column": col,
        }

    def download(self, resource_id: str, start=None, end=None):
        """A file on this disk and its sha256: the source AS_IS or a materialised CUT."""
        path = self._path(resource_id)
        holdout = self._holdout()
        col = self._time_col(resource_id, path)

        def as_is():
            digest, size = self.sha256(path)
            return {
                "path": str(path),
                "filename": path.name,
                "sha256": digest,
                "bytes": size,
                "source_sha256": digest,
                "delivery": "AS_IS",
                "time_column": col or "",
            }

        if col is None:
            if holdout is not None and resource_id not in (self.params.get("untimed") or []):
                raise HoldoutError("no time column under holdout")
            return as_is()
        if start is None and end is None:
            if holdout is not None:
                _, _, t_max = self._scan(path, col)
                if t_max is None or not t_max < holdout:
                    raise HoldoutError("spans holdout: request a range")
            return as_is()
        import pandas as pd

        lo, hi = day_range(start, end)
        if holdout is not None and hi - pd.Timedelta(days=1) >= holdout:
            raise HoldoutError("holdout")  # to >= holdout_start, re-checked here
        mask, kept_max = self._keep_mask(path, col, lo, hi)
        if holdout is not None and kept_max is not None and not kept_max < holdout:
            raise HoldoutError("holdout")
        if mask.all():
            return as_is()
        source_sha, _ = self.sha256(path)
        cut = self.cuts_dir() / source_sha / f"{start}_{end}{path.suffix.lower()}"
        with self._lock:
            if not cut.is_file():
                cut.parent.mkdir(parents=True, exist_ok=True)
                part = cut.with_name(cut.name + ".part")
                try:
                    if path.suffix.lower() == ".parquet":
                        _cut_parquet(path, part, mask)
                    else:
                        _cut_csv(path, part, mask)
                except BaseException:
                    part.unlink(missing_ok=True)
                    raise
                os.replace(part, cut)
        digest, size = self.sha256(cut)
        return {
            "path": str(cut),
            "filename": cut.name,
            "sha256": digest,
            "bytes": size,
            "source_sha256": source_sha,
            "delivery": "CUT",
            "time_column": col,
        }

    def read(self, resource_id: str, start=None, end=None):
        col = self._time_col(resource_id, self._path(resource_id))
        if col is None and self._holdout() is not None and resource_id not in (self.params.get("untimed") or []):
            # same rule as download: without a time column nothing proves the rows end before the holdout
            raise HoldoutError("no time column under holdout")
        frame = self._frame(resource_id)
        if start is not None or end is not None:
            lo, hi = day_range(start, end)
            if col is not None:
                times = wall_clock(frame[col])
                frame = frame[((times >= lo) & (times < hi)).to_numpy()]
        payload = frame.to_dict(orient="records")
        canonical = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":"))
        return {
            "resource_id": resource_id,
            "rows": payload,
            "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "bytes": len(canonical.encode()),
        }

    def storage(self):
        import shutil

        root = self._root()
        usage = shutil.disk_usage(root)
        lake_bytes = sum(item["bytes"] for item in self.discover())
        return {
            "root": str(root),
            "host_total": usage.total,
            "host_used": usage.used,
            "host_free": usage.free,
            "lake_bytes": lake_bytes,
        }

    def describe(self):
        return {
            "lake_id": self.params.get("lake_id"),
            "title": self.params.get("title"),
            "description": self.params.get("description"),
            "kind": self.params.get("kind"),
            "root_path": str(self._root()),
            "holdout_start": self.params.get("holdout_start"),
            "n_resources": len(self.discover()),
        }
