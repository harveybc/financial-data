#!/usr/bin/env python3
"""Audit top Stage B diagnostic candidates for feature and action behavior.

The Stage B ranking showed many distinct ``tech_stat`` variants with nearly
identical metrics. This worker checks whether that is a data/evidence issue or
whether the policy behavior is simply insensitive to those feature changes.

It does not launch training and does not read Stage C.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HARDENING = ROOT / "experiments" / "stage_b_validation" / "hardening"
RANKING = HARDENING / "stage_b_diagnostic_candidate_ranking.json"
STAT_REPORT = HARDENING / "stageb_dsr_pbo_report.json"
OUT_JSON = HARDENING / "stage_b_feature_action_audit.json"
OUT_CSV = HARDENING / "stage_b_feature_action_audit.csv"
OUT_MD = HARDENING / "stage_b_feature_action_audit.md"

TOP_N = 12
OOS_SPLITS = {"validation", "test", "evaluation", "stage_b_validation"}
FORCE_CLOSE_OBS_FIELDS = {
    "bars_to_force_close",
    "hours_to_force_close",
    "is_force_close_zone",
    "is_monday_entry_window",
}
FOCUS_AUDIT_SLUGS = (
    "ethusdt_4h_sac_tech_stat_full_candidate",
    "ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate",
    "ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate",
)
NON_FEATURE_COLUMNS = {
    "timestamp",
    "date",
    "datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "OPEN",
    "HIGH",
    "LOW",
    "CLOSE",
    "VOLUME",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def csv_columns(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader, [])


def csv_row_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(sum(1 for _ in handle) - 1, 0)


def feature_summary(path_text: str, reference_columns: set[str]) -> dict[str, Any]:
    if not path_text:
        return {
            "data_file_exists": False,
            "row_count": 0,
            "column_count": 0,
            "feature_count": 0,
            "calendar_feature_count": 0,
            "added_vs_reference": [],
            "missing_vs_reference": [],
        }
    path = Path(path_text)
    if not path.exists():
        return {
            "data_file_exists": False,
            "row_count": 0,
            "column_count": 0,
            "feature_count": 0,
            "calendar_feature_count": 0,
            "added_vs_reference": [],
            "missing_vs_reference": [],
        }
    columns = csv_columns(path)
    colset = set(columns)
    feature_columns = [c for c in columns if c not in NON_FEATURE_COLUMNS]
    return {
        "data_file_exists": True,
        "row_count": csv_row_count(path),
        "column_count": len(columns),
        "feature_count": len(feature_columns),
        "calendar_feature_count": sum(1 for c in columns if c.startswith("calendar_")),
        "added_vs_reference": sorted(colset - reference_columns),
        "missing_vs_reference": sorted(reference_columns - colset),
    }


def _parse_timestamp(text: str) -> datetime | None:
    if not text:
        return None
    cleaned = text.strip().replace("T", " ")
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(cleaned[: len(fmt)], fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _shannon_entropy_bits(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for count in counter.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def trace_action_summary(trace_entries: list[dict[str, Any]]) -> dict[str, Any]:
    actions: list[float] = []
    positions: list[float] = []
    rewards: list[float] = []
    net_returns: list[float] = []
    split_trade_last: dict[str, int] = {}
    split_rows = Counter()
    friday_late_bars = 0
    friday_late_exposed_bars = 0
    rounded_action_hist: Counter = Counter()
    for entry in trace_entries:
        split = str(entry.get("split", "")).lower()
        if split not in OOS_SPLITS:
            continue
        trace_file = Path(str(entry.get("trace_file", "")))
        if not trace_file.exists():
            continue
        last_trade_value = 0
        with trace_file.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                split_rows[split] += 1
                action_value = safe_float(row.get("action_raw"))
                position_value = safe_float(row.get("position"))
                actions.append(action_value)
                positions.append(position_value)
                rewards.append(safe_float(row.get("reward")))
                net_returns.append(safe_float(row.get("net_return")))
                rounded_action_hist[round(action_value, 4)] += 1
                last_trade_value = int(safe_float(row.get("trades")))
                ts = _parse_timestamp(str(row.get("timestamp", "")))
                # Force-close zone heuristic: Friday from 16:00 UTC onward.
                # Agent-multi enforces a Friday session close; bars in this
                # window are where exposure must be unwound. Reporting fraction
                # rather than abs count keeps the metric scale-free.
                if ts is not None and ts.weekday() == 4 and ts.hour >= 16:
                    friday_late_bars += 1
                    if abs(position_value) > 1e-12:
                        friday_late_exposed_bars += 1
        split_trade_last[split] = last_trade_value
    position_changes = sum(
        1
        for prev, cur in zip(positions, positions[1:])
        if abs(cur - prev) > 1e-12
    )
    oos_n = len(actions)
    return {
        "oos_row_count": oos_n,
        "oos_split_rows": dict(sorted(split_rows.items())),
        "action_mean": mean(actions) if actions else 0.0,
        "action_std": pstdev(actions) if len(actions) > 1 else 0.0,
        "action_min": min(actions) if actions else 0.0,
        "action_max": max(actions) if actions else 0.0,
        "action_unique_rounded_4dp": len(rounded_action_hist),
        "action_entropy_bits_rounded_4dp": _shannon_entropy_bits(rounded_action_hist),
        "position_exposure_fraction": (
            sum(1 for p in positions if abs(p) > 1e-12) / oos_n
            if oos_n else 0.0
        ),
        "position_changes": position_changes,
        "position_flip_rate": position_changes / oos_n if oos_n else 0.0,
        "friday_late_bar_count": friday_late_bars,
        "friday_late_exposed_bars": friday_late_exposed_bars,
        "friday_late_exposure_fraction": (
            friday_late_exposed_bars / friday_late_bars
            if friday_late_bars else 0.0
        ),
        "trades_total_oos": sum(split_trade_last.values()),
        "reward_sum_oos": sum(rewards),
        "net_return_sum_oos": sum(net_returns),
    }


def evidence_contract_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize feature/observation evidence contract fields for a candidate."""
    feature_hashes: list[str] = []
    observation_hashes: list[str] = []
    observation_field_sets: list[set[str]] = []
    evidence_files_checked = 0
    for rec in records:
        feature_hash = str(rec.get("feature_list_hash") or "")
        if feature_hash and feature_hash.lower() not in {"none", "null"}:
            feature_hashes.append(feature_hash)
        evidence_path = Path(str(rec.get("evidence_file") or ""))
        if not evidence_path.exists():
            continue
        evidence_files_checked += 1
        try:
            evidence = load_json(evidence_path)
        except Exception:
            continue
        obs_hash = str(evidence.get("observation_state_hash") or "")
        if obs_hash and obs_hash.lower() not in {"none", "null"}:
            observation_hashes.append(obs_hash)
        fields = evidence.get("observation_state_fields") or []
        if isinstance(fields, list):
            observation_field_sets.append({str(field) for field in fields})
    records_n = len(records)
    force_close_present = sum(
        1 for fields in observation_field_sets if FORCE_CLOSE_OBS_FIELDS.issubset(fields)
    )
    return {
        "evidence_files_checked": evidence_files_checked,
        "feature_list_hash_missing": len(feature_hashes) < records_n,
        "feature_list_hash_count": len(set(feature_hashes)),
        "observation_state_hash_missing": len(observation_hashes) < records_n,
        "observation_state_hash_count": len(set(observation_hashes)),
        "force_close_obs_fields_present_records": force_close_present,
        "force_close_obs_contract_ok": records_n > 0 and force_close_present == records_n,
    }


