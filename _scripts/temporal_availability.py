"""C81-C83 temporal availability semantics (order 2026-09-12).

Two notions that must never be confused:

1. ``causal_information_bound`` -- the earliest instant at which a datum
   COULD be complete by the definition of its period. BAR_OPEN -> the
   bar's own, per-bar ``close_time`` (never ``open + nominal``);
   BAR_CLOSE -> the timestamp itself; PUBLICATION -> the publication
   timestamp.
2. ``operational_delivery_bound`` -- the instant at which the provider
   was OBSERVED or GUARANTEED to deliver it. It needs an observed or
   declared latency. ``UNOBSERVED`` stays UNOBSERVED; it is never read
   as zero.

Gates:

* E5a (offline experiments) requires a RESOLVED causal bound only.
* E5b (live) requires BOTH bounds RESOLVED. A causal bound presented in
  place of an operational one never opens E5b. An open E5b states that
  the NECESSARY temporal conditions hold; it is not a grant of live
  viability.

Everything here is a pure function over plain mappings. No I/O.
"""
from __future__ import annotations

import math
import numbers
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

SCHEMA_ID = "financial_data.temporal_availability_schema.v1"

TIMESTAMP_SEMANTICS = ("BAR_OPEN", "BAR_CLOSE", "PUBLICATION", "UNDECLARED")
# The causal rule is a FUNCTION of the semantics; a contract that pairs
# them differently is invalid.
CAUSAL_RULE_BY_SEMANTICS = {
    "BAR_OPEN": "PER_BAR_CLOSE_TIME",
    "BAR_CLOSE": "TIMESTAMP_ITSELF",
    "PUBLICATION": "PUBLICATION_TIMESTAMP",
    "UNDECLARED": "UNDECLARED",
}
CAUSAL_RULES = tuple(CAUSAL_RULE_BY_SEMANTICS.values())
CLOSE_TIME_CONVENTIONS = ("INCLUSIVE_LAST_MILLISECOND", "EXCLUSIVE_END")
LATENCY_STATUSES = ("OBSERVED", "DECLARED", "UNOBSERVED")
PROVENANCE_STATUSES = (
    "DECLARED",
    "EVIDENCED_BY_EXACT_MATCH_WITH_DECLARED_UPSTREAM",
    "EVIDENCED_BY_EXACT_MATCH_NOT_BY_DECLARATION",
    "UNDECLARED",
)
BOUND_KINDS = ("causal_information_bound", "operational_delivery_bound")
BOUND_STATUSES = ("RESOLVED", "UNRESOLVED", "UNOBSERVED", "REFUSED")
GATE_IDS = ("E5a", "E5b")
GATE_STATUSES = ("OPEN", "CLOSED")

REASON_CODES = (
    # contract / binding
    "CONTRACT_INVALID",
    "DATASET_DIGEST_NOT_PRESENTED",
    "DATASET_TRANSPLANTED",
    "PROVENANCE_UNDECLARED",
    "TIMESTAMP_SEMANTICS_UNDECLARED",
    "TIMESTAMP_ABSENT",
    "NON_INCREASING_TIMESTAMP",
    # BAR_OPEN
    "PER_BAR_CLOSE_TIME",
    "CLOSE_TIME_ABSENT_NOT_INFERRED_FROM_NOMINAL_BAR",
    "CLOSE_TIME_BEFORE_OPEN_TIME",
    "CLOSE_TIME_EXCEEDS_NOMINAL_BAR",
    "CLOSE_TIME_OVERLAPS_NEXT_BAR",
    "TRUNCATED_BAR",
    "ZERO_SPAN_BAR",
    "FOLLOWED_BY_GAP",
    # BAR_CLOSE
    "TIMESTAMP_IS_BAR_CLOSE",
    "CLOSE_TIME_CONTRADICTS_BAR_CLOSE_SEMANTICS",
    # PUBLICATION
    "PUBLICATION_TIMESTAMP",
    "PUBLICATION_TIME_ABSENT",
    "PUBLICATION_BEFORE_EVENT_TIME",
    # operational
    "BOUND_KIND_MISMATCH",
    "BOUND_FROM_OTHER_CONTRACT",
    "CAUSAL_BOUND_NOT_RESOLVED",
    "PROVIDER_DELIVERY_LATENCY_UNOBSERVED",
    "PROVIDER_DELIVERY_LATENCY_OBSERVED",
    "PROVIDER_DELIVERY_LATENCY_DECLARED",
    # gates
    "CAUSAL_INFORMATION_BOUND_RESOLVED",
    "CAUSAL_INFORMATION_BOUND_NOT_RESOLVED",
    "OPERATIONAL_DELIVERY_BOUND_ABSENT",
    "OFFLINE_CAUSAL_BOUND_PRESENTED_AS_OPERATIONAL",
    "OPERATIONAL_DELIVERY_BOUND_NOT_RESOLVED",
    "OPERATIONAL_BOUND_PRECEDES_CAUSAL_BOUND",
    "OPERATIONAL_DELIVERY_BOUND_RESOLVED",
    "NECESSARY_CONDITIONS_ONLY_NOT_A_LIVE_VIABILITY_GRANT",
    "NO_ROWS_EVALUATED",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


# ------------------------------------------------------------- results
@dataclass(frozen=True)
class Bound:
    kind: str
    status: str
    utc_ms: int | None
    reasons: tuple[str, ...]
    contract_id: str | None
    dataset_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "status": self.status,
                "utc_ms": self.utc_ms, "reasons": list(self.reasons),
                "contract_id": self.contract_id,
                "dataset_sha256": self.dataset_sha256}


