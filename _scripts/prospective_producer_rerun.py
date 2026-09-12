#!/usr/bin/env python3
"""C94-C95 (order 2026-09-12): an isolated, prospective rerun of the
CURRENT committed Stage 2.2 producer on the recorded physical input,
written to a NEW, write-once root as a SUCCESSOR dataset.

What it does, in order, and what it refuses:

1. Refuses unless CUDA_VISIBLE_DEVICES is set to the empty string, the
   financial-data checkout holding THIS file is clean (tracked and
   untracked) and its HEAD equals `--expect-commit`, and every executed
   file (this harness, the producer, the assembler, the config) is
   tracked and byte-equal to HEAD.
2. Refuses unless every recorded input and every comparison artifact
   hashes to the digest pinned in the committed config, and the raw
   input's physical schema equals the pinned schema.
3. Refuses unless the output root is absolute, is not a symlink, lies
   outside the checkout and every data root, and is absent or empty.
4. SEALS `PRE_RUN_MANIFEST.json` (commit, tree, executed files and
   symbols with sha256, package versions, input/config digests, schema,
   seeds, output policy, budget and stop conditions) into the output
   root BEFORE any producer code runs.
5. Inside a write guard (no write outside the output root, no
   subprocess, no socket, no DataFrame writer) and a wall budget, runs
   `read_asset`, `compute_technical`, `compute_statistical` in-process
   on a sealed COPY of the input bytes, assembles the successor table
   with the identified assembler, runs the end-to-end prefix-invariance
   probe over every output column, and compares the outputs with the
   old technical/statistical parquet and the historical CSV column by
   column. Old artifacts are only read.
6. Every file is written with O_EXCL and chmod 0o444; a stop after the
   seal writes `STOP_RECORD.json`; success writes
   `POST_RUN_MANIFEST.json` with every output digest.

The run's output is a NEW successor dataset whether or not its values
coincide with the historical artifacts. Equality is reported, never
required, and never turns the historical run into something it was not.

Limitation (declared): the write guard patches Python-level entry points
(open, os.*, subprocess, socket, pandas/pyarrow writers). A C extension
could bypass it; the post-run checks (checkout still clean, inputs and
comparison artifacts re-hashed unchanged) are the backstop.
"""
from __future__ import annotations

import argparse
import ast
import builtins
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
import platform
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.dont_write_bytecode = True

PRE_SCHEMA = "financial_data.prospective_rerun.pre_run_manifest.v1"
POST_SCHEMA = "financial_data.prospective_rerun.post_run_manifest.v1"
STOP_SCHEMA = "financial_data.prospective_rerun.stop_record.v1"
E2E_SCHEMA = "financial_data.prospective_rerun.e2e_prefix_invariance.v1"
CMP_SCHEMA = "financial_data.prospective_rerun.comparison.v1"
CONFIG_SCHEMA = "financial_data.prospective_rerun.config.v1"

PRE_NAME = "PRE_RUN_MANIFEST.json"
POST_NAME = "POST_RUN_MANIFEST.json"
STOP_NAME = "STOP_RECORD.json"
E2E_NAME = "E2E_PREFIX_INVARIANCE.json"
CMP_NAME = "COMPARISON.json"
INPUT_COPY = "inputs/raw_ohlcv.parquet"
TECH_OUT = "producer_outputs/technical.parquet"
STAT_OUT = "producer_outputs/statistical.parquet"
SUCC_PARQUET = "successor/ethusdt_4h_tech_stat_model_ready_successor.parquet"
SUCC_CSV = "successor/ethusdt_4h_tech_stat_model_ready_successor.csv"

EXIT_OK, EXIT_REFUSED, EXIT_STOPPED = 0, 2, 3
VALUE_MODES = ("scale_noise", "nan_inject", "zeros_and_spikes")
ALL_MODES = ("truncate",) + VALUE_MODES

_REAL = {
    "open": builtins.open, "io_open": io.open, "os_open": os.open,
    "mkdir": os.mkdir, "makedirs": os.makedirs, "chmod": os.chmod,
    "write_table": pq.write_table,
}
_HOME = re.compile(r"(/home|/Users|/root)/[^\s'\"]*")


class RerunRefused(RuntimeError):
    """Raised BEFORE the seal; nothing has been written."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class RunStopped(RuntimeError):
    """Raised AFTER the seal; STOP_RECORD.json has been written."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class SandboxViolation(BaseException):
    """BaseException so a producer's `except Exception` cannot swallow it."""


class BudgetExceeded(BaseException):
    pass


# ------------------------------------------------------------- helpers
def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def scrub(text) -> str:
    return _HOME.sub("<path>", str(text))


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with _REAL["open"](path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_bytes(obj) -> bytes:
    text = json.dumps(obj, indent=1, sort_keys=True, allow_nan=False,
                      ensure_ascii=False) + "\n"
    if _HOME.search(text):
        raise ValueError("refusing to publish an absolute home path")
    return text.encode("utf-8")


def sha_obj(obj) -> str:
    return sha_bytes(json.dumps(obj, sort_keys=True, allow_nan=False,
                                separators=(",", ":")).encode("utf-8"))


def seal_obj(obj: dict, field: str) -> dict:
    out = dict(obj)
    out.pop(field, None)
    out[field] = sha_obj({k: v for k, v in out.items() if k != field})
    return out


def git(repo: Path, *args) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                       text=True, check=False)
    if r.returncode != 0:
        raise RerunRefused("GIT_FAILED", scrub(r.stderr.strip())[:300])
    return r.stdout.strip()


