#!/usr/bin/env python3
"""C55-C56 (order 2026-09-12): a TRANSITIVE causal graph, or UNRESOLVED.

The v1 index found assignments. It read one line — the right-hand side
of `df['col'] = ...` — and if it saw no `center=True` and no negative
shift there, it called the column CAUSAL. The evidence showed what that
is worth: `log_return_1 = returns`, `macd = ema12 - ema26`, `stoch_k`,
`cci_14` and `mfi_14` all came out CAUSAL with lookback 1 and NO direct
inputs. A dependency stored in a local variable, or computed by a
helper, was simply invisible; `shift(-1)` behind a helper still is.

This resolves the dataflow INSIDE the defining symbol — locals,
intermediates, and calls to helpers it can trace — and accumulates the
window along every path to a leaf. A leaf is a raw column subscript or
a declared external input. Anything it cannot follow makes the whole
output `UNRESOLVED`, because a graph with one unknown edge proves
nothing about the paths that go through it.

Classes: CAUSAL_ACTIVE, NON_CAUSAL, HISTORICAL_OR_RETIRED_PRODUCER,
EXTERNAL_LATENCY_REQUIRED, UNRESOLVED.

C56: availability is never `event_time + one bar` by default. The
dataset must declare what its timestamp MEANS — bar open, bar close, or
publication — and the provider's latency and each transformation's
latency are added on top. One unresolved leaf or helper leaves the
output unavailable.
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

CAUSAL = "CAUSAL_ACTIVE"
NON_CAUSAL = "NON_CAUSAL"
RETIRED = "HISTORICAL_OR_RETIRED_PRODUCER"
EXTERNAL = "EXTERNAL_LATENCY_REQUIRED"
UNRESOLVED = "UNRESOLVED"

MAX_DEPTH = 12

#: element-wise or reducing methods that neither read forward nor hide a
#: dependency. They are named so an UNFOLLOWED call stays a real signal.
SAFE_METHODS = frozenset({
    "mean", "std", "sum", "min", "max", "abs", "diff", "pct_change",
    "astype", "cumsum", "median", "quantile", "var", "corr", "cov",
    "rank", "replace", "clip", "round", "dropna", "reset_index",
    "squeeze", "to_frame", "copy", "rename", "sub", "add", "mul",
    "div", "pow", "lower", "upper", "strip", "get", "items", "keys",
    "sort_index", "tail", "head", "first", "last", "any", "all",
    "isin", "eq", "ne", "lt", "le", "gt", "ge", "apply", "map",
    "transform", "agg", "count", "nunique", "unique", "value_counts",
})

#: names that are MODULES, so `np.roll(a, -1)` is a function call with
#: the array first, not a method on an object
MODULE_NAMES = frozenset({"np", "numpy", "pd", "pandas", "math",
                          "scipy", "sp", "ta", "talib", "sk", "stats"})

#: parameter names that carry the FRAME itself rather than a value
FRAME_PARAMS = frozenset({
    "df", "data", "frame", "series", "s", "x", "self", "prices",
    "ohlc", "ohlcv", "bars", "d", "input_data",
})

#: operations that read FORWARD in time. Any of them anywhere on a
#: path makes the output non-causal, however deep it is hidden.
FORWARD_CALLS = {"bfill", "backfill"}
RAW_LEAVES = {"OPEN", "HIGH", "LOW", "CLOSE", "VOLUME", "DATE_TIME"}

#: path tokens marking code as retired. A producer found only there
#: still answers WHERE a column comes from, and the answer is declared.
RETIRED_TOKENS = ("invalidated", "deprecated", "archive", "_old",
                  "legacy", "attic")

TIMESTAMP_SEMANTICS = ("BAR_OPEN", "BAR_CLOSE", "PUBLICATION",
                       "UNDECLARED")


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha_obj(o) -> str:
    return hashlib.sha256(
        json.dumps(o, sort_keys=True, default=str).encode()).hexdigest()


def git(repo: Path, *args) -> str:
    return subprocess.run(("git", "-C", str(repo), *args),
                          capture_output=True, text=True).stdout.strip()


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


class Symbol:
    """One function or method, with its locals and its assignments."""

    __slots__ = ("name", "file", "repo", "commit", "code_sha256",
                 "lineno", "locals", "outputs", "returns", "params")

    def __init__(self, node, file, repo, commit, code_sha256):
        self.name = node.name
        self.file = file
        self.repo = repo
        self.commit = commit
        self.code_sha256 = code_sha256
        self.lineno = node.lineno
        self.params = [a.arg for a in node.args.args]
        self.locals: dict[str, ast.AST] = {}
        self.outputs: dict[str, ast.AST] = {}
        self.returns: ast.AST | None = None
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                t = stmt.targets[0]
                col = _assigned_column(t)
                if col is not None:
                    self.outputs[col] = stmt.value
                elif isinstance(t, ast.Name):
                    self.locals.setdefault(t.id, stmt.value)
            elif isinstance(stmt, ast.Return) and stmt.value is not None \
                    and self.returns is None:
                self.returns = stmt.value


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


def index_producers(repos: dict[str, Path]) -> dict:
    """Every symbol that assigns a column, and every symbol at all."""
    by_output: dict[str, list[Symbol]] = {}
    by_name: dict[str, list[Symbol]] = {}
    scanned = 0
    for repo_name, repo in repos.items():
        if not repo.is_dir():
            continue
        commit = git(repo, "rev-parse", "HEAD")
        for py in sorted(repo.rglob("*.py")):
            # a TEST is not a producer. Indexing test files let my own
            # C55 fixtures — which deliberately define `mean`, `helper`
            # and a dozen `compute`s — collide with real helper names
            # and turn six genuinely resolved columns UNRESOLVED.
            if any(part in ("__pycache__", ".git", "build", "tests",
                            "test", ".tox", ".venv", "site-packages")
                   for part in py.parts) \
                    or py.name.startswith("test_") \
                    or py.name.endswith("_test.py") \
                    or py.name == "conftest.py":
                continue
            try:
                tree = ast.parse(py.read_text(encoding="utf-8",
                                              errors="replace"))
            except (SyntaxError, ValueError, OSError):
                continue
            scanned += 1
            rel = str(py.relative_to(repo))
            digest = sha_file(py)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef,
                                         ast.AsyncFunctionDef)):
                    continue
                sym = Symbol(node, rel, repo_name, commit, digest)
                by_name.setdefault(sym.name, []).append(sym)
                for col in sym.outputs:
                    by_output.setdefault(col, []).append(sym)
    return {"by_output": by_output, "by_name": by_name,
            "files_scanned": scanned}


class Walk:
    """One transitive resolution, accumulating what it finds."""

    def __init__(self, by_name: dict):
        self.by_name = by_name
        self.leaves: set[str] = set()
        self.unknown: list[str] = []
        self.forward: list[str] = []
        self.lookbacks: list[int] = []
        self.helpers: list[dict] = []
        self.params_used: set[str] = set()
        self.cycle = False

    def resolve(self, expr, sym: Symbol, depth: int,
                seen: frozenset) -> None:
        if depth > MAX_DEPTH:
            self.unknown.append(f"depth>{MAX_DEPTH}")
            return
        if expr is None:
            self.unknown.append("missing expression")
            return
        for node in ast.walk(expr):
            if isinstance(node, ast.Subscript):
                sl = node.slice
                if isinstance(sl, ast.Constant) and \
                        isinstance(sl.value, str):
                    self.leaves.add(sl.value)
                elif isinstance(sl, (ast.Slice, ast.BinOp)):
                    # df[i+1] or s[1:] can read forward; a static
                    # reader cannot tell which, so it does not guess
                    self.unknown.append(
                        f"positional indexing in {sym.name}")
            elif isinstance(node, ast.Call):
                self._call(node, sym, depth, seen)
            elif isinstance(node, ast.Name):
                if node.id in sym.locals:
                    if node.id in seen:
                        self.cycle = True
                        continue
                    self.resolve(sym.locals[node.id], sym, depth + 1,
                                 seen | {node.id})
                elif node.id in sym.params:
                    # a parameter is not a column. A FRAME parameter is
                    # how the caller hands the data in and resolves to
                    # the subscripts already recorded; any OTHER
                    # parameter is a value from outside the symbol,
                    # and a window whose size arrives as an argument is
                    # not statically known
                    if node.id not in FRAME_PARAMS:
                        self.params_used.add(node.id)

    def _call(self, node: ast.Call, sym: Symbol, depth: int,
              seen: frozenset) -> None:
        # `series.mean()` is a METHOD on an object, not a call to a
        # module-level function named `mean`. Conflating the two made
        # `macd` and `cci_14` UNRESOLVED for the reason "helper mean()
        # is defined 3 times", which was my error, not the code's.
        attr = isinstance(node.func, ast.Attribute)
        on_module = attr and isinstance(node.func.value, ast.Name) \
            and node.func.value.id in MODULE_NAMES
        is_method = attr and not on_module
        fn = (node.func.attr if attr else
              getattr(node.func, "id", None))
        if fn in FORWARD_CALLS:
            self.forward.append(f"{fn}() in {sym.name}")
        if fn in ("rolling", "ewm"):
            lb = None
            for kw in node.keywords:
                if kw.arg in ("window", "span"):
                    lb = _literal(kw.value)
                if kw.arg == "center" and _literal(kw.value) is True:
                    self.forward.append(f"centred window in {sym.name}")
            if lb is None and node.args:
                lb = _literal(node.args[0])
            if isinstance(lb, int):
                self.lookbacks.append(lb)
        if fn in ("shift", "roll"):
            # `series.shift(-1)` carries the amount FIRST; `np.roll(a,
            # -1)` carries the array first and the amount SECOND.
            # Reading args[0] for both made every np.roll UNRESOLVED
            # instead of the detectable leak it is.
            idx = 1 if (fn == "roll" and on_module) else 0
            amount = (_literal(node.args[idx])
                      if len(node.args) > idx else None)
            for kw in node.keywords:
                if kw.arg in ("periods", "shift"):
                    amount = _literal(kw.value)
            if isinstance(amount, int) and amount < 0:
                self.forward.append(
                    f"{fn}({amount}) in {sym.name}")
            elif isinstance(amount, int):
                self.lookbacks.append(abs(amount))
            elif amount is None:
                self.unknown.append(f"{fn}() with a non-literal amount")
        if fn == "fillna":
            for kw in node.keywords:
                if kw.arg == "method" and _literal(kw.value) in (
                        "bfill", "backfill"):
                    self.forward.append(f"fillna(bfill) in {sym.name}")
        # follow a helper defined anywhere in the indexed producers
        # ONLY a bare-name call can be a module-level helper in the
        # indexed repositories. `np.log(...)` is neither a method nor
        # one of our helpers, and resolving it against the seventeen
        # local functions named `log` was my second error here.
        if fn and not attr and fn in self.by_name and \
                fn not in ("rolling", "ewm"):
            targets = self.by_name[fn]
            if len(targets) > 1:
                self.unknown.append(
                    f"helper {fn}() is defined {len(targets)} times")
                return
            helper = targets[0]
            if helper.name in seen:
                self.cycle = True
                return
            self.helpers.append({"symbol": helper.name,
                                 "file": helper.file,
                                 "repo": helper.repo})
            if helper.returns is None:
                self.unknown.append(f"helper {fn}() returns nothing "
                                    "traceable")
                return
            self.resolve(helper.returns, helper, depth + 1,
                         seen | {helper.name})
        elif fn and not (attr and fn in SAFE_METHODS) and \
                fn not in ("rolling", "ewm", "shift", "roll",
                               "mean", "std", "sum", "min", "max",
                               "abs", "diff", "pct_change", "apply",
                               "astype", "fillna", "log", "sqrt",
                               "where", "clip", "round", "float",
                               "int", "len", "range", "bfill",
                               "backfill", "ffill", "cumsum", "shape",
                               "values", "to_numpy", "Series",
                               "DataFrame", "array", "asarray",
                               "concat", "isna", "notna", "median",
                               "quantile", "var", "corr", "cov",
                               "rank", "sign", "exp", "maximum",
                               "minimum", "nan_to_num", "reindex"):
            self.unknown.append(f"unfollowed call {fn}()")


def classify(column: str, symbols: list, by_name: dict) -> dict:
    if column.upper() in RAW_LEAVES:
        return {"klass": CAUSAL, "why": "a raw bar field",
                "leaves": [column], "lookback": 1, "forward": [],
                "unknown": [], "params": [], "helpers": [],
                "producer": None}
    if not symbols:
        return {"klass": UNRESOLVED,
                "why": "no producer in the searched repositories "
                       "assigns this column",
                "leaves": [], "lookback": None, "forward": [],
                "unknown": ["no producer"], "params": [], "helpers": [],
                "producer": None}
    live = [s for s in symbols
            if not any(t in s.file.lower() for t in RETIRED_TOKENS)]
    retired_only = not live
    sym = (live or symbols)[0]
    walk = Walk(by_name)
    walk.resolve(sym.outputs[column], sym, 0, frozenset())

    producer = {"repository": sym.repo, "commit": sym.commit,
                "file": sym.file, "symbol": sym.name,
                "line": sym.lineno, "code_sha256": sym.code_sha256}
    leaves = sorted(c for c in walk.leaves if not c.startswith("<"))
    params = sorted(walk.params_used)
    lookback = max(walk.lookbacks) if walk.lookbacks else None
    if walk.cycle:
        return {"klass": UNRESOLVED,
                "why": "the dataflow contains a cycle",
                "leaves": leaves, "lookback": lookback,
                "forward": walk.forward, "unknown": ["cycle"], "params": params,
                "helpers": walk.helpers, "producer": producer}
    if walk.unknown:
        return {"klass": UNRESOLVED,
                "why": "a dependency could not be followed: "
                       + "; ".join(sorted(set(walk.unknown))[:3]),
                "leaves": leaves, "lookback": lookback,
                "forward": walk.forward,
                "unknown": sorted(set(walk.unknown)), "params": params,
                "helpers": walk.helpers, "producer": producer}
    if walk.forward:
        return {"klass": NON_CAUSAL,
                "why": "a path reads forward in time: "
                       + "; ".join(sorted(set(walk.forward))[:3]),
                "leaves": leaves, "lookback": lookback,
                "forward": sorted(set(walk.forward)), "unknown": [], "params": params,
                "helpers": walk.helpers, "producer": producer}
    if not leaves:
        return {"klass": UNRESOLVED,
                "why": "the expression reaches no leaf, so nothing is "
                       "known about its inputs",
                "leaves": [], "lookback": lookback, "forward": [],
                "unknown": ["no leaf"], "params": params, "helpers": walk.helpers,
                "producer": producer}
    if lookback is None and params:
        return {"klass": UNRESOLVED,
                "why": "the window size arrives as a parameter "
                       f"({', '.join(params)}), so no lookback is "
                       "statically known",
                "leaves": leaves, "lookback": None, "forward": [],
                "unknown": [f"window from parameter {p}"
                            for p in params],
                "params": params, "helpers": walk.helpers,
                "producer": producer}
    klass = RETIRED if retired_only else CAUSAL
    return {"klass": klass,
            "why": ("every path ends at a declared leaf and none reads "
                    "forward"
                    + ("; the only producer found lives under a "
                       "retired path" if retired_only else "")),
            "leaves": leaves, "lookback": lookback or 1,
            "forward": [], "unknown": [], "params": params, "helpers": walk.helpers,
            "producer": producer}


# ---------------------------------------------------- C56 availability
TIMEFRAME_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 604800}


def availability(node: dict, dataset: dict) -> dict:
    """C56: never `event_time + one bar` by default."""
    semantics = dataset.get("timestamp_semantics", "UNDECLARED")
    if node["klass"] in (UNRESOLVED, NON_CAUSAL):
        return {"earliest_available_time": "UNAVAILABLE",
                "reason": ("an unresolved path" if node["klass"] ==
                           UNRESOLVED else "a forward-looking path")
                          + " leaves the whole output unavailable"}
    if semantics == "UNDECLARED":
        return {"earliest_available_time": "UNAVAILABLE",
                "reason": "the dataset does not declare what its "
                          "timestamp MEANS — bar open, bar close or "
                          "publication. event_time is never copied and "
                          "no bar width is assumed"}
    bar = dataset.get("bar_seconds")
    provider = dataset.get("provider_latency_seconds")
    if bar is None or provider is None:
        missing = [k for k, v in (("bar_seconds", bar),
                                  ("provider_latency_seconds", provider))
                   if v is None]
        return {"earliest_available_time": "UNAVAILABLE",
                "reason": f"the dataset declares no {missing}"}
    lb = node.get("lookback") or 1
    base = 0 if semantics == "PUBLICATION" else (
        bar if semantics == "BAR_OPEN" else 0)
    total = base + provider
    return {
        "earliest_available_time":
            f"event_time(last input bar) + {total}s",
        "formula": (f"max(event_time over the last {lb} bars) "
                    f"+ {base}s to reach the bar close under "
                    f"{semantics} + {provider}s provider latency"),
        "timestamp_semantics": semantics,
        "lookback_bars": lb,
        "provider_latency_seconds": provider,
        "reason": "derived from the declared timestamp semantics, the "
                  "provider latency and the resolved window",
    }


_SYMBOL_TF = re.compile(r"\.([a-z0-9]+)_(\d+[mhdw])_", re.I)


def dataset_facts(ds: dict, contracts: dict) -> dict:
    m = _SYMBOL_TF.search(ds["dataset_id"])
    tf = m.group(2) if m else None
    mt = re.fullmatch(r"(\d+)([mhdw])", tf or "")
    declared = contracts.get(ds["dataset_id"], {})
    return {
        "dataset_id": ds["dataset_id"],
        "symbol": m.group(1).upper() if m else "UNDERIVABLE",
        "timeframe": tf or "UNDERIVABLE",
        "bar_seconds": (int(mt.group(1)) * TIMEFRAME_SECONDS[mt.group(2)]
                        if mt else None),
        "provider": ds.get("provider", "UNDECLARED"),
        "timestamp_semantics": declared.get("timestamp_semantics",
                                            "UNDECLARED"),
        "provider_latency_seconds": declared.get(
            "provider_latency_seconds"),
        "contract_source": ("DECLARED_BY_DATASET_CONTRACT" if declared
                            else "NO_CONTRACT_DECLARED"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--predictor-root", required=True, type=Path)
    ap.add_argument("--producer-root", action="append", default=[])
    ap.add_argument("--contracts", type=Path, default=None,
                    help="per-dataset timestamp semantics and provider "
                         "latency; absent means UNDECLARED")
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--derived-at", required=True)
    a = ap.parse_args(argv)

    repos = {}
    for spec in a.producer_root:
        name, _, path = spec.partition("=")
        repos[name] = Path(path).expanduser()
    found = index_producers(repos)
    contracts = (json.loads(a.contracts.read_text())
                 if a.contracts and a.contracts.is_file() else {})

    inv = json.loads((a.predictor_root /
                      "examples/research/crispdm_dataset_inventory.v1.json"
                      ).read_text())
    nodes, by_class = [], {}
    for ds in inv["datasets"]:
        path = a.predictor_root / ds["relative_path"]
        if not path.is_file():
            continue
        facts = dataset_facts(ds, contracts)
        with path.open(encoding="utf-8", errors="replace") as fh:
            header = [c.strip() for c in fh.readline().split(",")
                      if c.strip()]
        for column in header:
            if column.strip().lower() in ("date_time", "datetime",
                                          "date", "timestamp"):
                continue
            node = classify(column, found["by_output"].get(column, []),
                            found["by_name"])
            avail = availability(node, facts)
            by_class[node["klass"]] = by_class.get(node["klass"], 0) + 1
            nodes.append({
                "dataset_id": ds["dataset_id"], "column": column,
                "class": node["klass"], "why": node["why"],
                "entity": {k: facts[k] for k in
                           ("symbol", "timeframe", "provider",
                            "timestamp_semantics", "contract_source")},
                "producer": node["producer"],
                "leaves": node["leaves"],
                "parameter_inputs": node["params"],
                "helpers_followed": node["helpers"],
                "lookback_bars": node["lookback"],
                "forward_reads": node["forward"],
                "unresolved_because": node["unknown"],
                "availability": avail,
            })

    doc = {
        "schema": "financial_data.feature_dag.v2",
        "derived_at": a.derived_at,
        "supersedes": "financial_data.feature_dag.v1 — which read one "
                      "assignment line and called the result causal",
        "producer_repositories": {
            k: {"commit": git(v, "rev-parse", "HEAD"),
                "present": v.is_dir()} for k, v in repos.items()},
        "producer_files_scanned": found["files_scanned"],
        "symbols_indexed": sum(len(v) for v in
                               found["by_name"].values()),
        "columns_examined": len(nodes),
        "by_class": by_class,
        "unresolved": sorted({n["column"] for n in nodes
                              if n["class"] == UNRESOLVED}),
        "non_causal": sorted({n["column"] for n in nodes
                              if n["class"] == NON_CAUSAL}),
        "nodes": nodes,
        "rules": {
            "transitive": "locals and intermediates are resolved inside "
                          "the defining symbol and helpers are followed "
                          "where they can be traced; every path ends at "
                          "a leaf or the output is UNRESOLVED",
            "forward": "a centred window, a negative shift or roll, a "
                       "bfill or positional indexing anywhere on a path "
                       "makes the output NON_CAUSAL",
            "availability": "never event_time + one bar by default: the "
                            "dataset must declare what its timestamp "
                            "means, and provider latency is added",
            "unknown": "one unfollowed call, one ambiguous helper or "
                       "one cycle leaves the whole output UNRESOLVED",
        },
        "grants_nothing": "a lineage describes how a value comes to "
                          "exist. It confers no eligibility",
    }
    doc["dag_sha256"] = sha_obj(doc)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: doc[k] for k in
                      ("columns_examined", "by_class",
                       "producer_files_scanned", "symbols_indexed",
                       "dag_sha256")}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