@dataclass(frozen=True)
class Gate:
    gate: str
    status: str
    reasons: tuple[str, ...]

    @property
    def is_open(self) -> bool:
        return self.status == "OPEN"

    def to_dict(self) -> dict[str, Any]:
        return {"gate": self.gate, "status": self.status,
                "reasons": list(self.reasons)}


# ----------------------------------------------------------- contract
def _is_int(v: Any) -> bool:
    return isinstance(v, numbers.Integral) and not isinstance(v, bool)


def _ms(v: Any) -> int | None:
    """An integer UTC-millisecond value, or None when absent/NaN."""
    if v is None:
        return None
    if _is_int(v):
        return int(v)
    if isinstance(v, float):
        if math.isnan(v):
            return None
        if v.is_integer():
            return int(v)
    raise TypeError(f"timestamp must be integer UTC milliseconds, got {v!r}")


def validate_contract(contract: Mapping[str, Any]) -> tuple[str, ...]:
    """Every defect of a contract against TEMPORAL_AVAILABILITY_SCHEMA.v1."""
    d: list[str] = []
    if not isinstance(contract, Mapping):
        return ("CONTRACT_NOT_A_MAPPING",)
    for key in ("contract_id", "dataset_id"):
        if not isinstance(contract.get(key), str) or not contract.get(key):
            d.append(f"MISSING:{key}")
    sha = contract.get("dataset_sha256")
    if not isinstance(sha, str) or not _HEX64.match(sha):
        d.append("INVALID:dataset_sha256")
    sem = contract.get("timestamp_semantics")
    if sem not in TIMESTAMP_SEMANTICS:
        d.append("INVALID:timestamp_semantics")
    rule = contract.get("information_complete_not_before")
    if rule not in CAUSAL_RULES:
        d.append("INVALID:information_complete_not_before")
    elif sem in CAUSAL_RULE_BY_SEMANTICS and rule != CAUSAL_RULE_BY_SEMANTICS[sem]:
        d.append("RULE_CONTRADICTS_SEMANTICS")
    nominal = contract.get("nominal_bar_seconds")
    if sem == "BAR_OPEN":
        if not _is_int(nominal) or nominal <= 0:
            d.append("INVALID:nominal_bar_seconds")
        if contract.get("bar_close_time_convention") not in CLOSE_TIME_CONVENTIONS:
            d.append("INVALID:bar_close_time_convention")
    elif nominal is not None and (not _is_int(nominal) or nominal <= 0):
        d.append("INVALID:nominal_bar_seconds")
    lat = contract.get("provider_delivery_latency")
    if not isinstance(lat, Mapping):
        d.append("MISSING:provider_delivery_latency")
    else:
        st, secs = lat.get("status"), lat.get("seconds", "ABSENT")
        if st not in LATENCY_STATUSES:
            d.append("INVALID:provider_delivery_latency.status")
        if secs == "ABSENT":
            d.append("MISSING:provider_delivery_latency.seconds")
        elif st == "UNOBSERVED":
            if secs is not None:
                # the defect this order exists to prevent
                d.append("LATENCY_UNOBSERVED_BUT_VALUED")
        elif st in ("OBSERVED", "DECLARED"):
            if (isinstance(secs, bool) or not isinstance(secs, numbers.Real)
                    or math.isnan(secs) or secs < 0):
                d.append("INVALID:provider_delivery_latency.seconds")
    prov = contract.get("provenance")
    if not isinstance(prov, Mapping):
        d.append("MISSING:provenance")
    else:
        if prov.get("status") not in PROVENANCE_STATUSES:
            d.append("INVALID:provenance.status")
        if not isinstance(prov.get("basis"), str) or not prov.get("basis"):
            d.append("MISSING:provenance.basis")
    return tuple(d)


