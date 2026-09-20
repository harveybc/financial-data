"""`financial_files` — the financial lake as an installable backend of a lake host.

This package owns the domain: what a resource is, where its bytes live, the producer
contract that declares its time semantics and availability, and the cut that applies
them. It owns no HTTP route, no console and no governance decision.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .inventory import Plugin as _Inventory

CAPABILITIES = ("describe", "storage", "discover", "coverage", "read",
                "download", "governed_download")

#: The domain defaults that shape the inventory. They used to live in the lake application's
#: `app/config.py` and were merged in by the legacy host, so a generic host that only passed
#: the runtime file inventoried 16,346 resources where the deployed service inventories
#: 5,275 (found by the deployment dry run on 2026-09-14). What a resource *is* belongs to
#: this provider, not to whichever host loads it.
DEFAULT_SETTINGS = {
    "include_globs": [
        "market_data/**/*.parquet", "market_data/**/*.csv",
        "macro_economic/**/*.parquet", "macro_economic/**/*.csv",
        "alternative_data/**/*.parquet", "alternative_data/**/*.csv",
        "reference_data/**/*.parquet", "reference_data/**/*.csv",
        "economic_calendar/**/*.parquet", "economic_calendar/**/*.csv",
        "derivatives/**/*.parquet", "fundamental/**/*.parquet",
        "microstructure/**/*.parquet", "features/**/*.parquet", "features/**/*.csv",
    ],
    "time_column": None,
    "time_columns": {},
    "untimed": [],
    "resource_contracts": {},
    "holdout_start": "2025-01-01",
    "max_downloads": 2,
    "kind": "files_inventory",
}


def _source_commit() -> str | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            try:
                out = subprocess.run(["git", "-C", str(parent), "rev-parse", "HEAD"],
                                     capture_output=True, text=True, timeout=10)
                if out.returncode == 0:
                    return out.stdout.strip()
            except OSError:
                return None
            return None
    return None


class FinancialStore(_Inventory):
    """The deployed inventory plus what a host asks of a backend: capabilities and identity."""

    def __init__(self):
        super().__init__()
        self.params.update(DEFAULT_SETTINGS)

    def capabilities(self):
        return CAPABILITIES

    def source_identity(self):
        from . import __version__

        return {"kind": "python_distribution", "distribution": "financial-data-store",
                "version": __version__, "module": __name__, "source_commit": _source_commit()}


def backend():
    return FinancialStore()
