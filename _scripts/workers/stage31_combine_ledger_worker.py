#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
sys.path.insert(0, str(PROJECT_ROOT / "_scripts" / "lib"))

from experiment_ledger import combine_ledgers  # noqa: E402


def main() -> int:
    summary = combine_ledgers()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
