from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(os.environ.get("PROJECT3_ROOT", "/home/harveybc/Documents/GitHub/financial-data"))
TARGET_TIMEFRAMES = ("5m", "15m", "1h", "4h")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def parquet_summary(path: Path) -> dict[str, Any]:
    try:
        parquet_file = pq.ParquetFile(path)
        columns = list(parquet_file.schema.names)
        row_count = int(parquet_file.metadata.num_rows)
    except Exception:
        columns = []
        row_count = None
    try:
        df = pd.read_parquet(path, columns=["timestamp"])
    except Exception:
        return {
            "path": rel(path),
            "status": "ok_metadata_only" if columns else "failed",
            "rows": row_count,
            "start": None,
            "end": None,
            "columns": columns,
        }
    timestamp = pd.to_datetime(df["timestamp"], utc=True, errors="coerce") if "timestamp" in df.columns else None
    return {
        "path": rel(path),
        "status": "ok",
        "rows": row_count if row_count is not None else int(len(df)),
        "start": timestamp.min().isoformat() if timestamp is not None and timestamp.notna().any() else None,
        "end": timestamp.max().isoformat() if timestamp is not None and timestamp.notna().any() else None,
        "columns": columns or list(df.columns),
    }


def trading_assets() -> dict[str, Any]:
    root = ROOT / "features" / "trading_asset_data"
    out: dict[str, Any] = {}
    if not root.exists():
        return out
    for asset_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        tfs: dict[str, Any] = {}
        for tf in TARGET_TIMEFRAMES:
            path = asset_dir / f"{tf}.parquet"
            if path.exists():
                tfs[tf] = parquet_summary(path)
            else:
                tfs[tf] = {"status": "missing"}
        out[asset_dir.name] = {"timeframes": tfs}
    return out


def cross_source_features() -> dict[str, Any]:
    root = ROOT / "features" / "cross_source_features"
    out: dict[str, Any] = {}
    for tf in TARGET_TIMEFRAMES:
        tf_dir = root / tf
        items: dict[str, Any] = {}
        if tf_dir.exists():
            for path in sorted(tf_dir.glob("*.parquet")):
                items[path.stem] = parquet_summary(path)
        out[tf] = items
    return out


def write_features_readme(manifest: dict[str, Any]) -> None:
    root = ROOT / "features"
    root.mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text(
        "\n".join(
            [
                "# Project 3 Feature Library",
                "",
                "Generated Phase 2 feature and aligned-data outputs.",
                "",
                "- `trading_asset_data/`: Stage 2.1 canonical multi-timeframe OHLCV inputs.",
                "- `cross_source_features/`: Stage 2.1 point-in-time forward-filled macro, on-chain, calendar, funding, and market context inputs.",
                "- `MANIFEST.json`: machine-readable inventory used by later Phase 2 and Phase 3 workers.",
                "",
                f"Trading assets: {len(manifest['trading_assets'])}",
                f"Cross-source 5m files: {len(manifest['cross_source_features'].get('5m', {}))}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_deliverable(manifest: dict[str, Any]) -> None:
    path = ROOT / "STAGE_2.1_DELIVERABLE.md"
    trading_assets_count = len(manifest["trading_assets"])
    complete_assets = sum(
        all(item.get("status") == "ok" for item in data["timeframes"].values())
        for data in manifest["trading_assets"].values()
    )
    cross_counts = {tf: len(items) for tf, items in manifest["cross_source_features"].items()}
    lines = [
        "# Stage 2.1 Deliverable - Downsampling and Resampling",
        "",
        f"Generated: {manifest['generated_at']}",
        "",
        "## Trading Assets Processed",
        "",
        f"- Total trading assets: {trading_assets_count}",
        f"- Assets with all target timeframes: {complete_assets}",
        "",
        "| Asset | 5m | 15m | 1h | 4h |",
        "| --- | --- | --- | --- | --- |",
    ]
    for asset, data in sorted(manifest["trading_assets"].items()):
        row = [asset]
        for tf in TARGET_TIMEFRAMES:
            row.append(data["timeframes"].get(tf, {}).get("status", "missing"))
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(
        [
            "",
            "## Cross-Source Features Forward-Filled",
            "",
            f"- 5m files: {cross_counts.get('5m', 0)}",
            f"- 15m files: {cross_counts.get('15m', 0)}",
            f"- 1h files: {cross_counts.get('1h', 0)}",
            f"- 4h files: {cross_counts.get('4h', 0)}",
            "",
            "## Manifest",
            "",
            "- `features/MANIFEST.json`",
            "",
            "## Validation",
            "",
            "- Trading asset OHLC integrity and timestamp ordering were checked per worker.",
            "- Cross-source alignment uses point-in-time backward/as-of merge, so no future value is used.",
            "- No interpolation is used.",
            "",
            "## User Gate",
            "",
            "Stage 2.1 is ready for review once all machine reports are synced and this deliverable is current.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata_reports = {
        path.name: read_json(path, {})
        for path in sorted((ROOT / "_metadata").glob("stage21_*.json"))
    }
    manifest = {
        "generated_at": utc_now(),
        "stage": "Stage 2.1",
        "trading_assets": trading_assets(),
        "cross_source_features": cross_source_features(),
        "worker_reports": metadata_reports,
    }
    out = ROOT / "features" / "MANIFEST.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (ROOT / "_metadata" / "stage21_manifest.json").write_text(
        json.dumps(
            {
                "generated_at": manifest["generated_at"],
                "trading_assets": len(manifest["trading_assets"]),
                "cross_source_counts": {tf: len(items) for tf, items in manifest["cross_source_features"].items()},
                "manifest_path": rel(out),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    write_features_readme(manifest)
    write_deliverable(manifest)
    report = ROOT / "_logs" / "supervisor_reports" / "stage21_manifest.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# Stage 2.1 Manifest",
                "",
                f"Generated: {manifest['generated_at']}",
                "",
                f"- Trading assets: {len(manifest['trading_assets'])}",
                f"- Cross-source counts: {json.dumps({tf: len(items) for tf, items in manifest['cross_source_features'].items()}, sort_keys=True)}",
                "- Manifest: `features/MANIFEST.json`",
                "- Deliverable: `STAGE_2.1_DELIVERABLE.md`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
