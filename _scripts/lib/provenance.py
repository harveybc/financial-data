from __future__ import annotations

import sys
from pathlib import Path

WORKERS_DIR = Path(__file__).resolve().parents[1] / "workers"
if str(WORKERS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKERS_DIR))

from stage13_common import sha256_file  # noqa: E402,F401

