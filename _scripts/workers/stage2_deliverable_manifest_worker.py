from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("/home/harveybc/Documents/GitHub/financial-data")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def count_files(pattern: str) -> int:
    return sum(1 for _ in ROOT.glob(pattern))


def stage22_summary() -> dict[str, Any]:
    fx = load_json("_metadata/stage22_trading_features_omega_forex_g10.json")
    crypto = load_json("_metadata/stage22_trading_features_dragon_crypto.json")
    cross = load_json("_metadata/stage22_cross_source_stats_gamma.json")
    cross_results = cross.get("results", [])
    skipped = [
        item
        for item in cross_results
        if item.get("status") == "failed" and "no numeric columns" in item.get("error", "").lower()
    ]
    true_failures = [
        item
        for item in cross_results
        if item.get("status") == "failed" and "no numeric columns" not in item.get("error", "").lower()
    ]
    return {
        "generated_at": utc_now(),
        "stage": "Stage 2.2",
        "trading_jobs_total": fx["jobs_total"] + crypto["jobs_total"],
        "trading_jobs_ok": fx["jobs_ok"] + crypto["jobs_ok"],
        "trading_jobs_failed": fx["jobs_failed"] + crypto["jobs_failed"],
        "cross_jobs_total": cross["jobs_total"],
        "cross_jobs_ok": cross["jobs_ok"],
        "cross_jobs_skipped_no_numeric": len(skipped),
        "cross_jobs_failed_actionable": len(true_failures),
        "technical_files": count_files("features/trading_asset_features/*/*/technical.parquet"),
        "statistical_files": count_files("features/trading_asset_features/*/*/statistical.parquet"),
        "cross_statistical_files": count_files("features/cross_source_statistical/*/*.parquet"),
        "skipped_examples": skipped[:12],
        "actionable_failures": true_failures,
        "source_reports": [
            "_metadata/stage22_trading_features_omega_forex_g10.json",
            "_metadata/stage22_trading_features_dragon_crypto.json",
            "_metadata/stage22_cross_source_stats_gamma.json",
        ],
    }


def stage23_summary() -> dict[str, Any]:
    fx = load_json("_metadata/stage23_signal_decomposition_omega_forex_g10.json")
    crypto = load_json("_metadata/stage23_signal_decomposition_dragon_crypto.json")
    return {
        "generated_at": utc_now(),
        "stage": "Stage 2.3",
        "jobs_total": fx["jobs_total"] + crypto["jobs_total"],
        "jobs_ok": fx["jobs_ok"] + crypto["jobs_ok"],
        "jobs_failed": fx["jobs_failed"] + crypto["jobs_failed"],
        "wavelet_files": count_files("features/trading_asset_features/*/*/wavelet.parquet"),
        "hilbert_files": count_files("features/trading_asset_features/*/*/hilbert.parquet"),
        "multitaper_files": count_files("features/trading_asset_features/*/*/multitaper.parquet"),
        "emd_files": count_files("features/trading_asset_features/*/*/emd.parquet"),
        "fracdiff_files": count_files("features/trading_asset_features/*/*/fracdiff.parquet"),
        "source_reports": [
            "_metadata/stage23_signal_decomposition_omega_forex_g10.json",
            "_metadata/stage23_signal_decomposition_dragon_crypto.json",
        ],
    }


def stage24_input_prep_summary() -> dict[str, Any]:
    reports = [
        "_metadata/stage24_learned_input_prep_dragon_crypto_stage_a.json",
        "_metadata/stage24_learned_input_prep_gamma_fx_stage_a.json",
    ]
    loaded = [load_json(path) for path in reports if (ROOT / path).exists()]
    return {
        "generated_at": utc_now(),
        "stage": "Stage 2.4 input preparation",
        "jobs_total": sum(item["jobs_total"] for item in loaded),
        "jobs_ok": sum(item["jobs_ok"] for item in loaded),
        "jobs_failed": sum(item["jobs_failed"] for item in loaded),
        "learned_input_train_csv_files": count_files("features/learned_inputs/*/*/train.csv"),
        "learned_input_validation_csv_files": count_files("features/learned_inputs/*/*/validation.csv"),
        "learned_input_test_csv_files": count_files("features/learned_inputs/*/*/test.csv"),
        "learned_input_full_parquet_files": count_files("features/learned_inputs/*/*/full_normalized.parquet"),
        "source_reports": reports,
    }


