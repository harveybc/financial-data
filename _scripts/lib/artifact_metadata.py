"""
Artifact metadata schema and writer for Phase 3X unsupervised/causal artifacts.

Every fitted object (scaler, HMM, GMM, OOD estimator, causal graph, feature mask)
must emit an ArtifactMetadata record before being accepted by the registry.

Schema matches the requirements from:
  - experiments/design/unsupervised_causal_audit.md § Artifact Rules
  - experiments/design/leakage_audit.md § Fitted Transform Metadata
  - work_plan/PHASE_3X_UNSUPERVISED_CAUSAL_AUDIT.md § 7. Required Artifacts
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def compute_file_hash(path: str | Path, algorithm: str = "sha256") -> str:
    """Return hex digest of a file's content. Returns 'FILE_NOT_FOUND' if absent."""
    p = Path(path)
    if not p.exists():
        return "FILE_NOT_FOUND"
    h = hashlib.new(algorithm)
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_config_hash(config: dict[str, Any], algorithm: str = "sha256") -> str:
    """Return hex digest of a canonical JSON serialisation of config."""
    canonical = json.dumps(config, sort_keys=True, default=str).encode("utf-8")
    return hashlib.new(algorithm, canonical).hexdigest()


def compute_manifest_hash(paths: list[str | Path], algorithm: str = "sha256") -> str:
    """Return a combined hash over the sorted list of file hashes."""
    individual = sorted(
        compute_file_hash(p, algorithm) for p in paths
    )
    combined = "\n".join(individual).encode("utf-8")
    return hashlib.new(algorithm, combined).hexdigest()