def _inside(path, root: Path) -> bool:
    try:
        rp = os.path.realpath(os.fspath(path))
    except TypeError:
        return False
    r = os.path.realpath(root)
    return rp == r or rp.startswith(r + os.sep)


# ---------------------------------------------------- checkout identity
def checkout_identity(repo: Path, expect_commit: str) -> dict:
    repo = Path(repo).resolve()
    top = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    if top != repo:
        raise RerunRefused("NOT_A_CHECKOUT_ROOT")
    status = git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise RerunRefused("CHECKOUT_DIRTY",
                           f"{len(status.splitlines())} entries")
    if not re.fullmatch(r"[0-9a-f]{40}", expect_commit or ""):
        raise RerunRefused("EXPECT_COMMIT_NOT_A_FULL_SHA")
    head = git(repo, "rev-parse", "HEAD")
    if head != expect_commit:
        raise RerunRefused("COMMIT_MISMATCH", f"HEAD={head}")
    return {"commit": head, "tree": git(repo, "rev-parse", "HEAD^{tree}"),
            "clean": True,
            "status_command": "git status --porcelain=v1 "
                              "--untracked-files=all"}


def tracked_file(repo: Path, rel: str) -> dict:
    path = repo / rel
    if not path.is_file():
        raise RerunRefused("EXECUTED_FILE_ABSENT", rel)
    listed = git(repo, "ls-files", "-s", "--", rel)
    if not listed:
        raise RerunRefused("EXECUTED_FILE_UNTRACKED", rel)
    blob = listed.split()[1]
    if git(repo, "hash-object", "--", rel) != blob or \
            git(repo, "rev-parse", f"HEAD:{rel}") != blob:
        raise RerunRefused("EXECUTED_FILE_DIFFERS_FROM_HEAD", rel)
    return {"path": rel, "sha256": sha_file(path), "git_blob": blob}


def called_module_functions(source: str, entries) -> list[str]:
    tree = ast.parse(source)
    defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    seen, stack = set(), list(entries)
    while stack:
        s = stack.pop()
        if s in seen or s not in defs:
            continue
        seen.add(s)
        for n in ast.walk(defs[s]):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id in defs:
                stack.append(n.func.id)
    return sorted(seen)


def declared_literal(source: str, name: str):
    for n in ast.parse(source).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and \
                isinstance(n.targets[0], ast.Name) and \
                n.targets[0].id == name:
            return ast.literal_eval(n.value)
    raise RerunRefused("DECLARATION_ABSENT", name)


def dependencies() -> dict:
    out = {"python": platform.python_version(),
           "python_implementation": platform.python_implementation(),
           "machine": platform.machine(), "system": platform.system(),
           "packages": {}}
    for dist in ("numpy", "pandas", "pyarrow"):
        d = importlib.metadata.distribution(dist)
        record = d.read_text("RECORD") or ""
        out["packages"][dist] = {"version": d.version,
                                 "record_sha256": sha_bytes(record.encode())}
    out["runtime_versions"] = {"numpy": np.__version__,
                               "pandas": pd.__version__,
                               "pyarrow": pa.__version__}
    return out


def arrow_schema_of(data: bytes) -> dict:
    s = pq.read_schema(pa.BufferReader(data))
    return {f.name: str(f.type) for f in s}


# -------------------------------------------------------- write policy
def write_once(root: Path, rel: str, data: bytes) -> dict:
    root = Path(os.path.realpath(root))
    if Path(rel).is_absolute() or ".." in Path(rel).parts:
        raise SandboxViolation("write_once target outside the output root")
    path = root / rel
    if not _inside(path, root):
        raise SandboxViolation("write_once target outside the output root")
    parent = path.parent
    missing = []
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for d in reversed(missing):
        _REAL["mkdir"](d, 0o755)
    fd = _REAL["os_open"](path, os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                          0o644)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    _REAL["chmod"](path, 0o444)
    return {"path": rel, "sha256": sha_bytes(data), "bytes": len(data)}


def parquet_bytes(df: pd.DataFrame) -> bytes:
    table = pa.Table.from_pandas(df, preserve_index=False)
    sink = pa.BufferOutputStream()
    _REAL["write_table"](table, sink)
    return sink.getvalue().to_pybytes()


def csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    _CSV_WRITER(df, buf, index=False)
    return buf.getvalue().encode("utf-8")


_CSV_WRITER = pd.DataFrame.to_csv


