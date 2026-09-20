"""The financial file inventory, packaged as a provider for a reusable lake host.

The module `financial_data_store.inventory` is the deployed inventory verbatim
(`financial-data/lake/inventory_plugins/fs_inventory.py`). It is copied, not rewritten, so
that the provider and the running service cannot drift silently: `tests/test_parity.py`
compares their SHA-256 and fails when they differ. The copy disappears when the host
migration completes and the service loads this package instead.
"""

from .provider import FinancialStore, backend

__all__ = ["FinancialStore", "backend", "__version__"]
__version__ = "0.1.0"