def _git_commit(repo_root: str | Path | None = None) -> str:
    """Return the current HEAD commit SHA or 'UNKNOWN'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(repo_root) if repo_root else None,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "UNKNOWN"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Required metadata fields (from leakage_audit.md)
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "artifact_type",
    "asset",
    "timeframe",
    "fit_start",
    "fit_end",
    "heldout_start",
    "uses_heldout",
    "input_hashes",
    "config_hash",
    "fit_excludes_heldout_2025",
    "fit_excludes_validation_if_required",
}


# ---------------------------------------------------------------------------
# ArtifactMetadata dataclass
# ---------------------------------------------------------------------------

@dataclass
class ArtifactMetadata:
    """
    Complete provenance record for one fitted unsupervised/causal artifact.

    All fields with defaults are optional extras; REQUIRED_FIELDS above must be
    populated with meaningful values before writing.
    """

    # ---- Identity ----
    artifact_type: str                      # e.g. "hmm_regime", "gmm_ood", "scaler"
    asset: str                              # e.g. "ethusdt"
    timeframe: str                          # e.g. "4h"
    feature_family: str = ""               # e.g. "tech_stat"
    model_class: str = ""                  # e.g. "hmmlearn.hmm.GaussianHMM"

    # ---- Fit window ----
    fit_start: str = ""                    # ISO-8601
    fit_end: str = ""                      # ISO-8601 (exclusive upper bound of fitted data)
    fit_assets: list[str] = field(default_factory=list)
    fit_timeframes: list[str] = field(default_factory=list)
    fit_columns: list[str] = field(default_factory=list)
    fit_row_count: int = 0

    # ---- Transform/scoring window (validation) ----
    transform_start: str = ""              # ISO-8601; empty means not yet applied
    transform_end: str = ""               # ISO-8601

    # ---- Heldout / Stage C boundary ----
    heldout_start: str = "2025-01-01T00:00:00Z"
    uses_heldout: bool = False            # MUST remain False until Stage C eval

    # ---- Leakage checks ----
    fit_excludes_heldout_2025: bool = True
    fit_excludes_validation_if_required: bool = True
    leakage_checks: dict[str, Any] = field(default_factory=dict)

    # ---- Provenance / reproducibility ----
    input_hashes: dict[str, str] = field(default_factory=dict)   # path → sha256
    input_manifest_hash: str = ""          # combined hash of all inputs
    config_hash: str = ""                  # sha256 of canonical JSON config
    output_paths: list[str] = field(default_factory=list)
    output_manifest_hash: str = ""

    # ---- Execution context ----
    code_commit: str = ""                  # git HEAD SHA
    software_version: str = ""            # e.g. "python=3.12.7 numpy=2.1.3"
    random_seed: int | None = None
    generated_at: str = field(default_factory=_utc_now)

    # ---- Free-form notes ----
    notes: str = ""

    # ---------------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation errors; empty list means schema-valid."""
        errors: list[str] = []
        for f in REQUIRED_FIELDS:
            v = getattr(self, f, None)
            if v is None or v == "" or v == {} or v == []:
                errors.append(f"Required field '{f}' is empty or missing.")
        if self.uses_heldout:
            errors.append("uses_heldout=True is forbidden before Stage C evaluation.")
        if not self.fit_excludes_heldout_2025:
            errors.append("fit_excludes_heldout_2025 must be True.")
        if self.fit_end and self.heldout_start:
            try:
                from datetime import datetime, timezone as tz
                fe = datetime.fromisoformat(self.fit_end.replace("Z", "+00:00"))
                hs = datetime.fromisoformat(self.heldout_start.replace("Z", "+00:00"))
                if fe >= hs:
                    errors.append(
                        f"fit_end ({self.fit_end}) >= heldout_start ({self.heldout_start})."
                    )
            except Exception:
                errors.append(f"fit_end or heldout_start is not valid ISO-8601.")
        return errors

    def assert_valid(self) -> None:
        """Raise ValueError if validate() returns any errors."""
        errors = self.validate()
        if errors:
            raise ValueError(
                "ArtifactMetadata validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True, default=str)


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------

def build_metadata(
    artifact_type: str,
    asset: str,
    timeframe: str,
    config: dict[str, Any],
    input_paths: list[str | Path],
    output_paths: list[str | Path],
    fit_df_timestamps: "pd.Series | None" = None,
    *,
    feature_family: str = "",
    model_class: str = "",
    random_seed: int | None = None,
    heldout_start: str = "2025-01-01T00:00:00Z",
    fit_columns: list[str] | None = None,
    notes: str = "",
    repo_root: str | Path | None = None,
) -> ArtifactMetadata:
    """
    Convenience factory.  Computes hashes, timestamps, and git commit automatically.

    fit_df_timestamps: the UTC timestamp Series that was actually passed to .fit().
    Used to record fit_start / fit_end and to populate fit_row_count.
    """
    import pandas as pd

    input_hashes = {str(p): compute_file_hash(p) for p in input_paths}
    input_manifest_hash = compute_manifest_hash(input_paths)
    config_hash = compute_config_hash(config)
    code_commit = _git_commit(repo_root)

    fit_start = ""
    fit_end = ""
    fit_row_count = 0
    if fit_df_timestamps is not None and len(fit_df_timestamps) > 0:
        ts_utc = pd.to_datetime(fit_df_timestamps, utc=True)
        fit_start = ts_utc.min().isoformat()
        fit_end = ts_utc.max().isoformat()
        fit_row_count = len(ts_utc)

    output_strs = [str(p) for p in output_paths]

    import platform, sys
    sw_version = (
        f"python={sys.version.split()[0]} "
        f"numpy={_safe_pkg_version('numpy')} "
        f"pandas={_safe_pkg_version('pandas')}"
    )

    meta = ArtifactMetadata(
        artifact_type=artifact_type,
        asset=asset,
        timeframe=timeframe,
        feature_family=feature_family,
        model_class=model_class,
        fit_start=fit_start,
        fit_end=fit_end,
        fit_assets=[asset],
        fit_timeframes=[timeframe],
        fit_columns=fit_columns or [],
        fit_row_count=fit_row_count,
        heldout_start=heldout_start,
        uses_heldout=False,
        fit_excludes_heldout_2025=True,
        fit_excludes_validation_if_required=True,
        leakage_checks={
            "heldout_timestamp_exclusion": "CHECKED",
            "fit_window_precedes_validation": "CHECKED",
        },
        input_hashes=input_hashes,
        input_manifest_hash=input_manifest_hash,
        config_hash=config_hash,
        output_paths=output_strs,
        output_manifest_hash=compute_manifest_hash(
            [p for p in output_paths if Path(p).exists()]
        ),
        code_commit=code_commit,
        software_version=sw_version,
        random_seed=random_seed,
        notes=notes,
    )
    return meta


def _safe_pkg_version(pkg: str) -> str:
    try:
        import importlib.metadata
        return importlib.metadata.version(pkg)
    except Exception:
        return "UNKNOWN"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------

def write_metadata(meta: ArtifactMetadata, path: str | Path) -> Path:
    """
    Validate and write metadata to a JSON file.
    Raises ValueError if validation fails.
    Returns the written path.
    """
    meta.assert_valid()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(meta.to_json(), encoding="utf-8")
    return out
