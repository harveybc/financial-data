from __future__ import annotations

import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_line(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def load_env(env_path: Path | None = None) -> None:
    env_path = env_path or ROOT / "_metadata" / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_table(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        try:
            df.to_parquet(path, index=False)
            return
        except Exception:
            path = path.with_suffix(".csv")
    df.to_csv(path, index=False)


def write_docs(folder: Path, source: str, description: str, files: Iterable[Path]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    file_list = [p for p in files if p.exists()]
    (folder / "README.md").write_text(
        f"# {folder.name}\n\n{description}\n\nSource: {source}\nAcquired: {utc_now()}\n",
        encoding="utf-8",
    )
    (folder / "data_dictionary.md").write_text(
        "# Data Dictionary\n\nColumns follow source naming unless normalized by the acquisition script.\n",
        encoding="utf-8",
    )
    provenance = {
        "source": source,
        "description": description,
        "acquired_at": utc_now(),
        "files": [
            {"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p)} for p in file_list
        ],
    }
    (folder / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")


def append_acquisition_log(row: dict[str, str]) -> None:
    path = ROOT / "_metadata" / "acquisition_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    fields = ["timestamp", "source", "dataset", "status", "path", "notes"]
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in fields})


def polite_sleep(seconds: float) -> None:
    time.sleep(seconds)