class WriteGuard:
    WRITE_FLAGS = (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC
                   | os.O_APPEND)

    def __init__(self, allowed_root: Path):
        self.root = Path(allowed_root)
        self.violations: list[str] = []

    def _refuse(self, what: str):
        self.violations.append(what)
        raise SandboxViolation(what)

    @contextlib.contextmanager
    def active(self):
        g = self

        def guarded_open(file, mode="r", *a, **k):
            if not isinstance(file, int) and \
                    any(c in mode for c in "wax+") and \
                    not _inside(file, g.root):
                g._refuse("open-for-write outside the output root")
            return _REAL["open"](file, mode, *a, **k)

        def guarded_os_open(path, flags, *a, **k):
            if flags & g.WRITE_FLAGS and not _inside(path, g.root):
                g._refuse("os.open-for-write outside the output root")
            return _REAL["os_open"](path, flags, *a, **k)

        def path_op(name, real):
            def op(*a, **k):
                paths = [x for x in a if isinstance(x, (str, bytes,
                                                        os.PathLike))]
                if not paths or not all(_inside(p, g.root) for p in paths):
                    g._refuse(f"os.{name} outside the output root")
                return real(*a, **k)
            return op

        def refuse(name):
            def op(*a, **k):
                g._refuse(f"{name} refused")
            return op

        patches = [(builtins, "open", guarded_open),
                   (io, "open", guarded_open),
                   (os, "open", guarded_os_open)]
        for name in ("mkdir", "makedirs", "rmdir", "remove", "unlink",
                     "rename", "replace", "chmod", "truncate", "symlink",
                     "link", "removedirs", "renames"):
            if hasattr(os, name):
                patches.append((os, name, path_op(name, getattr(os, name))))
        for obj, name in ((subprocess, "Popen"), (subprocess, "run"),
                          (subprocess, "call"), (subprocess, "check_call"),
                          (subprocess, "check_output"), (os, "system"),
                          (os, "popen"), (socket, "socket"),
                          (socket, "create_connection"),
                          (pq, "write_table")):
            patches.append((obj, name, refuse(f"{obj.__name__}.{name}")))
        for cls in (pd.DataFrame, pd.Series):
            for meth in ("to_csv", "to_parquet", "to_pickle", "to_json",
                         "to_excel", "to_feather", "to_hdf", "to_sql",
                         "to_stata", "to_orc", "to_xml"):
                if hasattr(cls, meth):
                    patches.append((cls, meth,
                                    refuse(f"{cls.__name__}.{meth}")))
        saved = [(o, n, getattr(o, n)) for o, n, _ in patches]
        try:
            for o, n, v in patches:
                setattr(o, n, v)
            yield g
        finally:
            for o, n, v in saved:
                setattr(o, n, v)


@contextlib.contextmanager
def wall_budget(seconds: float):
    def handler(signum, frame):
        raise BudgetExceeded(f"wall budget of {seconds}s exhausted")
    old = signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, float(seconds))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, old)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------ C95 end-to-end probe
def perturb_raw(raw: pd.DataFrame, cut_ts, mode: str, rng,
                ts_col: str = "timestamp") -> pd.DataFrame:
    """Change ONLY rows whose timestamp is strictly after `cut_ts`."""
    if mode == "truncate":
        return raw.loc[raw[ts_col] <= cut_ts].copy()
    out = raw.copy()
    mask = (out[ts_col] > cut_ts).to_numpy()
    k = int(mask.sum())
    if k == 0:
        return out
    for c in out.columns:
        if c == ts_col:
            continue
        dt = out[c].dtype
        if pd.api.types.is_datetime64_any_dtype(dt):
            if mode == "scale_noise":
                col = out[c].copy()
                col.iloc[np.flatnonzero(mask)] = (
                    col.iloc[np.flatnonzero(mask)]
                    + pd.to_timedelta(rng.integers(1, 86_400, k), unit="s"))
                out[c] = col
            continue
        if pd.api.types.is_bool_dtype(dt) or \
                not pd.api.types.is_numeric_dtype(dt):
            continue
        vals = out[c].to_numpy(dtype="float64", na_value=np.nan).copy()
        sub = vals[mask]
        if mode == "scale_noise":
            sub = sub * rng.uniform(0.5, 1.5, k) + rng.normal(0, 1, k)
        elif mode == "nan_inject":
            sub = sub.copy()
            sub[rng.random(k) < 0.3] = np.nan
        elif mode == "zeros_and_spikes":
            u = rng.random(k)
            sub = sub.copy()
            sub[u < 0.15] = 0.0
            sub[(u >= 0.15) & (u < 0.30)] *= 1e6
        else:
            raise ValueError(f"unknown perturbation mode {mode}")
        vals[mask] = sub
        if pd.api.types.is_integer_dtype(dt):
            vals = np.where(np.isfinite(vals), np.round(vals), 0)
            out[c] = vals.astype(dt)
        else:
            out[c] = vals.astype(dt)
    return out


def _col_equal(x: pd.Series, y: pd.Series):
    """(equal mask, non-NaN compared count)."""
    if pd.api.types.is_numeric_dtype(x.dtype) and \
            pd.api.types.is_numeric_dtype(y.dtype) and \
            not pd.api.types.is_bool_dtype(x.dtype):
        a = x.to_numpy(dtype="float64", na_value=np.nan)
        b = y.to_numpy(dtype="float64", na_value=np.nan)
        same = (a == b) | (np.isnan(a) & np.isnan(b))
        return same, int((~np.isnan(a)).sum())
    a, b = x.to_numpy(), y.to_numpy()
    same = np.array([(p == q) or (pd.isna(p) and pd.isna(q))
                     for p, q in zip(a, b)], dtype=bool)
    return same, int(pd.notna(x).sum())


