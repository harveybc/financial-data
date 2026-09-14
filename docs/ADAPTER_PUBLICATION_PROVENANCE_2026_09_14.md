# Adapter publication provenance

Date: 2026-09-14. Maintainer disposition: selected-content publication accepted;
no whole-branch merge required and no runtime restart required.

The lake adapter on master intentionally includes selected files from the
research branch. This is not a claim that the entire research branch has
been merged or reviewed. Git ancestry and file-content identity are distinct.

Published revision: `cc0f15e6ef9cf79c1fb47bd7d7731eb349831008`.
Source revision: `f00bc6c151392d3cc3193f24a1c797c7ba7988d8`.

These three files were compared directly between those Git revisions and
are byte-identical:

| Path | SHA-256 |
|---|---|
| `lake/inventory_plugins/fs_inventory.py` | `3ea4ab5533405a044f71eacabe5d57dde9addf0244af4fbc8bdfd9918acb6a87` |
| `lake/web_plugins/default_web.py` | `4f88c0803a8dcabbf3c0bc2960347c4ca6b90346b4c24611bb149a846f0dcc8a` |
| `lake/tests/test_availability_scope_v2.py` | `e01d2da0f85e5bfe46989f6dde5b2acc74d32f87f250bbca8b39ab8ed4dabe8f` |

The full revisions are NOT tree-identical: the comparison contains 80 changed
paths, including research scripts, census artifacts and documentation. Do not
describe an ordinary whole-branch merge as byte-neutral. Do not manufacture
ancestry using a merge that discards the other branch's contents while implying
that its changes have been integrated.

The publication README and runtime receipt already identify the selected
adapter scope. This record makes the per-file mapping explicit. A future
research merge needs its own scope and tests; it is not a prerequisite for
using this tested adapter or implementing the external financial-data plugin.

Reproduction:

```bash
git diff --exit-code cc0f15e6ef9cf79c1fb47bd7d7731eb349831008 \
  f00bc6c151392d3cc3193f24a1c797c7ba7988d8 -- \
  lake/inventory_plugins/fs_inventory.py \
  lake/web_plugins/default_web.py \
  lake/tests/test_availability_scope_v2.py
```

This documentation-only disposition neither changes the deployed code nor
grants a scientific data-use license.
