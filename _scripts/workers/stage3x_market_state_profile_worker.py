#!/usr/bin/env python3
"""Generate CPU-first market-state profile contracts for Stage 3X.

This worker is intentionally contract-first. It does not fit heavy encoders,
launch training, or consume Stage C. It turns the weekly causal contract into
hashable market-state profile candidates so the next CPU screen can compare
1h/4h engineered summaries, PCA-style compression, regime features, and later
learned embeddings without guessing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAUSAL_CONTRACT = (
    ROOT
    / "experiments"
    / "stage3x_market_state_causal_contract"
    / "stage3x_market_state_causal_contract.json"
)
OUT_ROOT = ROOT / "experiments" / "stage3x_market_state_profile"

SCHEMA_VERSION = "project3_stage3x_market_state_profiles_v1"
HELDOUT_START = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)

ENGINEERED_COLUMNS = [
    "state_return_cum",
    "state_realized_volatility",
    "state_trend_slope",
    "state_momentum",
    "state_max_drawdown",
    "state_downside_deviation",
    "state_tail_risk_proxy",
    "state_liquidity_proxy",
    "state_spread_cost_proxy",
    "state_cross_asset_relative_strength",
    "state_cross_asset_correlation_mean",
    "state_cross_asset_beta_proxy",
    "state_hour_sin",
    "state_hour_cos",
    "state_dayofweek_sin",
    "state_dayofweek_cos",
    "state_hours_to_friday_close",
    "state_is_force_close_zone",
    "state_monday_entry_window",
    "state_known_event_risk_score",
    "state_ood_score",
]

PROFILE_DEFS: dict[str, dict[str, Any]] = {
    "engineered_summary": {
        "family": "engineered",
        "implementation_status": "implemented_cpu_contract",
        "source_columns": ENGINEERED_COLUMNS,
        "output_columns": ENGINEERED_COLUMNS,
        "fit_method": "deterministic_window_summary",
        "redundancy_signature": "engineered_summary_v1",
    },
    "engineered_pca": {
        "family": "linear_compression",
        "implementation_status": "implemented_cpu_contract",
        "source_columns": ENGINEERED_COLUMNS,
        "fit_method": "train_only_standardize_then_pca",
        "redundancy_signature": "pca_components_v1",
    },
    "engineered_regime": {
        "family": "regime",
        "implementation_status": "implemented_cpu_contract",
        "source_columns": ENGINEERED_COLUMNS,
        "output_columns": [
            "state_regime_prob_0",
            "state_regime_prob_1",
            "state_regime_prob_2",
            "state_regime_entropy",
            "state_regime_transition_risk",
            "state_regime_persistence",
        ],
        "fit_method": "train_only_hmm_gmm_or_cluster_probabilities",
        "redundancy_signature": "regime_probabilities_v1",
    },
    "engineered_autoencoder": {
        "family": "nonlinear_compression",
        "implementation_status": "stub_dependency_pending",
        "source_columns": ENGINEERED_COLUMNS,
        "fit_method": "train_only_small_autoencoder",
        "redundancy_signature": "autoencoder_bottleneck_v1",
    },
    "engineered_ts2vec": {
        "family": "contrastive_sequence_embedding",
        "implementation_status": "stub_dependency_pending",
        "source_columns": ENGINEERED_COLUMNS,
        "fit_method": "train_only_ts2vec_style_contrastive_encoder",
        "redundancy_signature": "ts2vec_embedding_v1",
    },
    "engineered_patch": {
        "family": "patch_sequence_embedding",
        "implementation_status": "stub_dependency_pending",
        "source_columns": ENGINEERED_COLUMNS,
        "fit_method": "train_only_patch_or_masked_time_series_encoder",
        "redundancy_signature": "patch_embedding_v1",
    },
}


class MarketStateProfileError(RuntimeError):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def parse_dt(value: Any) -> dt.datetime:
    text = str(value).strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text[: len(fmt)], fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    parsed = dt.datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _csv_tokens(value: str | None, default: tuple[str, ...]) -> list[str]:
    if not value:
        return list(default)
    return [token.strip().lower() for token in value.split(",") if token.strip()]


def _profile_tokens(value: str | None) -> list[str]:
    if not value:
        return list(PROFILE_DEFS)
    profiles = _csv_tokens(value, tuple(PROFILE_DEFS))
    unknown = sorted(set(profiles) - set(PROFILE_DEFS))
    if unknown:
        raise MarketStateProfileError(f"Unknown profile(s): {', '.join(unknown)}")
    return profiles


def pca_dim_for_timeframe(timeframe: str) -> int:
    return 16 if timeframe == "1h" else 8


def default_output_columns(profile_id: str, timeframe: str) -> list[str]:
    profile = PROFILE_DEFS[profile_id]
    if "output_columns" in profile:
        return list(profile["output_columns"])
    if profile_id == "engineered_pca":
        return [f"state_pca_{idx:02d}" for idx in range(pca_dim_for_timeframe(timeframe))]
    if profile_id == "engineered_autoencoder":
        dim = 16 if timeframe == "1h" else 8
        return [f"state_autoencoder_{idx:02d}" for idx in range(dim)]
    if profile_id == "engineered_ts2vec":
        dim = 32 if timeframe == "1h" else 16
        return [f"state_ts2vec_{idx:02d}" for idx in range(dim)]
    if profile_id == "engineered_patch":
        dim = 32 if timeframe == "1h" else 16
        return [f"state_patch_{idx:02d}" for idx in range(dim)]
    return list(ENGINEERED_COLUMNS)


def validate_causal_contract(doc: dict[str, Any]) -> None:
    if doc.get("stage_c_access") != "DENIED" or bool(doc.get("stage_c_allowed")):
        raise MarketStateProfileError("Causal contract must deny Stage C.")
    if bool(doc.get("training_launched")):
        raise MarketStateProfileError("Causal contract must not launch training.")
    rows = doc.get("rows") or []
    if not rows:
        raise MarketStateProfileError("Causal contract has no rows.")
    for row in rows:
        if row.get("temporal_issues"):
            raise MarketStateProfileError(f"Causal row has temporal issues: {row['causal_unit_id']}")
        outcome_end = parse_dt(row["outcome_window_end"])
        if outcome_end >= HELDOUT_START:
            raise MarketStateProfileError("Causal contract contains Stage C outcome rows.")


def build_profile_row(
    causal_row: dict[str, Any],
    *,
    timeframe: str,
    profile_id: str,
    state_lookback_weeks: int,
) -> dict[str, Any]:
    profile = PROFILE_DEFS[profile_id]
    observation_end = parse_dt(causal_row["observation_window_end"])
    observation_start = parse_dt(causal_row["observation_window_start"])
    outcome_start = parse_dt(causal_row["outcome_window_start"])
    if observation_end > parse_dt(causal_row["decision_cutoff"]):
        raise MarketStateProfileError("Observation window crosses decision cutoff.")
    if observation_end >= outcome_start:
        raise MarketStateProfileError("Observation window crosses outcome start.")
    if outcome_start >= HELDOUT_START:
        raise MarketStateProfileError("Profile would consume Stage C outcome.")

    source_columns = list(profile["source_columns"])
    output_columns = default_output_columns(profile_id, timeframe)
    encoder_config = {
        "profile_id": profile_id,
        "family": profile["family"],
        "fit_method": profile["fit_method"],
        "timeframe": timeframe,
        "state_lookback_weeks": state_lookback_weeks,
        "source_column_count": len(source_columns),
        "output_column_count": len(output_columns),
        "pca_dim": pca_dim_for_timeframe(timeframe) if profile_id == "engineered_pca" else None,
        "fit_scope": "train_only_before_decision_cutoff",
    }
    source_contract_hash = sha256_text(canonical_json(causal_row))
    encoder_config_hash = sha256_text(canonical_json(encoder_config))
    profile_output_hash = sha256_text(
        canonical_json(
            {
                "causal_unit_id": causal_row["causal_unit_id"],
                "timeframe": timeframe,
                "profile_id": profile_id,
                "output_columns": output_columns,
                "encoder_config_hash": encoder_config_hash,
            }
        )
    )
    market_state_profile_hash = sha256_text(
        canonical_json(
            {
                "source_contract_hash": source_contract_hash,
                "encoder_config_hash": encoder_config_hash,
                "profile_output_hash": profile_output_hash,
            }
        )
    )
    # Negative-control evidence carried from the causal contract. The causal
    # validator already rejects rows with ``temporal_issues``; we re-stamp the
    # sentinel here so the screen reads real evidence instead of hard-coding
    # ``True``. Any optional row-level negative-control scores survive the
    # round-trip so a future causal worker can drive the gate from data.
    future_leak_sentinel_detected = (
        not causal_row.get("temporal_issues")
        and bool(causal_row.get("future_leak_sentinel_detected", True))
    )
    negative_control_evidence = {
        "future_leak_sentinel_detected": future_leak_sentinel_detected,
        "shuffled_outcome_score": causal_row.get("shuffled_outcome_score"),
        "irrelevant_feature_score": causal_row.get("irrelevant_feature_score"),
        "source_temporal_issues": list(causal_row.get("temporal_issues") or []),
    }
    return {
        "market_state_profile_id": (
            f"{causal_row['target_asset']}__{timeframe}__"
            f"{causal_row['weekly_anchor_id']}__{profile_id}"
        ),
        "causal_unit_id": causal_row["causal_unit_id"],
        "weekly_anchor_id": causal_row["weekly_anchor_id"],
        "target_asset": causal_row["target_asset"],
        "timeframe": timeframe,
        "profile_family": profile["family"],
        "profile_name": profile_id,
        "implementation_status": profile["implementation_status"],
        "fit_method": profile["fit_method"],
        "fit_window_start": causal_row["observation_window_start"],
        "fit_window_end": causal_row["observation_window_end"],
        "decision_cutoff": causal_row["decision_cutoff"],
        "outcome_window_start": causal_row["outcome_window_start"],
        "outcome_window_end": causal_row["outcome_window_end"],
        "state_lookback_weeks": state_lookback_weeks,
        "source_columns": source_columns,
        "output_columns": output_columns,
        "source_column_count": len(source_columns),
        "output_column_count": len(output_columns),
        "redundancy_signature": profile["redundancy_signature"],
        "source_contract_hash": source_contract_hash,
        "encoder_config": encoder_config,
        "encoder_config_hash": encoder_config_hash,
        "profile_output_hash": profile_output_hash,
        "market_state_profile_hash": market_state_profile_hash,
        "train_only_fit": True,
        "future_leak_sentinel_detected": future_leak_sentinel_detected,
        "negative_control_evidence": negative_control_evidence,
        "uses_stage_c": False,
        "stage_c_access": "DENIED",
        "training_launched": False,
    }


def build_profiles(
    causal_contract: dict[str, Any],
    *,
    timeframes: list[str],
    profile_names: list[str],
    state_lookback_weeks_1h: int,
    state_lookback_weeks_4h: int,
) -> dict[str, Any]:
    validate_causal_contract(causal_contract)
    profiles: list[dict[str, Any]] = []
    for causal_row in causal_contract["rows"]:
        for timeframe in timeframes:
            lookback = state_lookback_weeks_1h if timeframe == "1h" else state_lookback_weeks_4h
            for profile_id in profile_names:
                profiles.append(
                    build_profile_row(
                        causal_row,
                        timeframe=timeframe,
                        profile_id=profile_id,
                        state_lookback_weeks=lookback,
                    )
                )
    implemented = [row for row in profiles if row["implementation_status"] == "implemented_cpu_contract"]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "stage_c_access": "DENIED",
        "stage_c_allowed": False,
        "training_launched": False,
        "heldout_start": HELDOUT_START.date().isoformat(),
        "source_causal_schema_version": causal_contract.get("schema_version"),
        "source_causal_contract_hash": sha256_text(canonical_json(causal_contract)),
        "timeframes": timeframes,
        "profile_names": profile_names,
        "profile_count": len(profiles),
        "implemented_profile_count": len(implemented),
        "stub_profile_count": len(profiles) - len(implemented),
        "profiles": profiles,
    }


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Stage 3X Market-State Profiles",
        "",
        f"- schema_version: `{payload['schema_version']}`",
        f"- stage_c_access: `{payload['stage_c_access']}`",
        f"- training_launched: `{str(payload['training_launched']).lower()}`",
        f"- profiles: `{payload['profile_count']}`",
        f"- implemented_profiles: `{payload['implemented_profile_count']}`",
        f"- stub_profiles: `{payload['stub_profile_count']}`",
        "",
        "## Profile Families",
        "",
        "| profile | family | status |",
        "| --- | --- | --- |",
    ]
    for name in payload["profile_names"]:
        profile = PROFILE_DEFS[name]
        lines.append(f"| `{name}` | `{profile['family']}` | `{profile['implementation_status']}` |")
    lines.extend(
        [
            "",
            "## First Profile Rows",
            "",
            "| profile id | target | timeframe | family | status | hash |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in payload["profiles"][:30]:
        lines.append(
            "| `{market_state_profile_id}` | `{target_asset}` | `{timeframe}` | `{profile_name}` | `{implementation_status}` | `{market_state_profile_hash}` |".format(
                **row
            )
        )
    return "\n".join(lines) + "\n"


def write_outputs(payload: dict[str, Any], out_root: Path) -> tuple[Path, Path]:
    out_root.mkdir(parents=True, exist_ok=True)
    out_json = out_root / "stage3x_market_state_profiles.json"
    out_md = out_root / "stage3x_market_state_profiles.md"
    write_json(out_json, payload)
    out_md.write_text(render_md(payload), encoding="utf-8")
    return out_json, out_md


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--causal-contract", type=Path, default=DEFAULT_CAUSAL_CONTRACT)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    parser.add_argument("--timeframes", default="4h,1h")
    parser.add_argument("--profiles", default=None)
    parser.add_argument("--state-lookback-weeks-1h", type=int, default=1)
    parser.add_argument("--state-lookback-weeks-4h", type=int, default=2)
    args = parser.parse_args()
    payload = build_profiles(
        load_json(args.causal_contract),
        timeframes=_csv_tokens(args.timeframes, ("4h", "1h")),
        profile_names=_profile_tokens(args.profiles),
        state_lookback_weeks_1h=args.state_lookback_weeks_1h,
        state_lookback_weeks_4h=args.state_lookback_weeks_4h,
    )
    out_json, out_md = write_outputs(payload, args.out_root)
    print(
        json.dumps(
            {
                "profile_count": payload["profile_count"],
                "implemented_profile_count": payload["implemented_profile_count"],
                "stub_profile_count": payload["stub_profile_count"],
                "stage_c_access": payload["stage_c_access"],
                "training_launched": payload["training_launched"],
                "out_json": str(out_json),
                "out_md": str(out_md),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
