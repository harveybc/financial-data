"""Walk data roots with stat() only. Content hash happens on read."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


class Plugin:
    plugin_params = {
        "root_path": ".",
        "include_globs": ["**/*.parquet", "**/*.csv"],
        "holdout_start": "2025-01-01",
        "time_column": None,
        "lake_id": "financial_files",
        "title": "financial-data",
        "description": "",
        "kind": "files_inventory",
    }

    def __init__(self):
        self.params = dict(self.plugin_params)
        self._cache = None

    def set_params(self, **kwargs):
        self.params.update(kwargs)
        self._cache = None

    def _root(self) -> Path:
        return Path(self.params.get("root_path") or ".").resolve()

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

    def _frame(self, resource_id: str):
        import pandas as pd

        path = self._root() / resource_id
        if not path.is_file():
            raise FileNotFoundError(resource_id)
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)

    def _time_col(self, frame):
        named = self.params.get("time_column")
        if named and named in frame.columns:
            return named
        for col in frame.columns:
            lower = col.lower()
            if lower in {"ts", "time", "date", "datetime", "timestamp"} or "time" in lower or "date" in lower:
                return col
        return None

    def coverage(self, resource_id: str):
        frame = self._frame(resource_id)
        col = self._time_col(frame)
        if col is None:
            return {
                "resource_id": resource_id,
                "rows": int(len(frame)),
                "t_min": None,
                "t_max": None,
            }
        series = frame[col]
        return {
            "resource_id": resource_id,
            "rows": int(len(frame)),
            "t_min": str(series.min()),
            "t_max": str(series.max()),
            "time_column": col,
        }

    def read(self, resource_id: str, start=None, end=None):
        import pandas as pd

        frame = self._frame(resource_id)
        col = self._time_col(frame)
        if col and (start or end):
            times = pd.to_datetime(frame[col], utc=True)
            mask = pd.Series(True, index=frame.index)
            if start:
                mask &= times >= pd.Timestamp(start, tz="UTC")
            if end:
                mask &= times <= pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1)
            frame = frame.loc[mask]
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
