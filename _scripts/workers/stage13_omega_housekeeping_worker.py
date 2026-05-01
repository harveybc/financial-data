from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from stage13_deliverable_validator_worker import main as validate_deliverables
from stage13_omega_doc_backfill_worker import main as backfill_docs
from stage13_omega_validation_inventory_worker import main as refresh_inventory


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")
LOG = ROOT / "_logs" / "omega" / "stage13_housekeeping_worker.log"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def main() -> None:
    log("START omega housekeeping worker")
    backfill_docs()
    refresh_inventory()
    validate_deliverables()
    log("DONE omega housekeeping worker")


if __name__ == "__main__":
    main()