def e2e_prefix_probe(raw: pd.DataFrame, pipeline, *, cut_fractions,
                     modes=ALL_MODES, seed: int = 0,
                     ts_col: str = "timestamp",
                     out_ts_col: str = "DATE_TIME") -> dict:
    """Perturb exclusively raw rows after each cut; every output column
    value at or before the cut must be unchanged, and the set of output
    rows at or before the cut must be unchanged."""
    base = pipeline(raw.copy())
    order = raw[ts_col].sort_values(kind="stable").reset_index(drop=True)
    n = len(order)
    cols = [c for c in base.columns if c != out_ts_col]
    per_col = {c: {"runs_pass": 0, "runs_vacuous": 0, "runs_fail": 0,
                   "sensitive_runs": 0, "compared_values": 0,
                   "first_failure": None} for c in cols}
    runs = []
    rng = np.random.default_rng(seed)
    for frac in cut_fractions:
        cut_row = int(round(float(frac) * (n - 1)))
        cut_ts = order.iloc[cut_row]
        for mode in modes:
            pert = perturb_raw(raw, cut_ts, mode, rng, ts_col)
            other = pipeline(pert)
            a = base.loc[base[out_ts_col] <= cut_ts].reset_index(drop=True)
            b = other.loc[other[out_ts_col] <= cut_ts].reset_index(drop=True)
            rowset_equal = len(a) == len(b) and bool(
                (a[out_ts_col] == b[out_ts_col]).all())
            run = {"cut_fraction": float(frac), "cut_row": cut_row,
                   "cut_timestamp": pd.Timestamp(cut_ts).isoformat(),
                   "mode": mode, "output_rows_at_or_before_cut": len(a),
                   "rowset_at_or_before_cut_equal": rowset_equal,
                   "failed_columns": []}
            if mode in VALUE_MODES:
                fa = base.loc[base[out_ts_col] > cut_ts].set_index(out_ts_col)
                fb = other.loc[other[out_ts_col] > cut_ts].set_index(
                    out_ts_col)
                common = fa.index.intersection(fb.index)
                run["rowset_after_cut_changed"] = not (
                    len(common) == len(fa) == len(fb))
            for c in cols:
                st = per_col[c]
                if not rowset_equal:
                    same_all, compared, first = False, 0, 0
                else:
                    same, compared = _col_equal(a[c], b[c])
                    same_all = bool(same.all())
                    first = None if same_all else int(np.argmin(same))
                if not same_all:
                    st["runs_fail"] += 1
                    run["failed_columns"].append(c)
                    if st["first_failure"] is None:
                        st["first_failure"] = {
                            "cut_row": cut_row, "mode": mode,
                            "first_changed_output_row": first,
                            "rowset_changed": not rowset_equal}
                elif compared:
                    st["runs_pass"] += 1
                    st["compared_values"] += compared
                else:
                    st["runs_vacuous"] += 1
                if mode in VALUE_MODES and len(common):
                    s2, _ = _col_equal(fa.loc[common, c], fb.loc[common, c])
                    if not bool(s2.all()):
                        st["sensitive_runs"] += 1
            runs.append(run)
    columns = {}
    for c, st in per_col.items():
        if st["runs_fail"]:
            verdict = "FAIL"
        elif not st["runs_pass"]:
            verdict = "VACUOUS"
        elif not st["sensitive_runs"]:
            verdict = "NOT_DEMONSTRATED_INSENSITIVE_TO_PERTURBATION"
        else:
            verdict = "PASS"
        columns[c] = dict(st, verdict=verdict)
    verdicts = {v["verdict"] for v in columns.values()}
    overall = ("FAIL" if "FAIL" in verdicts else
               "PASS" if verdicts == {"PASS"} else "INCOMPLETE")
    return {"schema": E2E_SCHEMA, "verdict": overall,
            "columns_total": len(columns),
            "columns_pass": sum(v["verdict"] == "PASS"
                                for v in columns.values()),
            "columns_fail": sorted(c for c, v in columns.items()
                                   if v["verdict"] == "FAIL"),
            "columns_not_pass": sorted(c for c, v in columns.items()
                                       if v["verdict"] != "PASS"),
            "modes": list(modes), "cut_fractions": list(cut_fractions),
            "seed": seed, "raw_rows": n, "base_output_rows": len(base),
            "columns": columns, "runs": runs}


def make_pipeline(worker, assembler, symbols: dict):
    read = getattr(worker, symbols["reader"])
    tech_fn = getattr(worker, symbols["technical"])
    stat_fn = getattr(worker, symbols["statistical"])

    def pipeline(raw_stored: pd.DataFrame) -> pd.DataFrame:
        buf = io.BytesIO(parquet_bytes(raw_stored))
        raw = read(buf)
        return assembler.assemble(raw, tech_fn(raw), stat_fn(raw))
    return pipeline