def _bound(contract: Mapping[str, Any], kind: str, status: str,
           utc_ms: int | None, reasons: Iterable[str]) -> Bound:
    c = contract if isinstance(contract, Mapping) else {}
    return Bound(kind, status, utc_ms, tuple(reasons),
                 c.get("contract_id"), c.get("dataset_sha256"))


# -------------------------------------------------- causal information
def causal_information_bound(contract: Mapping[str, Any],
                             bar_row: Mapping[str, Any], *,
                             observed_sha256: str | None) -> Bound:
    """When the datum in ``bar_row`` could be complete by definition.

    ``bar_row`` keys (integer UTC ms): ``timestamp_ms`` (the dataset's
    timestamp, interpreted per the contract), optional ``close_time_ms``,
    ``publication_time_ms`` and ``next_timestamp_ms`` (the next bar of
    the SOURCE, used to detect overlap and gaps).

    ``observed_sha256`` is the digest of the bytes the row came from; it
    is keyword-only and has no default so that no caller can forget the
    binding. A contract applied to other bytes is refused.
    """
    kind = "causal_information_bound"
    defects = validate_contract(contract)
    if defects:
        return _bound(contract, kind, "REFUSED", None,
                      ["CONTRACT_INVALID"] + [f"CONTRACT_INVALID:{x}" for x in defects])
    if observed_sha256 is None:
        return _bound(contract, kind, "UNRESOLVED", None,
                      ["DATASET_DIGEST_NOT_PRESENTED"])
    if observed_sha256 != contract["dataset_sha256"]:
        return _bound(contract, kind, "REFUSED", None, ["DATASET_TRANSPLANTED"])
    unresolved = []
    if contract["provenance"]["status"] == "UNDECLARED":
        unresolved.append("PROVENANCE_UNDECLARED")
    sem = contract["timestamp_semantics"]
    if sem == "UNDECLARED":
        unresolved.append("TIMESTAMP_SEMANTICS_UNDECLARED")
    if unresolved:
        return _bound(contract, kind, "UNRESOLVED", None, unresolved)

    ts = _ms(bar_row.get("timestamp_ms"))
    if ts is None:
        return _bound(contract, kind, "UNRESOLVED", None, ["TIMESTAMP_ABSENT"])
    nxt = _ms(bar_row.get("next_timestamp_ms"))
    if nxt is not None and nxt <= ts:
        return _bound(contract, kind, "REFUSED", None, ["NON_INCREASING_TIMESTAMP"])
    close = _ms(bar_row.get("close_time_ms"))

    if sem == "BAR_OPEN":
        nominal_ms = int(contract["nominal_bar_seconds"]) * 1000
        full_span = nominal_ms - (1 if contract["bar_close_time_convention"]
                                  == "INCLUSIVE_LAST_MILLISECOND" else 0)
        if close is None:
            return _bound(contract, kind, "UNRESOLVED", None,
                          ["CLOSE_TIME_ABSENT_NOT_INFERRED_FROM_NOMINAL_BAR"])
        if close < ts:
            return _bound(contract, kind, "REFUSED", None, ["CLOSE_TIME_BEFORE_OPEN_TIME"])
        if close - ts > full_span:
            return _bound(contract, kind, "REFUSED", None, ["CLOSE_TIME_EXCEEDS_NOMINAL_BAR"])
        if nxt is not None and close >= nxt:
            return _bound(contract, kind, "REFUSED", None, ["CLOSE_TIME_OVERLAPS_NEXT_BAR"])
        reasons = ["PER_BAR_CLOSE_TIME"]
        if close - ts < full_span:
            reasons.append("TRUNCATED_BAR")
        if close == ts:
            reasons.append("ZERO_SPAN_BAR")
        if nxt is not None and nxt - ts > nominal_ms:
            reasons.append("FOLLOWED_BY_GAP")
        return _bound(contract, kind, "RESOLVED", close, reasons)

    if sem == "BAR_CLOSE":
        if close is not None and close != ts:
            return _bound(contract, kind, "REFUSED", None,
                          ["CLOSE_TIME_CONTRADICTS_BAR_CLOSE_SEMANTICS"])
        return _bound(contract, kind, "RESOLVED", ts, ["TIMESTAMP_IS_BAR_CLOSE"])

    # PUBLICATION: timestamp_ms is the event / reference time.
    pub = _ms(bar_row.get("publication_time_ms"))
    if pub is None:
        return _bound(contract, kind, "UNRESOLVED", None, ["PUBLICATION_TIME_ABSENT"])
    if pub < ts:
        return _bound(contract, kind, "REFUSED", None, ["PUBLICATION_BEFORE_EVENT_TIME"])
    return _bound(contract, kind, "RESOLVED", pub, ["PUBLICATION_TIMESTAMP"])