def selected_audit_slugs(ranking_rows: list[dict[str, Any]], records: list[dict[str, Any]]) -> list[str]:
    """Audit top-ranked candidates plus named diagnostic slugs even if lower ranked."""
    ordered: list[str] = []
    seen: set[str] = set()
    record_slugs = {str(rec.get("candidate_slug")) for rec in records if not rec.get("is_baseline")}
    for rank_row in ranking_rows[:TOP_N]:
        slug = str(rank_row.get("candidate_slug") or "")
        if slug and slug not in seen:
            ordered.append(slug)
            seen.add(slug)
    for slug in FOCUS_AUDIT_SLUGS:
        if slug in record_slugs and slug not in seen:
            ordered.append(slug)
            seen.add(slug)
    return ordered


def default_rank_row(slug: str, fallback_rank: int) -> dict[str, Any]:
    return {
        "diagnostic_rank": fallback_rank,
        "candidate_slug": slug,
        "diagnostic_score": 0.0,
        "blocking_reasons": "",
        "mean_return": 0.0,
        "min_return": 0.0,
        "mean_sharpe": 0.0,
    }


def build_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranking = load_json(RANKING)
    stat = load_json(STAT_REPORT)
    ranking_rows = list(ranking.get("rows", []))
    records = stat.get("records", [])
    audit_slugs = selected_audit_slugs(ranking_rows, records)
    rank_lookup = {str(row.get("candidate_slug")): row for row in ranking_rows}
    by_slug: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in records:
        if rec.get("candidate_slug") in audit_slugs and not rec.get("is_baseline"):
            by_slug[str(rec.get("candidate_slug"))].append(rec)

    reference_file = ""
    if audit_slugs and by_slug.get(audit_slugs[0]):
        reference_file = str(by_slug[audit_slugs[0]][0].get("data_file") or "")
    reference_columns = set(csv_columns(Path(reference_file))) if reference_file and Path(reference_file).exists() else set()

    rows: list[dict[str, Any]] = []
    for fallback_rank, slug in enumerate(audit_slugs, start=1):
        rank_row = rank_lookup.get(slug) or default_rank_row(slug, fallback_rank)
        recs = by_slug.get(slug, [])
        if not recs:
            continue
        data_files = sorted({str(rec.get("data_file") or "") for rec in recs})
        data_hashes = sorted({str(rec.get("data_file_hash") or "") for rec in recs})
        feature_hashes = sorted({str(rec.get("feature_list_hash") or "") for rec in recs})
        trace_summaries = [trace_action_summary(rec.get("trace_entries") or []) for rec in recs]
        action_std_values = [s["action_std"] for s in trace_summaries]
        action_unique_values = [s["action_unique_rounded_4dp"] for s in trace_summaries]
        action_entropy_values = [s["action_entropy_bits_rounded_4dp"] for s in trace_summaries]
        flip_rates = [s["position_flip_rate"] for s in trace_summaries]
        friday_exposure = [s["friday_late_exposure_fraction"] for s in trace_summaries]
        trades_values = [s["trades_total_oos"] for s in trace_summaries]
        exposure_values = [s["position_exposure_fraction"] for s in trace_summaries]
        feature = feature_summary(data_files[0] if data_files else "", reference_columns)
        evidence_contract = evidence_contract_summary(recs)
        row = {
            "diagnostic_rank": rank_row.get("diagnostic_rank"),
            "candidate_slug": slug,
            "diagnostic_score": safe_float(rank_row.get("diagnostic_score")),
            "blocking_reasons": rank_row.get("blocking_reasons", ""),
            "record_count": len(recs),
            "costs": ";".join(sorted({str(rec.get("cost_scenario") or "") for rec in recs})),
            "seeds": ";".join(sorted({str(rec.get("seed") or "") for rec in recs})),
            "data_file": data_files[0] if data_files else "",
            "data_hash_count": len(data_hashes),
            "data_file_hash": data_hashes[0] if len(data_hashes) == 1 else ";".join(data_hashes),
            "feature_list_hash_missing": evidence_contract["feature_list_hash_missing"],
            "feature_list_hash_count": evidence_contract["feature_list_hash_count"],
            "observation_state_hash_missing": evidence_contract["observation_state_hash_missing"],
            "observation_state_hash_count": evidence_contract["observation_state_hash_count"],
            "force_close_obs_fields_present_records": evidence_contract["force_close_obs_fields_present_records"],
            "force_close_obs_contract_ok": evidence_contract["force_close_obs_contract_ok"],
            "data_file_exists": feature["data_file_exists"],
            "row_count": feature["row_count"],
            "column_count": feature["column_count"],
            "feature_count": feature["feature_count"],
            "calendar_feature_count": feature["calendar_feature_count"],
            "added_vs_reference_count": len(feature["added_vs_reference"]),
            "missing_vs_reference_count": len(feature["missing_vs_reference"]),
            "added_vs_reference": ";".join(feature["added_vs_reference"][:40]),
            "missing_vs_reference": ";".join(feature["missing_vs_reference"][:40]),
            "mean_action_std": mean(action_std_values) if action_std_values else 0.0,
            "min_action_unique_rounded_4dp": min(action_unique_values) if action_unique_values else 0,
            "max_action_unique_rounded_4dp": max(action_unique_values) if action_unique_values else 0,
            "mean_action_entropy_bits": mean(action_entropy_values) if action_entropy_values else 0.0,
            "mean_position_flip_rate": mean(flip_rates) if flip_rates else 0.0,
            "mean_friday_late_exposure_fraction": (
                mean(friday_exposure) if friday_exposure else 0.0
            ),
            "mean_trades_oos": mean(trades_values) if trades_values else 0.0,
            "min_trades_oos": min(trades_values) if trades_values else 0,
            "max_trades_oos": max(trades_values) if trades_values else 0,
            "mean_exposure_fraction": mean(exposure_values) if exposure_values else 0.0,
            "mean_return": safe_float(rank_row.get("mean_return")),
            "min_return": safe_float(rank_row.get("min_return")),
            "mean_sharpe": safe_float(rank_row.get("mean_sharpe")),
        }
        rows.append(row)

    performance_groups = Counter(
        (
            round(safe_float(row["mean_return"]), 8),
            round(safe_float(row["min_return"]), 8),
            round(safe_float(row["mean_sharpe"]), 8),
            row["blocking_reasons"],
        )
        for row in rows
    )
    # Build paired calendar-vs-non-calendar comparisons. For each audited slug
    # whose name ends in ``_plus_session_calendar_candidate``, find the matching
    # non-calendar slug (``_candidate``) and report the delta in action-std,
    # trade rate, and Friday late exposure. If both candidates collapse to the
    # same metrics, the calendar columns did not move policy behavior.
    by_slug = {row["candidate_slug"]: row for row in rows}
    paired_calendar_compare: list[dict[str, Any]] = []
    for slug, row in by_slug.items():
        if not slug.endswith("_plus_session_calendar_candidate"):
            continue
        partner_slug = slug.replace("_plus_session_calendar_candidate", "_candidate")
        partner = by_slug.get(partner_slug)
        if partner is None:
            continue
        paired_calendar_compare.append({
            "calendar_slug": slug,
            "non_calendar_slug": partner_slug,
            "delta_mean_action_std": safe_float(row["mean_action_std"]) - safe_float(partner["mean_action_std"]),
            "delta_mean_action_entropy_bits": (
                safe_float(row["mean_action_entropy_bits"])
                - safe_float(partner["mean_action_entropy_bits"])
            ),
            "delta_mean_trades_oos": safe_float(row["mean_trades_oos"]) - safe_float(partner["mean_trades_oos"]),
            "delta_mean_position_flip_rate": (
                safe_float(row["mean_position_flip_rate"])
                - safe_float(partner["mean_position_flip_rate"])
            ),
            "delta_mean_friday_late_exposure_fraction": (
                safe_float(row["mean_friday_late_exposure_fraction"])
                - safe_float(partner["mean_friday_late_exposure_fraction"])
            ),
            "identical_action_signature": (
                round(safe_float(row["mean_action_std"]), 6)
                == round(safe_float(partner["mean_action_std"]), 6)
                and round(safe_float(row["mean_trades_oos"]), 4)
                == round(safe_float(partner["mean_trades_oos"]), 4)
            ),
        })

    force_close_obs_compare: list[dict[str, Any]] = []
    force_slug = "ethusdt_4h_sac_tech_stat_full_plus_force_close_obs_candidate"
    force = by_slug.get(force_slug)
    if force is not None:
        for partner_slug, label in (
            ("ethusdt_4h_sac_tech_stat_full_candidate", "non_calendar"),
            ("ethusdt_4h_sac_tech_stat_full_plus_session_calendar_candidate", "session_calendar"),
        ):
            partner = by_slug.get(partner_slug)
            if partner is None:
                continue
            delta_action_std = safe_float(force["mean_action_std"]) - safe_float(partner["mean_action_std"])
            delta_entropy = (
                safe_float(force["mean_action_entropy_bits"])
                - safe_float(partner["mean_action_entropy_bits"])
            )
            delta_trades = safe_float(force["mean_trades_oos"]) - safe_float(partner["mean_trades_oos"])
            delta_flip = safe_float(force["mean_position_flip_rate"]) - safe_float(partner["mean_position_flip_rate"])
            delta_friday = (
                safe_float(force["mean_friday_late_exposure_fraction"])
                - safe_float(partner["mean_friday_late_exposure_fraction"])
            )
            force_close_obs_compare.append({
                "force_close_slug": force_slug,
                "partner_slug": partner_slug,
                "partner_label": label,
                "force_close_obs_contract_ok": bool(force["force_close_obs_contract_ok"]),
                "delta_mean_action_std": delta_action_std,
                "delta_mean_action_entropy_bits": delta_entropy,
                "delta_mean_trades_oos": delta_trades,
                "delta_mean_position_flip_rate": delta_flip,
                "delta_mean_friday_late_exposure_fraction": delta_friday,
                "behavior_changed": (
                    abs(delta_action_std) > 1e-6
                    or abs(delta_entropy) > 1e-6
                    or abs(delta_trades) > 1e-6
                    or abs(delta_flip) > 1e-6
                    or abs(delta_friday) > 1e-6
                ),
                "friday_late_exposure_improved": delta_friday < -1e-6,
            })

    warnings: list[str] = []
    if any(row["feature_list_hash_missing"] for row in rows):
        # Missing feature_list_hash is a diagnostic warning, not a Stage C
        # promotion attribute. ``stage_c_allowed`` must stay false regardless.
        warnings.append(
            "feature_list_hash is missing for one or more top candidates; "
            "agent-multi evidence contract should persist a deterministic hash."
        )
    if paired_calendar_compare and all(
        item["identical_action_signature"] for item in paired_calendar_compare
    ):
        warnings.append(
            "Session-calendar columns produced identical action and trade "
            "signatures vs. matched non-calendar variants for every audited "
            "pair; the policy is not consuming the calendar features."
        )
    if any(
        row["min_action_unique_rounded_4dp"] <= 2 and row["mean_trades_oos"] > 0
        for row in rows
    ):
        warnings.append(
            "At least one audited candidate emits two or fewer distinct rounded "
            "actions across OOS; check action deadband / squashing in agent-multi."
        )
    if force_close_obs_compare:
        if not all(item["force_close_obs_contract_ok"] for item in force_close_obs_compare):
            warnings.append(
                "force_close_obs comparison exists but the repaired observation "
                "contract is incomplete; do not interpret behavior deltas."
            )
        elif not any(item["behavior_changed"] for item in force_close_obs_compare):
            warnings.append(
                "force_close_obs contract is present, but behavior is still "
                "identical to the matched non-calendar/session-calendar policies."
            )
        elif not any(item["friday_late_exposure_improved"] for item in force_close_obs_compare):
            warnings.append(
                "force_close_obs changes policy behavior, but does not reduce "
                "Friday-late exposure versus matched policies."
            )

    summary = {
        "top_n": TOP_N,
        "audited_candidates": len(rows),
        "feature_list_hash_missing_candidates": sum(1 for row in rows if row["feature_list_hash_missing"]),
        "distinct_data_hashes": len({row["data_file_hash"] for row in rows}),
        "identical_performance_signature_groups": sum(1 for count in performance_groups.values() if count > 1),
        "largest_identical_performance_group": max(performance_groups.values(), default=0),
        "paired_calendar_compare": paired_calendar_compare,
        "paired_calendar_pairs_count": len(paired_calendar_compare),
        "paired_calendar_identical_signature_count": sum(
            1 for item in paired_calendar_compare if item["identical_action_signature"]
        ),
        "force_close_obs_compare": force_close_obs_compare,
        "force_close_obs_pairs_count": len(force_close_obs_compare),
        "force_close_obs_behavior_changed_count": sum(
            1 for item in force_close_obs_compare if item["behavior_changed"]
        ),
        "force_close_obs_friday_exposure_improved_count": sum(
            1 for item in force_close_obs_compare if item["friday_late_exposure_improved"]
        ),
        "force_close_obs_contract_ok": (
            bool(force_close_obs_compare)
            and all(item["force_close_obs_contract_ok"] for item in force_close_obs_compare)
        ),
        "warnings": warnings,
        "stage_c_allowed": False,
    }
    return rows, summary


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    payload = {
        "schema_version": "project3_stage_b_feature_action_audit_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Audit top failed Stage B candidates for feature distinctness and action behavior.",
        "stage_c_allowed": False,
        "summary": summary,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    fields = list(rows[0].keys()) if rows else ["candidate_slug"]
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Stage B Feature/Action Audit",
        "",
        f"Generated UTC: `{payload['generated_at_utc']}`",
        "",
        "This is a diagnosis artifact only. It does not approve Stage C.",
        "",
        "## Summary",
        "",
    ]
    scalar_summary_keys = (
        "top_n",
        "audited_candidates",
        "feature_list_hash_missing_candidates",
        "distinct_data_hashes",
        "identical_performance_signature_groups",
        "largest_identical_performance_group",
        "paired_calendar_pairs_count",
        "paired_calendar_identical_signature_count",
        "force_close_obs_pairs_count",
        "force_close_obs_behavior_changed_count",
        "force_close_obs_friday_exposure_improved_count",
        "force_close_obs_contract_ok",
        "stage_c_allowed",
    )
    for key in scalar_summary_keys:
        if key in summary:
            lines.append(f"- `{key}`: `{summary[key]}`")
    if summary.get("warnings"):
        lines += ["", "## Warnings", ""]
        for warn in summary["warnings"]:
            lines.append(f"- {warn}")
    lines += [
        "",
        "## Audited Candidates",
        "",
        "| Rank | Candidate | Columns | Calendar Cols | Missing Feature Hash | Missing Obs Hash | Force Obs OK | Mean Trades OOS | Mean Exposure | Action Std | Action Entropy | Flip Rate | Fri-late Exp | Same-Perf Clue |",
        "| ---: | --- | ---: | ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        same_perf = "yes" if safe_float(row["diagnostic_score"]) == safe_float(rows[0]["diagnostic_score"]) else ""
        lines.append(
            f"| {row['diagnostic_rank']} | `{row['candidate_slug']}` | "
            f"{row['column_count']} | {row['calendar_feature_count']} | "
            f"`{row['feature_list_hash_missing']}` | "
            f"`{row['observation_state_hash_missing']}` | "
            f"`{row['force_close_obs_contract_ok']}` | "
            f"{safe_float(row['mean_trades_oos']):.2f} | "
            f"{safe_float(row['mean_exposure_fraction']):.4f} | "
            f"{safe_float(row['mean_action_std']):.6f} | "
            f"{safe_float(row['mean_action_entropy_bits']):.4f} | "
            f"{safe_float(row['mean_position_flip_rate']):.4f} | "
            f"{safe_float(row['mean_friday_late_exposure_fraction']):.4f} | "
            f"{same_perf} |"
        )
    if summary.get("paired_calendar_compare"):
        lines += [
            "",
            "## Paired Calendar vs Non-Calendar Compare",
            "",
            "| Calendar slug | Non-calendar partner | Δ action std | Δ action entropy | Δ trades OOS | Δ flip rate | Δ Fri-late exposure | Identical action sig |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
        for item in summary["paired_calendar_compare"]:
            lines.append(
                f"| `{item['calendar_slug']}` | `{item['non_calendar_slug']}` | "
                f"{safe_float(item['delta_mean_action_std']):+.6f} | "
                f"{safe_float(item['delta_mean_action_entropy_bits']):+.6f} | "
                f"{safe_float(item['delta_mean_trades_oos']):+.4f} | "
                f"{safe_float(item['delta_mean_position_flip_rate']):+.6f} | "
                f"{safe_float(item['delta_mean_friday_late_exposure_fraction']):+.6f} | "
                f"`{item['identical_action_signature']}` |"
            )
    if summary.get("force_close_obs_compare"):
        lines += [
            "",
            "## Force-Close Observation Compare",
            "",
            "| Force-close slug | Partner | Partner type | Contract OK | Δ action std | Δ action entropy | Δ trades OOS | Δ flip rate | Δ Fri-late exposure | Behavior changed | Fri-late exposure improved |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
        for item in summary["force_close_obs_compare"]:
            lines.append(
                f"| `{item['force_close_slug']}` | `{item['partner_slug']}` | "
                f"{item['partner_label']} | `{item['force_close_obs_contract_ok']}` | "
                f"{safe_float(item['delta_mean_action_std']):+.6f} | "
                f"{safe_float(item['delta_mean_action_entropy_bits']):+.6f} | "
                f"{safe_float(item['delta_mean_trades_oos']):+.4f} | "
                f"{safe_float(item['delta_mean_position_flip_rate']):+.6f} | "
                f"{safe_float(item['delta_mean_friday_late_exposure_fraction']):+.6f} | "
                f"`{item['behavior_changed']}` | "
                f"`{item['friday_late_exposure_improved']}` |"
            )
    lines += [
        "",
        "## Findings",
        "",
        "- Distinct data hashes with identical ranking metrics indicate the run plan did not collapse to one file, but policy behavior may be insensitive to feature differences.",
        "- Missing `feature_list_hash` in legacy evidence is an evidence-contract gap; repaired force-close evidence must carry both feature and observation hashes.",
        "- If action statistics are near-identical across variants, the next fix belongs in observation/action/reward diagnostics before another broad GPU matrix.",
    ]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows, summary = build_rows()
    write_outputs(rows, summary)
    print(json.dumps({
        "json": str(OUT_JSON),
        "csv": str(OUT_CSV),
        "markdown": str(OUT_MD),
        **summary,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