# ------------------------------------------------------- comparisons
def compare_tables(old: pd.DataFrame, new: pd.DataFrame, key: str) -> dict:
    o = old.set_index(key)
    w = new.set_index(key)
    common = o.index.intersection(w.index)
    columns = {}
    for c in sorted(set(o.columns) | set(w.columns)):
        rec = {"in_old": c in o.columns, "in_new": c in w.columns}
        if rec["in_old"] and rec["in_new"]:
            rec["dtype_old"] = str(o[c].dtype)
            rec["dtype_new"] = str(w[c].dtype)
            a = o.loc[common, c].to_numpy(dtype="float64", na_value=np.nan)
            b = w.loc[common, c].to_numpy(dtype="float64", na_value=np.nan)
            eq = (a == b) | (np.isnan(a) & np.isnan(b))
            both = np.isfinite(a) & np.isfinite(b) & ~eq
            a32, b32 = a.astype("float32"), b.astype("float32")
            eq32 = (a32 == b32) | (np.isnan(a32) & np.isnan(b32))
            rec.update({
                "compared_rows": int(len(common)),
                "equal": int(eq.sum()), "differ": int((~eq).sum()),
                "equal_at_float32": int(eq32.sum()),
                "nan_mismatch": int((np.isnan(a) ^ np.isnan(b)).sum()),
                "max_abs_diff": (float(np.abs(a[both] - b[both]).max())
                                 if both.any() else None)})
        columns[c] = rec
    both_cols = [c for c, r in columns.items() if r["in_old"] and r["in_new"]]
    return {
        "rows_old": int(len(o)), "rows_new": int(len(w)),
        "rows_common": int(len(common)),
        "rows_only_old": int(len(o.index.difference(w.index))),
        "rows_only_new": int(len(w.index.difference(o.index))),
        "columns_compared": len(both_cols),
        "columns_all_equal": sum(columns[c]["differ"] == 0
                                 for c in both_cols),
        "columns_with_differences": sorted(c for c in both_cols
                                           if columns[c]["differ"]),
        "columns_equal_only_at_float32": sorted(
            c for c in both_cols if columns[c]["differ"] and
            columns[c]["equal_at_float32"] == columns[c]["compared_rows"]),
        "columns_only_old": sorted(c for c, r in columns.items()
                                   if not r["in_new"]),
        "columns_only_new": sorted(c for c, r in columns.items()
                                   if not r["in_old"]),
        "columns": columns}


# ------------------------------------------------------------- config
def load_config(repo: Path, config_arg: str) -> tuple[dict, dict, bytes]:
    p = Path(config_arg)
    p = (repo / p) if not p.is_absolute() else p
    if not _inside(p, repo):
        raise RerunRefused("CONFIG_OUTSIDE_CHECKOUT")
    rel = str(Path(os.path.realpath(p)).relative_to(os.path.realpath(repo)))
    ident = tracked_file(repo, rel)
    data = p.read_bytes()
    cfg = json.loads(data)
    if cfg.get("schema") != CONFIG_SCHEMA:
        raise RerunRefused("CONFIG_SCHEMA_UNKNOWN")
    for k in ("run_id", "successor_dataset_id", "historical_dataset_id",
              "producer", "assembler", "inputs", "budget", "e2e_probe",
              "expected_raw_schema", "expected_output_columns", "seeds"):
        if k not in cfg:
            raise RerunRefused("CONFIG_FIELD_MISSING", k)
    return cfg, ident, data


def _resolve(spec: dict, data_roots: dict) -> Path:
    rid = spec["root_id"]
    if rid not in data_roots:
        raise RerunRefused("DATA_ROOT_NOT_PROVIDED", rid)
    rel = Path(spec["path"])
    if rel.is_absolute() or ".." in rel.parts:
        raise RerunRefused("DATA_PATH_NOT_RELATIVE", spec["path"])
    return Path(data_roots[rid]) / rel


def check_output_root(out_root: Path, forbidden: list[Path]) -> None:
    if not Path(out_root).is_absolute():
        raise RerunRefused("OUTPUT_ROOT_NOT_ABSOLUTE")
    if Path(out_root).is_symlink():
        raise RerunRefused("OUTPUT_ROOT_IS_SYMLINK")
    for f in forbidden:
        if _inside(out_root, f) or _inside(f, out_root):
            raise RerunRefused("OUTPUT_ROOT_OVERLAPS_CHECKOUT_OR_DATA_ROOT")
    if Path(out_root).exists():
        if not Path(out_root).is_dir():
            raise RerunRefused("OUTPUT_ROOT_NOT_A_DIRECTORY")
        if any(Path(out_root).iterdir()):
            raise RerunRefused("OUTPUT_ROOT_NOT_EMPTY")


