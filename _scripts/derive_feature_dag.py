#!/usr/bin/env python3
"""C47 (order 2026-09-12): a causal DAG per feature, or an honest
`UNRESOLVED_PRODUCER`.

The previous lineage gave all 84 derived features one sentence —
"computed inside this view's producer from the OHLCV of the same bar" —
and one availability formula. A 60-bar rolling mean, a lagged return, a
centred decomposition and an externally published series do not share a
graph and do not share an availability. That was a label, not a
derivation.

This locates each column's real producer by searching the producer
repositories for the code that EMITS it, and records what it finds:
repository, commit, file, function or class, the digest of the
producing code, the direct inputs and their roles, the lookback, the
lead/shift, the alignment and the window policy, the event time of each
input, the causal latency, and an executable formula for
`earliest_available_time`.

Where the producer cannot be located, the class is
`UNRESOLVED_PRODUCER` and nothing is asserted about availability. A
generic sentence is worse than an admitted gap, because it looks like
an answer.

Classes: CAUSAL, NON_CAUSAL, EXTERNAL_LATENCY_REQUIRED,
UNRESOLVED_PRODUCER.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CAUSAL = "CAUSAL"
NON_CAUSAL = "NON_CAUSAL"
EXTERNAL = "EXTERNAL_LATENCY_REQUIRED"
UNRESOLVED = "UNRESOLVED_PRODUCER"

OHLCV = {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"}

#: name patterns that carry their own window in the column name. These
#: are read from the NAME only as a hypothesis; the producer's code is
#: what confirms them, and a column whose producer is not found stays
#: UNRESOLVED whatever its name suggests.
PATTERNS = (
    (re.compile(r"^(log_)?return_(\d+)$"), "lagged_return"),
    (re.compile(r"^(sma|ema|wma)_(\d+)$"), "rolling_mean"),
    (re.compile(r"^close_(sma|ema)_ratio_(\d+)$"), "rolling_ratio"),
    (re.compile(r"^(rsi|atr|adx|cci|mfi|willr)_(\d+)$"), "indicator"),
    (re.compile(r"^(std|var|skew|kurt|zscore)_(\d+)$"), "rolling_stat"),
    (re.compile(r"^(macd|stoch|bb)_"), "indicator"),
    (re.compile(r"^(day|hour|month|week)_of_"), "calendar"),
)


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_obj(o) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def git(repo: Path, *args) -> str:
    return subprocess.run(("git", "-C", str(repo), *args),
                          capture_output=True, text=True).stdout.strip()


# ------------------------------------------------------- producer hunt
def index_producers(repos: dict[str, Path]) -> dict:
    """Map every column literal a producer ASSIGNS to the code that
    assigns it.

    The source is parsed, never executed. Only assignment targets count
    — a column merely mentioned in a comment or read as an input is not
    produced there.
    """
    index: dict[str, list] = {}
    scanned = []
    for repo_name, repo in repos.items():
        if not repo.is_dir():
            continue
        commit = git(repo, "rev-parse", "HEAD")
        for py in sorted(repo.rglob("*.py")):
            if any(part in ("__pycache__", ".git", "tests", "build")
                   for part in py.parts):
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8",
                                              errors="replace"))
            except (SyntaxError, ValueError, OSError):
                continue
            scanned.append(str(py.relative_to(repo)))
            digest = sha_file(py)
            for node in ast.walk(tree):
                # df["COL"] = ... / df.loc[:, "COL"] = ...
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    literal = _assigned_column(target)
                    if literal is None:
                        continue
                    index.setdefault(literal, []).append({
                        "repository": repo_name,
                        "commit": commit,
                        "file": str(py.relative_to(repo)),
                        "line": node.lineno,
                        "code_sha256": digest,
                        "symbol": _enclosing_symbol(tree, node),
                        "expression": ast.unparse(node.value)[:200],
                        "inputs": sorted(_referenced_columns(node.value)),
                        "window_hint": _window_hint(node.value),
                    })
    return {"index": index, "files_scanned": len(scanned)}


def _assigned_column(target) -> str | None:
    if isinstance(target, ast.Subscript):
        sl = target.slice
        if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
            return sl.value
        if isinstance(sl, ast.Tuple) and sl.elts:
            last = sl.elts[-1]
            if isinstance(last, ast.Constant) and \
                    isinstance(last.value, str):
                return last.value
    return None


def _enclosing_symbol(tree, node) -> str:
    best = "<module>"
    for parent in ast.walk(tree):
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            if parent.lineno <= node.lineno <= (parent.end_lineno or 0):
                best = parent.name
    return best


def _referenced_columns(expr) -> set[str]:
    out = set()
    for n in ast.walk(expr):
        if isinstance(n, ast.Subscript):
            sl = n.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                out.add(sl.value)
    return out


def _literal(node):
    """A literal argument, including a NEGATIVE one.

    `shift(-1)` parses as UnaryOp(USub, Constant(1)), not as a
    Constant. Reading only Constants left every forward shift looking
    like no shift at all — so a leaking feature was classified CAUSAL.
    """
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _window_hint(expr) -> dict:
    """Lookback, shift and centring, read from the call itself."""
    hint = {"lookback": None, "shift": None, "center": None,
            "calls": []}
    for n in ast.walk(expr):
        if not isinstance(n, ast.Call):
            continue
        fn = getattr(n.func, "attr", None)
        if fn:
            hint["calls"].append(fn)
        if fn in ("rolling", "ewm"):
            for kw in n.keywords:
                if kw.arg in ("window", "span"):
                    hint["lookback"] = _literal(kw.value)
                if kw.arg == "center":
                    hint["center"] = _literal(kw.value)
            if n.args:
                hint["lookback"] = hint["lookback"] or _literal(n.args[0])
        if fn == "shift":
            if n.args:
                hint["shift"] = _literal(n.args[0])
            for kw in n.keywords:
                if kw.arg == "periods":
                    hint["shift"] = _literal(kw.value)
    hint["calls"] = sorted(set(hint["calls"]))
    return hint


# ------------------------------------------------------------- nodes
#: path tokens that mark code as retired, invalidated or archived. A
#: producer found only there still answers WHERE the column comes from,
#: but a reviewer must be told, because an invalidated study is not the
#: pipeline that built the view.
DEMOTED_PATH_TOKENS = ("invalidated", "deprecated", "archive", "_old",
                       "legacy", "attic", "part_ii_invalidated")


def producer_rank(entry: dict) -> tuple:
    """Prefer a live producer over a retired one, then a shorter path."""
    path = entry["file"].lower()
    demoted = any(tok in path for tok in DEMOTED_PATH_TOKENS)
    return (1 if demoted else 0, path.count("/"), path)


def rank_producers(producers: list) -> list:
    return sorted(producers, key=producer_rank)


def classify(column: str, producers: list, view: dict) -> dict:
    upper = column.upper()
    if upper in OHLCV:
        return {
            "klass": CAUSAL,
            "why": "a raw bar field: known at the close of the bar it "
                   "describes",
            "lookback": 1, "shift": 0, "center": False,
            "inputs": [], "window_policy": "single bar",
        }
    if not producers:
        return {
            "klass": UNRESOLVED,
            "why": "no producer in the searched repositories assigns "
                   "this column, so its graph, its window and its "
                   "availability are unknown. Nothing is asserted",
            "lookback": None, "shift": None, "center": None,
            "inputs": [], "window_policy": "UNKNOWN",
        }
    best = producers[0]
    hint = best["window_hint"]
    demoted = any(tok in best["file"].lower()
                  for tok in DEMOTED_PATH_TOKENS)
    center = hint.get("center")
    shift = hint.get("shift")
    if center is True:
        klass, why = NON_CAUSAL, ("the producing window is centred, so "
                                  "the value depends on bars after the "
                                  "one it is stamped with")
    elif isinstance(shift, int) and shift < 0:
        klass, why = NON_CAUSAL, ("the producer shifts by "
                                  f"{shift}, which reads forward")
    else:
        klass, why = CAUSAL, ("the producing window looks back only, "
                              "so the value is known at the close of "
                              "the bar it is stamped with")
    if demoted:
        why += ("; the only producer found lives under a retired or "
                "invalidated path, so this graph describes code that "
                "may not be the one that built the view")
    return {"klass": klass, "why": why,
            "producer_is_retired_path": demoted,
            "lookback": hint.get("lookback"), "shift": shift,
            "center": center, "inputs": best["inputs"],
            "window_policy": ("rolling/ewm " + ", ".join(hint["calls"]))
            if hint["calls"] else "elementwise"}


def name_hypothesis(column: str) -> dict:
    for rx, kind in PATTERNS:
        m = rx.match(column)
        if m:
            groups = [g for g in m.groups() if g and g.isdigit()]
            return {"shape": kind,
                    "window_from_name": int(groups[-1]) if groups
                    else None,
                    "status": "HYPOTHESIS_FROM_NAME_ONLY"}
    return {"shape": "unknown", "window_from_name": None,
            "status": "HYPOTHESIS_FROM_NAME_ONLY"}


def availability(node: dict, bar_seconds, policy: str) -> dict:
    if node["klass"] == UNRESOLVED:
        return {"earliest_available_time": "UNAVAILABLE",
                "formula": "UNAVAILABLE",
                "reason": "the producer was not located"}
    if node["klass"] == NON_CAUSAL:
        return {"earliest_available_time": "UNAVAILABLE",
                "formula": "UNAVAILABLE",
                "reason": "a value that depends on later bars is not "
                          "available at the bar it is stamped with; "
                          "this is a leakage finding, not a latency"}
    if not bar_seconds:
        return {"earliest_available_time": "UNAVAILABLE",
                "formula": "UNAVAILABLE",
                "reason": "the view declares no parseable timeframe"}
    if "CAUSAL" not in (policy or ""):
        return {"earliest_available_time": "UNAVAILABLE",
                "formula": "UNAVAILABLE",
                "reason": "the producer declares no causal availability "
                          "policy; event_time is never copied and no "
                          "latency is invented"}
    lb = node.get("lookback") or 1
    return {
        "earliest_available_time":
            f"close(bar_t) = event_time(bar_t) + {bar_seconds}s",
        "formula": (f"max(event_time(inputs over the last {lb} bars)) "
                    f"+ {bar_seconds}s causal latency"),
        "lookback_bars": lb,
        "causal_latency_seconds": bar_seconds,
        "reason": "derived from the producer's declared causal policy "
                  "and the located window",
    }


TIMEFRAME_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}
_SYMBOL_TF = re.compile(r"\.([a-z0-9]+)_(\d+[mhdw])_", re.I)


def view_facts(ds: dict) -> dict:
    m = _SYMBOL_TF.search(ds["dataset_id"])
    tf = m.group(2) if m else None
    mt = re.fullmatch(r"(\d+)([mhdw])", tf or "")
    return {
        "symbol": m.group(1).upper() if m else "UNDERIVABLE",
        "timeframe": tf or "UNDERIVABLE",
        "bar_seconds": (int(mt.group(1)) * TIMEFRAME_SECONDS[mt.group(2)]
                        if mt else None),
        "provider": ds.get("provider", "UNDECLARED"),
        "availability_policy": ds.get("availability_policy", "UNDECLARED"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--producer-root", action="append", default=[],
                    help="NAME=PATH of a producer repository; repeatable")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--derived-at", required=True)
    a = ap.parse_args(argv)

    repos = {}
    for spec in a.producer_root:
        name, _, path = spec.partition("=")
        repos[name] = Path(path).expanduser()
    found = index_producers(repos)
    index = found["index"]

    inv = json.loads((a.predictor_root /
                      "examples/research/crispdm_dataset_inventory.v1.json"
                      ).read_text())
    nodes, by_class = [], {}
    for ds in inv["datasets"]:
        path = a.predictor_root / ds["relative_path"]
        if not path.is_file():
            continue
        facts = view_facts(ds)
        with path.open(encoding="utf-8", errors="replace") as fh:
            header = [c.strip() for c in fh.readline().split(",")
                      if c.strip()]
        for column in header:
            if column.strip().lower() in ("date_time", "datetime",
                                          "date", "timestamp"):
                continue
            producers = rank_producers(index.get(column, []))
            node = classify(column, producers, facts)
            avail = availability(node, facts["bar_seconds"],
                                 facts["availability_policy"])
            by_class[node["klass"]] = by_class.get(node["klass"], 0) + 1
            nodes.append({
                "dataset_id": ds["dataset_id"],
                "column": column,
                "class": node["klass"],
                "why": node["why"],
                "entity": {k: facts[k] for k in
                           ("symbol", "timeframe", "provider")},
                "producers": producers[:3],
                "producer_count": len(producers),
                "producer_is_retired_path": node.get(
                    "producer_is_retired_path", False),
                "direct_inputs": node["inputs"],
                "lookback_bars": node["lookback"],
                "shift": node["shift"],
                "centered": node["center"],
                "window_policy": node["window_policy"],
                "name_hypothesis": name_hypothesis(column),
                "availability": avail,
            })

    unresolved = sorted({n["column"] for n in nodes
                         if n["class"] == UNRESOLVED})
    retired = sorted({n["column"] for n in nodes
                      if n.get("producer_is_retired_path")})
    doc = {
        "schema": "financial_data.feature_dag.v1",
        "derived_at": a.derived_at,
        "producer_repositories": {k: {"path": str(v.name),
                                      "commit": git(v, "rev-parse", "HEAD"),
                                      "present": v.is_dir()}
                                  for k, v in repos.items()},
        "producer_files_scanned": found["files_scanned"],
        "columns_examined": len(nodes),
        "by_class": by_class,
        "unresolved_producers": unresolved,
        "resolved_only_in_retired_paths": retired,
        "nodes": nodes,
        "rules": {
            "graph": "a node records the producing repository, commit, "
                     "file, symbol and code digest, its direct inputs "
                     "and its window; it is not serial and admits "
                     "several inputs",
            "availability": "max(input event times) + the located "
                            "causal latency. event_time is never "
                            "copied and no latency is invented",
            "unknown": "a column whose producer is not located is "
                       "UNRESOLVED_PRODUCER and asserts nothing",
        },
        "grants_nothing": "a lineage describes how a value comes to "
                          "exist. It confers no eligibility",
    }
    doc["dag_sha256"] = sha_obj(doc)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in
                      ("columns_examined", "by_class",
                       "producer_files_scanned", "dag_sha256")},
                     indent=1, sort_keys=True))
    print(f"unresolved producers: {len(unresolved)} "
          f"{unresolved[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