# ------------------------------------------------ operational delivery
def _same_contract(contract: Mapping[str, Any], bound: Bound) -> bool:
    return (bound.contract_id == contract.get("contract_id")
            and bound.dataset_sha256 == contract.get("dataset_sha256"))


def operational_delivery_bound(contract: Mapping[str, Any],
                               causal: Bound) -> Bound:
    """When the provider was observed/guaranteed to deliver the datum."""
    kind = "operational_delivery_bound"
    defects = validate_contract(contract)
    if defects:
        return _bound(contract, kind, "REFUSED", None,
                      ["CONTRACT_INVALID"] + [f"CONTRACT_INVALID:{x}" for x in defects])
    if not isinstance(causal, Bound) or causal.kind != "causal_information_bound":
        return _bound(contract, kind, "REFUSED", None, ["BOUND_KIND_MISMATCH"])
    if not _same_contract(contract, causal):
        return _bound(contract, kind, "REFUSED", None, ["BOUND_FROM_OTHER_CONTRACT"])
    if causal.status != "RESOLVED":
        return _bound(contract, kind, "UNRESOLVED", None,
                      ["CAUSAL_BOUND_NOT_RESOLVED", *causal.reasons])
    lat = contract["provider_delivery_latency"]
    if lat["status"] == "UNOBSERVED":
        return _bound(contract, kind, "UNOBSERVED", None,
                      ["PROVIDER_DELIVERY_LATENCY_UNOBSERVED"])
    delay_ms = int(math.ceil(float(lat["seconds"]) * 1000.0))
    return _bound(contract, kind, "RESOLVED", causal.utc_ms + delay_ms,
                  [f"PROVIDER_DELIVERY_LATENCY_{lat['status']}"])


# --------------------------------------------------------------- gates
def gate_e5a(contract: Mapping[str, Any], causal: Bound) -> Gate:
    """Offline experiments: a resolved causal information bound only."""
    if validate_contract(contract):
        return Gate("E5a", "CLOSED", ("CONTRACT_INVALID",))
    if not isinstance(causal, Bound) or causal.kind != "causal_information_bound":
        return Gate("E5a", "CLOSED", ("BOUND_KIND_MISMATCH",))
    if not _same_contract(contract, causal):
        return Gate("E5a", "CLOSED", ("BOUND_FROM_OTHER_CONTRACT",))
    if causal.status != "RESOLVED" or causal.utc_ms is None:
        return Gate("E5a", "CLOSED",
                    ("CAUSAL_INFORMATION_BOUND_NOT_RESOLVED", *causal.reasons))
    return Gate("E5a", "OPEN", ("CAUSAL_INFORMATION_BOUND_RESOLVED",))