# ---------------------------------------------------------------- run
def run(*, config: str, out_root: Path, expect_commit: str,
        data_roots: dict, sealed_at: str | None = None,
        seal_directories: bool = True, harness_file: str | None = None,
        now=utc_now) -> dict:
    t0 = time.monotonic()
    if os.environ.get("CUDA_VISIBLE_DEVICES", None) != "":
        raise RerunRefused("CPU_NOT_FORCED",
                           "set CUDA_VISIBLE_DEVICES to the empty string")
    harness = Path(harness_file or __file__).resolve()
    repo = Path(git(harness.parent, "rev-parse", "--show-toplevel")
                ).resolve()
    identity = checkout_identity(repo, expect_commit)
    cfg, cfg_ident, cfg_bytes = load_config(repo, config)
    files = {"harness": tracked_file(repo, str(harness.relative_to(repo))),
             "config": cfg_ident,
             "producer": tracked_file(repo, cfg["producer"]["file"]),
             "assembler": tracked_file(repo, cfg["assembler"]["file"])}
    roots = {k: Path(v).resolve() for k, v in data_roots.items()}
    out_root = Path(out_root)
    check_output_root(out_root, [repo, *roots.values()])

    inputs, input_bytes = {}, {}
    for key, spec in sorted(cfg["inputs"].items()):
        p = _resolve(spec, roots)
        if not p.is_file():
            raise RerunRefused("INPUT_ABSENT", key)
        data = p.read_bytes()
        digest = sha_bytes(data)
        if digest != spec["sha256"]:
            raise RerunRefused("INPUT_DIGEST_MISMATCH", key)
        inputs[key] = {"root_id": spec["root_id"], "path": spec["path"],
                       "sha256": digest, "bytes": len(data),
                       "established_by": spec.get("established_by", [])}
        input_bytes[key] = data
    comparisons = {}
    for key, spec in sorted(cfg.get("comparisons", {}).items()):
        p = _resolve(spec, roots)
        if not p.is_file():
            raise RerunRefused("COMPARISON_ARTIFACT_ABSENT", key)
        digest = sha_file(p)
        if digest != spec["sha256"]:
            raise RerunRefused("COMPARISON_DIGEST_MISMATCH", key)
        comparisons[key] = {"root_id": spec["root_id"],
                            "path": spec["path"], "sha256": digest,
                            "kind": spec["kind"], "key": spec["key"]}
    raw_schema = arrow_schema_of(input_bytes["raw_ohlcv"])
    if raw_schema != cfg["expected_raw_schema"]:
        raise RerunRefused("RAW_SCHEMA_MISMATCH")

    prod_src = (repo / cfg["producer"]["file"]).read_text(encoding="utf-8")
    asm_src = (repo / cfg["assembler"]["file"]).read_text(encoding="utf-8")
    psym = cfg["producer"]["symbols"]
    budget = float(cfg["budget"]["wall_seconds"])
    pre = {
        "schema": PRE_SCHEMA, "run_id": cfg["run_id"],
        "sealed_at": sealed_at or now(),
        "successor_dataset_id": cfg["successor_dataset_id"],
        "historical_dataset_id": cfg["historical_dataset_id"],
        "repository": {"name": cfg["producer"]["repository"], **identity},
        "executed_files": files,
        "executed_symbols": {
            "producer": called_module_functions(prod_src, psym.values()),
            "assembler": called_module_functions(
                asm_src, [cfg["assembler"]["symbol"]]),
            "harness": ["run", "e2e_prefix_probe", "perturb_raw",
                        "make_pipeline", "compare_tables", "write_once",
                        "parquet_bytes", "csv_bytes"]},
        "producer": cfg["producer"], "assembler": cfg["assembler"],
        "dependencies": dependencies(),
        "environment": {k: os.environ.get(k) for k in (
            "CUDA_VISIBLE_DEVICES", "PYTHONDONTWRITEBYTECODE",
            "PYTHONHASHSEED", "OMP_NUM_THREADS")},
        "config_sha256": cfg_ident["sha256"],
        "config_canonical_sha256": sha_obj(cfg),
        "inputs": inputs, "comparisons": comparisons,
        "raw_physical_schema": raw_schema,
        "expected_output_columns": None,
        "seeds": cfg["seeds"], "e2e_probe": cfg["e2e_probe"],
        "output_root": {"logical_id": cfg["run_id"],
                        "was_empty_or_absent": True,
                        "write_policy": "O_CREAT|O_EXCL then chmod 0o444; "
                                        "directories 0o555 at the end",
                        "planned_outputs": [INPUT_COPY, TECH_OUT, STAT_OUT,
                                            SUCC_PARQUET, SUCC_CSV, E2E_NAME,
                                            CMP_NAME, POST_NAME]},
        "budget": {"wall_seconds": budget},
        "stop_conditions": [
            "BUDGET_EXCEEDED", "SANDBOX_VIOLATION", "PRODUCER_ERROR",
            "ASSEMBLY_REFUSED", "ROW_ALIGNMENT_BROKEN",
            "INPUT_COPY_DIGEST_MISMATCH", "EXECUTED_SOURCE_CHANGED",
            "PIPELINE_DOES_NOT_REPRODUCE_SUCCESSOR",
            "CHECKOUT_DIRTY_AFTER_RUN", "PROTECTED_ARTIFACT_CHANGED"],
        "never_written": ["the recorded inputs", "the comparison artifacts",
                          "the checkout", "any data root"],
        "successor_statement": "the output is a NEW successor dataset even "
                               "if its values coincide with a historical "
                               "artifact; equality is reported, not "
                               "required",
    }
    np.random.seed(int(cfg["seeds"].get("numpy_global", 0)))
    # no assembler code runs before the seal: the declared operations are
    # read as a literal, the output columns come pinned from the config
    pre["expected_output_columns"] = list(cfg["expected_output_columns"])
    pre["assembler_declared_operations"] = declared_literal(
        asm_src, "DECLARED_OPERATIONS")
    pre = seal_obj(pre, "manifest_sha256")

    Path(out_root).mkdir(parents=True, exist_ok=True)
    check_output_root(out_root, [repo, *roots.values()])
    write_once(out_root, PRE_NAME, canonical_bytes(pre))
    written = []
    guard = WriteGuard(out_root)
    stage = "sealed"
    try:
        with wall_budget(budget):
            with guard.active():
                stage = "input_copy"
                rec = write_once(out_root, INPUT_COPY,
                                 input_bytes["raw_ohlcv"])
                written.append(rec)
                copy = out_root / INPUT_COPY
                if sha_file(copy) != inputs["raw_ohlcv"]["sha256"]:
                    raise RunStopped("INPUT_COPY_DIGEST_MISMATCH")
                stage = "load"
                for key, src in (("producer", prod_src),
                                 ("assembler", asm_src)):
                    now_src = (repo / cfg[key]["file"]).read_bytes()
                    if sha_bytes(now_src) != files[key]["sha256"] or \
                            now_src.decode("utf-8") != src:
                        raise RunStopped("EXECUTED_SOURCE_CHANGED", key)
                worker = load_module(repo / cfg["producer"]["file"],
                                     "_successor_producer")
                assembler = load_module(repo / cfg["assembler"]["file"],
                                        "_successor_assembler")
                stage = "produce"
                raw = getattr(worker, psym["reader"])(copy)
                tech = getattr(worker, psym["technical"])(raw)
                stat = getattr(worker, psym["statistical"])(raw)
                for name, fr in (("technical", tech), ("statistical", stat)):
                    if len(fr) != len(raw) or not bool(
                            (fr["timestamp"].reset_index(drop=True)
                             == raw["timestamp"].reset_index(drop=True)
                             ).all()):
                        raise RunStopped("ROW_ALIGNMENT_BROKEN", name)
                written.append(write_once(out_root, TECH_OUT,
                                          parquet_bytes(tech)))
                written.append(write_once(out_root, STAT_OUT,
                                          parquet_bytes(stat)))
                stage = "assemble"
                try:
                    succ = getattr(assembler,
                                   cfg["assembler"]["symbol"])(raw, tech,
                                                               stat)
                except ValueError as exc:
                    raise RunStopped("ASSEMBLY_REFUSED", scrub(exc)[:300])
                succ_pq = parquet_bytes(succ)
                succ_csv = csv_bytes(assembler.to_csv_frame(succ))
                written.append(write_once(out_root, SUCC_PARQUET, succ_pq))
                written.append(write_once(out_root, SUCC_CSV, succ_csv))
                stage = "e2e_probe"
                raw_stored = pd.read_parquet(copy)
                pipeline = make_pipeline(worker, assembler, psym)
                again = pipeline(raw_stored)
                same = compare_tables(succ, again, "DATE_TIME")
                if same["rows_only_old"] or same["rows_only_new"] or \
                        same["columns_with_differences"] or \
                        same["columns_only_old"] or same["columns_only_new"]:
                    raise RunStopped("PIPELINE_DOES_NOT_REPRODUCE_SUCCESSOR")
                e2e = e2e_prefix_probe(
                    raw_stored, pipeline,
                    cut_fractions=cfg["e2e_probe"]["cut_fractions"],
                    modes=tuple(cfg["e2e_probe"]["modes"]),
                    seed=int(cfg["e2e_probe"]["seed"]))
                e2e.update({"run_id": cfg["run_id"],
                            "successor_dataset_id":
                                cfg["successor_dataset_id"],
                            "successor_parquet_sha256": sha_bytes(succ_pq),
                            "input_sha256": inputs["raw_ohlcv"]["sha256"],
                            "pre_run_manifest_sha256":
                                pre["manifest_sha256"],
                            "path_probed": "raw bytes -> read_asset -> "
                                           "compute_technical, "
                                           "compute_statistical -> assemble"
                            })
                written.append(write_once(out_root, E2E_NAME,
                                          canonical_bytes(e2e)))
                stage = "compare"
                cmp_doc = {"schema": CMP_SCHEMA, "run_id": cfg["run_id"],
                           "pre_run_manifest_sha256": pre["manifest_sha256"],
                           "statement": "reported, never required; values "
                                        "that coincide do not bind the "
                                        "historical artifact",
                           "artifacts": {}}
                new_tables = {"technical": pd.read_parquet(out_root / TECH_OUT),
                              "statistical": pd.read_parquet(
                                  out_root / STAT_OUT)}
                new_bytes = {"technical": (out_root / TECH_OUT).read_bytes(),
                             "statistical": (out_root / STAT_OUT).read_bytes()}
                for key, spec in sorted(comparisons.items()):
                    p = _resolve(spec, roots)
                    old_bytes = p.read_bytes()
                    if sha_bytes(old_bytes) != spec["sha256"]:
                        raise RunStopped("PROTECTED_ARTIFACT_CHANGED", key)
                    if spec["kind"] == "parquet_table":
                        target = spec.get("successor_output", key)
                        old = pd.read_parquet(io.BytesIO(old_bytes))
                        res = compare_tables(old, new_tables[target],
                                             spec["key"])
                        res["bytes_identical"] = (old_bytes
                                                  == new_bytes[target])
                    elif spec["kind"] == "csv_table":
                        old = pd.read_csv(io.BytesIO(old_bytes))
                        new = pd.read_csv(io.BytesIO(succ_csv))
                        res = compare_tables(old, new, spec["key"])
                        res["bytes_identical"] = old_bytes == succ_csv
                    else:
                        raise RunStopped("UNKNOWN_COMPARISON_KIND", key)
                    res.update({"old": {"root_id": spec["root_id"],
                                        "path": spec["path"],
                                        "sha256": spec["sha256"]},
                                "kind": spec["kind"]})
                    cmp_doc["artifacts"][key] = res
                written.append(write_once(out_root, CMP_NAME,
                                          canonical_bytes(cmp_doc)))
            if guard.violations:
                raise SandboxViolation("; ".join(guard.violations))
            stage = "post_checks"
            if git(repo, "status", "--porcelain=v1",
                   "--untracked-files=all"):
                raise RunStopped("CHECKOUT_DIRTY_AFTER_RUN")
            for key, spec in list(inputs.items()) + list(comparisons.items()):
                if sha_file(_resolve(spec, roots)) != spec["sha256"]:
                    raise RunStopped("PROTECTED_ARTIFACT_CHANGED", key)
            post = {
                "schema": POST_SCHEMA, "run_id": cfg["run_id"],
                "ended_at": now(),
                "pre_run_manifest_sha256": pre["manifest_sha256"],
                "successor_dataset_id": cfg["successor_dataset_id"],
                "successor_dataset_sha256": sha_bytes(succ_pq),
                "successor_csv_sha256": sha_bytes(succ_csv),
                "input_sha256": inputs["raw_ohlcv"]["sha256"],
                "outputs": sorted(written, key=lambda r: r["path"]),
                "rows": {"raw": int(len(raw)), "technical": int(len(tech)),
                         "statistical": int(len(stat)),
                         "successor": int(len(succ))},
                "successor_columns": list(succ.columns),
                "successor_dtypes": {c: str(t) for c, t in
                                     succ.dtypes.items()},
                "e2e_verdict": e2e["verdict"],
                "e2e_columns_pass": e2e["columns_pass"],
                "e2e_columns_not_pass": e2e["columns_not_pass"],
                "comparison_summary": {
                    k: {x: v[x] for x in (
                        "rows_common", "rows_only_old", "rows_only_new",
                        "columns_compared", "columns_all_equal",
                        "columns_with_differences", "bytes_identical")}
                    for k, v in cmp_doc["artifacts"].items()},
                "post_checks": {"checkout_clean_after_run": True,
                                "inputs_and_comparisons_unchanged": True,
                                "guard_violations": 0},
                "wall_seconds": round(time.monotonic() - t0, 3),
            }
            post = seal_obj(post, "manifest_sha256")
            write_once(out_root, POST_NAME, canonical_bytes(post))
    except BaseException as exc:
        code = (exc.code if isinstance(exc, RunStopped) else
                "BUDGET_EXCEEDED" if isinstance(exc, BudgetExceeded) else
                "SANDBOX_VIOLATION" if isinstance(exc, SandboxViolation) else
                "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else
                "PRODUCER_ERROR")
        stop = seal_obj({
            "schema": STOP_SCHEMA, "run_id": cfg["run_id"],
            "stopped_at": now(), "stage": stage, "code": code,
            "error": scrub(f"{type(exc).__name__}: {exc}")[:500],
            "guard_violations": [scrub(v) for v in guard.violations],
            "pre_run_manifest_sha256": pre["manifest_sha256"],
            "outputs_written_before_stop": written,
            "statement": "no successor dataset is published from a "
                         "stopped run"}, "record_sha256")
        with contextlib.suppress(FileExistsError):
            write_once(out_root, STOP_NAME, canonical_bytes(stop))
        if isinstance(exc, KeyboardInterrupt):
            raise
        raise RunStopped(code, scrub(exc)[:300]) from exc
    if seal_directories:
        for d in sorted({p for p in out_root.rglob("*") if p.is_dir()} |
                        {out_root}, key=lambda p: -len(p.parts)):
            _REAL["chmod"](d, 0o555)
    return {"status": "COMPLETED", "run_id": cfg["run_id"],
            "pre_run_manifest_sha256": pre["manifest_sha256"],
            "post_run_manifest_sha256": post["manifest_sha256"],
            "successor_dataset_sha256": post["successor_dataset_sha256"],
            "rows": post["rows"], "e2e_verdict": e2e["verdict"],
            "e2e_columns_pass": e2e["columns_pass"],
            "comparison_summary": post["comparison_summary"],
            "wall_seconds": post["wall_seconds"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.
                                 RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output-root", required=True, type=Path)
    ap.add_argument("--expect-commit", required=True)
    ap.add_argument("--data-root", action="append", default=[],
                    help="root_id=path, e.g. financial-data=/path")
    ap.add_argument("--sealed-at", default=None)
    ap.add_argument("--no-seal-directories", action="store_true")
    a = ap.parse_args(argv)
    roots = {}
    for spec in a.data_root:
        name, _, path = spec.partition("=")
        roots[name] = Path(path).expanduser()
    try:
        out = run(config=a.config, out_root=a.output_root.expanduser(),
                  expect_commit=a.expect_commit, data_roots=roots,
                  sealed_at=a.sealed_at,
                  seal_directories=not a.no_seal_directories)
    except RerunRefused as exc:
        print(json.dumps({"status": "REFUSED", "code": exc.code,
                          "detail": scrub(exc.detail)}))
        return EXIT_REFUSED
    except RunStopped as exc:
        print(json.dumps({"status": "STOPPED", "code": exc.code,
                          "detail": scrub(exc.detail)}))
        return EXIT_STOPPED
    print(json.dumps(out, indent=1, sort_keys=True))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
