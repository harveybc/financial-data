"""The packaged provider must not drift from the inventory the service actually runs."""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEPLOYED = REPO / "lake" / "inventory_plugins" / "fs_inventory.py"
PACKAGED = REPO / "store" / "src" / "financial_data_store" / "inventory.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_packaged_inventory_is_the_deployed_inventory():
    assert DEPLOYED.is_file() and PACKAGED.is_file()
    assert _sha256(PACKAGED) == _sha256(DEPLOYED), (
        "the provider copy and the running inventory differ; make the change in one place "
        "and copy it, or finish the migration and delete the copy")


def test_the_provider_declares_the_capabilities_the_inventory_implements():
    import sys

    sys.path.insert(0, str(REPO / "store" / "src"))
    from financial_data_store.provider import CAPABILITIES, FinancialStore

    store = FinancialStore()
    for capability in CAPABILITIES:
        assert callable(getattr(store, capability)), capability
    assert store.capabilities() == CAPABILITIES
    identity = store.source_identity()
    assert identity["distribution"] == "financial-data-store"