def gate_e5b(contract: Mapping[str, Any], causal: Bound,
             operational: Bound | None) -> Gate:
    """Live: BOTH bounds resolved. Offline availability never opens it."""
    a = gate_e5a(contract, causal)
    if not a.is_open:
        return Gate("E5b", "CLOSED", a.reasons)
    if operational is None:
        return Gate("E5b", "CLOSED", ("OPERATIONAL_DELIVERY_BOUND_ABSENT",))
    if not isinstance(operational, Bound):
        return Gate("E5b", "CLOSED", ("BOUND_KIND_MISMATCH",))
    if operational.kind == "causal_information_bound":
        return Gate("E5b", "CLOSED", ("OFFLINE_CAUSAL_BOUND_PRESENTED_AS_OPERATIONAL",))
    if operational.kind != "operational_delivery_bound":
        return Gate("E5b", "CLOSED", ("BOUND_KIND_MISMATCH",))
    if not _same_contract(contract, operational):
        return Gate("E5b", "CLOSED", ("BOUND_FROM_OTHER_CONTRACT",))
    if operational.status != "RESOLVED" or operational.utc_ms is None:
        return Gate("E5b", "CLOSED",
                    ("OPERATIONAL_DELIVERY_BOUND_NOT_RESOLVED", *operational.reasons))
    if operational.utc_ms < causal.utc_ms:
        return Gate("E5b", "CLOSED", ("OPERATIONAL_BOUND_PRECEDES_CAUSAL_BOUND",))
    return Gate("E5b", "OPEN", ("CAUSAL_INFORMATION_BOUND_RESOLVED",
                                "OPERATIONAL_DELIVERY_BOUND_RESOLVED",
                                "NECESSARY_CONDITIONS_ONLY_NOT_A_LIVE_VIABILITY_GRANT"))


# ------------------------------------------------------ dataset level
def evaluate_rows(contract: Mapping[str, Any], rows: Iterable[Mapping[str, Any]],
                  *, observed_sha256: str | None) -> dict[str, Any]:
    """Apply both bounds and both gates to every row; a dataset gate is
    OPEN only if it is OPEN for every row and at least one row exists."""
    n = 0
    causal_status: dict[str, int] = {}
    oper_status: dict[str, int] = {}
    causal_reasons: dict[str, int] = {}
    oper_reasons: dict[str, int] = {}
    e5a_closed: dict[str, int] = {}
    e5b_closed: dict[str, int] = {}
    e5a_all = e5b_all = True
    for row in rows:
        n += 1
        c = causal_information_bound(contract, row, observed_sha256=observed_sha256)
        o = operational_delivery_bound(contract, c)
        ga, gb = gate_e5a(contract, c), gate_e5b(contract, c, o)
        causal_status[c.status] = causal_status.get(c.status, 0) + 1
        oper_status[o.status] = oper_status.get(o.status, 0) + 1
        for r in c.reasons:
            causal_reasons[r] = causal_reasons.get(r, 0) + 1
        for r in o.reasons:
            oper_reasons[r] = oper_reasons.get(r, 0) + 1
        if not ga.is_open:
            e5a_all = False
            for r in ga.reasons:
                e5a_closed[r] = e5a_closed.get(r, 0) + 1
        if not gb.is_open:
            e5b_all = False
            for r in gb.reasons:
                e5b_closed[r] = e5b_closed.get(r, 0) + 1
    if n == 0:
        e5a_all = e5b_all = False
        e5a_closed = {"NO_ROWS_EVALUATED": 0}
        e5b_closed = {"NO_ROWS_EVALUATED": 0}
    return {
        "rows_evaluated": n,
        "causal_information_bound_status_counts": dict(sorted(causal_status.items())),
        "causal_information_bound_reason_counts": dict(sorted(causal_reasons.items())),
        "operational_delivery_bound_status_counts": dict(sorted(oper_status.items())),
        "operational_delivery_bound_reason_counts": dict(sorted(oper_reasons.items())),
        "E5a": {"status": "OPEN" if e5a_all else "CLOSED",
                "closed_reason_counts": dict(sorted(e5a_closed.items()))},
        "E5b": {"status": "OPEN" if e5b_all else "CLOSED",
                "closed_reason_counts": dict(sorted(e5b_closed.items()))},
    }


