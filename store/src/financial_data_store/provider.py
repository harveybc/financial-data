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

    def capabilities(self):
        return CAPABILITIES

    def source_identity(self):
        from . import __version__

        return {"kind": "python_distribution", "distribution": "financial-data-store",
                "version": __version__, "module": __name__, "source_commit": _source_commit()}


def backend():
    return FinancialStore()