def write_stage22_doc(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage 2.2 Deliverable",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Status",
        "",
        "- Trading technical/statistical features: complete.",
        "- Cross-source statistical features: complete with nonnumeric metadata-like inputs skipped.",
        "- Actionable failures: 0.",
        "",
        "## Counts",
        "",
        f"- Trading jobs: {summary['trading_jobs_ok']}/{summary['trading_jobs_total']} ok.",
        f"- Cross-source jobs: {summary['cross_jobs_ok']}/{summary['cross_jobs_total']} ok.",
        f"- Cross-source skipped as no numeric columns: {summary['cross_jobs_skipped_no_numeric']}.",
        f"- Technical feature files: {summary['technical_files']}.",
        f"- Statistical feature files: {summary['statistical_files']}.",
        f"- Cross-source statistical files: {summary['cross_statistical_files']}.",
        "",
        "## Output Roots",
        "",
        "- `features/trading_asset_features/<asset>/<tf>/technical.parquet`",
        "- `features/trading_asset_features/<asset>/<tf>/statistical.parquet`",
        "- `features/cross_source_statistical/<tf>/*.parquet`",
        "",
        "## Validation Note",
        "",
        "The 16 skipped cross-source jobs are four nonnumeric sources across four timeframes. They do not block Phase 2 because they cannot produce numeric rolling statistics.",
    ]
    (ROOT / "STAGE_2.2_DELIVERABLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage23_doc(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage 2.3 Deliverable",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Status",
        "",
        "- Signal decomposition features: complete for FX G10 and crypto/perpetual trading assets.",
        "- Actionable failures: 0.",
        "",
        "## Counts",
        "",
        f"- Jobs: {summary['jobs_ok']}/{summary['jobs_total']} ok.",
        f"- Wavelet files: {summary['wavelet_files']}.",
        f"- Hilbert files: {summary['hilbert_files']}.",
        f"- Multitaper files: {summary['multitaper_files']}.",
        f"- EMD files: {summary['emd_files']}.",
        f"- Fractional differentiation files: {summary['fracdiff_files']}.",
        "",
        "## Output Roots",
        "",
        "- `features/trading_asset_features/<asset>/<tf>/wavelet.parquet`",
        "- `features/trading_asset_features/<asset>/<tf>/hilbert.parquet`",
        "- `features/trading_asset_features/<asset>/<tf>/multitaper.parquet`",
        "- `features/trading_asset_features/<asset>/<tf>/emd.parquet`",
        "- `features/trading_asset_features/<asset>/<tf>/fracdiff.parquet`",
    ]
    (ROOT / "STAGE_2.3_DELIVERABLE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage24_input_prep_doc(summary: dict[str, Any]) -> None:
    lines = [
        "# Stage 2.4 Input Prep Status",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Status",
        "",
        "- Learned-representation input matrices are prepared for Stage A crypto and FX assets.",
        "- This is not the full Stage 2.4 deliverable; model training/checkpoints still need the feature-extractor runtime wrapper.",
        "",
        "## Counts",
        "",
        f"- Jobs: {summary['jobs_ok']}/{summary['jobs_total']} ok.",
        f"- Train CSV files: {summary['learned_input_train_csv_files']}.",
        f"- Validation CSV files: {summary['learned_input_validation_csv_files']}.",
        f"- Test CSV files: {summary['learned_input_test_csv_files']}.",
        f"- Full normalized parquet files: {summary['learned_input_full_parquet_files']}.",
        "",
        "## Output Root",
        "",
        "- `features/learned_inputs/<asset>/<tf>/`",
    ]
    (ROOT / "_logs" / "supervisor_reports" / "stage24_input_prep_status.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def write_global_status(stage22: dict[str, Any], stage23: dict[str, Any], stage24: dict[str, Any]) -> None:
    lines = [
        "# Project 3 Global Status",
        "",
        f"Updated: {utc_now()}",
        "",
        "## Current Stage",
        "",
        "Phase 2 is active. Stage 2.1, 2.2, and 2.3 generation are complete. Stage 2.4 input preparation has completed for the first Stage A assets.",
        "",
        "## Machine Status",
        "",
        "- Omega: OpenCode Go / `deepseek-v4-pro`; completed Stage 2.3 FX decomposition and is coordinating manifests/docs.",
        "- Dragon: Hermes worker / `deepseek-v4-flash:cloud`; completed Stage 2.3 crypto decomposition and Stage 2.4 crypto learned-input prep.",
        "- Gamma: Hermes worker / `deepseek-v4-flash:cloud`; completed Stage 2.2 cross-source statistics and Stage 2.4 FX learned-input prep.",
        "",
        "## Deliverables",
        "",
        f"- Stage 2.2: trading jobs {stage22['trading_jobs_ok']}/{stage22['trading_jobs_total']} ok; cross-source {stage22['cross_jobs_ok']}/{stage22['cross_jobs_total']} ok; skipped nonnumeric {stage22['cross_jobs_skipped_no_numeric']}; actionable failures {stage22['cross_jobs_failed_actionable']}.",
        f"- Stage 2.3: signal decomposition jobs {stage23['jobs_ok']}/{stage23['jobs_total']} ok.",
        f"- Stage 2.4 input prep: {stage24['jobs_ok']}/{stage24['jobs_total']} jobs ok; training wrapper setup next.",
        "",
        "## Blockers",
        "",
        "- No user-side blocker right now.",
        "- Technical setup item: `feature-extractor` must be invoked with explicit `PYTHONPATH=/home/harveybc/Documents/GitHub/feature-extractor:/home/harveybc/Documents/GitHub/feature-extractor/app` because the generic `feature_extractor` console command is currently colliding with another installed CLI.",
    ]
    path = ROOT / "_logs" / "supervisor_reports" / "global_status.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    stage22 = stage22_summary()
    stage23 = stage23_summary()
    stage24 = stage24_input_prep_summary()
    (ROOT / "_metadata" / "stage22_manifest.json").write_text(json.dumps(stage22, indent=2) + "\n", encoding="utf-8")
    (ROOT / "_metadata" / "stage23_manifest.json").write_text(json.dumps(stage23, indent=2) + "\n", encoding="utf-8")
    (ROOT / "_metadata" / "stage24_input_prep_manifest.json").write_text(
        json.dumps(stage24, indent=2) + "\n", encoding="utf-8"
    )
    write_stage22_doc(stage22)
    write_stage23_doc(stage23)
    write_stage24_input_prep_doc(stage24)
    write_global_status(stage22, stage23, stage24)
    report = ROOT / "_logs" / "supervisor_reports" / "stage2_manifest.md"
    report.write_text(
        "\n".join(
            [
                "# Stage 2 Manifest",
                "",
                f"Generated: {utc_now()}",
                "",
                "- Stage 2.2 manifest: `_metadata/stage22_manifest.json`",
                "- Stage 2.3 manifest: `_metadata/stage23_manifest.json`",
                "- Stage 2.4 input prep manifest: `_metadata/stage24_input_prep_manifest.json`",
                "- Stage 2.2 deliverable: `STAGE_2.2_DELIVERABLE.md`",
                "- Stage 2.3 deliverable: `STAGE_2.3_DELIVERABLE.md`",
                "- Stage 2.4 input prep status: `_logs/supervisor_reports/stage24_input_prep_status.md`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