# -------------------------------------------------------------- schema
def schema_document() -> dict[str, Any]:
    """TEMPORAL_AVAILABILITY_SCHEMA.v1, built from the constants the code
    enforces so the published schema cannot drift from the code."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "Temporal availability contract (C81-C83)",
        "type": "object",
        "required": ["contract_id", "dataset_id", "dataset_sha256",
                     "timestamp_semantics", "information_complete_not_before",
                     "nominal_bar_seconds", "provider_delivery_latency",
                     "provenance"],
        "properties": {
            "contract_id": {"type": "string", "minLength": 1},
            "dataset_id": {"type": "string", "minLength": 1},
            "dataset_sha256": {"type": "string", "pattern": _HEX64.pattern,
                               "description": "Digest of the exact bytes the contract governs. A contract applied to other bytes is refused (DATASET_TRANSPLANTED)."},
            "timestamp_semantics": {"enum": list(TIMESTAMP_SEMANTICS)},
            "information_complete_not_before": {
                "enum": list(CAUSAL_RULES),
                "description": "Must equal the rule implied by timestamp_semantics.",
                "x-rule-by-semantics": dict(CAUSAL_RULE_BY_SEMANTICS)},
            "nominal_bar_seconds": {
                "type": ["integer", "null"], "exclusiveMinimum": 0,
                "description": "NOMINAL bar length. Required for BAR_OPEN. Never used to infer a missing close_time: individual bars may be truncated."},
            "bar_close_time_convention": {"enum": list(CLOSE_TIME_CONVENTIONS),
                                          "description": "Required for BAR_OPEN."},
            "provider_delivery_latency": {
                "type": "object", "required": ["status", "seconds", "evidence"],
                "properties": {
                    "status": {"enum": list(LATENCY_STATUSES)},
                    "seconds": {"type": ["number", "null"], "minimum": 0,
                                "description": "null iff status is UNOBSERVED. UNOBSERVED is never zero."},
                    "evidence": {"type": "string"}}},
            "provenance": {
                "type": "object", "required": ["status", "basis"],
                "properties": {"status": {"enum": list(PROVENANCE_STATUSES)},
                               "basis": {"type": "string", "minLength": 1}}},
        },
        "allOf": [
            {"if": {"properties": {"timestamp_semantics": {"const": "BAR_OPEN"}}},
             "then": {"required": ["bar_close_time_convention"],
                      "properties": {"information_complete_not_before": {"const": "PER_BAR_CLOSE_TIME"},
                                     "nominal_bar_seconds": {"type": "integer"}}}},
            {"if": {"properties": {"timestamp_semantics": {"const": "BAR_CLOSE"}}},
             "then": {"properties": {"information_complete_not_before": {"const": "TIMESTAMP_ITSELF"}}}},
            {"if": {"properties": {"timestamp_semantics": {"const": "PUBLICATION"}}},
             "then": {"properties": {"information_complete_not_before": {"const": "PUBLICATION_TIMESTAMP"}}}},
            {"if": {"properties": {"provider_delivery_latency": {"properties": {"status": {"const": "UNOBSERVED"}}}}},
             "then": {"properties": {"provider_delivery_latency": {"properties": {"seconds": {"const": None}}}}}},
        ],
        "x-row-fields": {
            "timestamp_ms": "integer UTC ms; the dataset timestamp interpreted per timestamp_semantics (event time for PUBLICATION)",
            "close_time_ms": "integer UTC ms; the bar's own close time as recorded by the source",
            "publication_time_ms": "integer UTC ms; PUBLICATION only",
            "next_timestamp_ms": "integer UTC ms; the next SOURCE bar, for overlap and gap detection",
        },
        "x-notions": {
            "causal_information_bound": "Earliest instant the datum could be complete by definition of its period. BAR_OPEN -> per-bar close_time; BAR_CLOSE -> the timestamp; PUBLICATION -> the publication timestamp.",
            "operational_delivery_bound": "Instant the provider was observed or guaranteed to deliver the datum: causal bound + observed/declared latency. UNOBSERVED latency yields an UNOBSERVED bound, never a zero-latency one.",
        },
        "x-gates": {
            "E5a": "Offline experiments. OPEN iff the causal_information_bound is RESOLVED under a valid contract whose dataset_sha256 equals the observed digest.",
            "E5b": "Live. OPEN iff E5a is OPEN AND an operational_delivery_bound (never a causal bound) is RESOLVED, from the same contract, not before the causal bound. OPEN states necessary temporal conditions only; it grants no live viability.",
        },
        "x-enums": {
            "bound_kinds": list(BOUND_KINDS), "bound_statuses": list(BOUND_STATUSES),
            "gate_ids": list(GATE_IDS), "gate_statuses": list(GATE_STATUSES),
            "reason_codes": list(REASON_CODES),
        },
        "x-implementation": {"root_id": "financial-data",
                             "relative_path": "_scripts/temporal_availability.py"},
    }
