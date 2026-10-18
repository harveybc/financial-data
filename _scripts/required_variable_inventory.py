"""REQUIRED_VARIABLE_INVENTORY candidate (order 2026-10-18 D.5): configured population, not existing files.

Three explicitly separated groups: every configured catalog variable (features/cross_source_docs
provenance), trading-required native variables (configs/native_fx_recovery.v1.json) and model
candidates (an external feature manifest with raw dependencies). Missing files stay in the
denominator; population sizes are counted, never hardcoded. Monthly coverage is computed in
chunks so one bounded process never loads the whole lake. Candidate only: no admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED_START, REQUIRED_END = '2020-01-01', '2026-01-01'
#: Model-candidate prefix -> raw dependency description (from the predictor availability contract vocabulary).
PREFIX_DEPENDENCY = {
    'fred.': ('macro_economic/fred', 'daily or lower, US business days', 'publisher release after event date (declared lag per feature)'),
    'yh.': ('market_data (yfinance daily)', 'daily close', 'exchange close of the event day'),
    'fx.': ('native FX hourly (FXCM H1)', 'hourly bar', 'bar end'),
    'px.': ('native FX hourly (FXCM H1 EURUSD)', 'hourly bar', 'bar end'),
    'rg.': ('native FX hourly (FXCM H1 EURUSD)', 'hourly bar', 'bar end'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def monthly(path, time_col=None, start=REQUIRED_START, end=REQUIRED_END):
    frame = pd.read_parquet(path)
    col = time_col or _time_column(frame)
    if col is None:
        return {'time_column': None, 'rows': int(len(frame)), 'coverage_error': 'NO_TIME_COLUMN_IDENTIFIED'}
    ts = pd.to_datetime(frame[col], utc=True, errors='coerce')
    months = pd.period_range(pd.Timestamp(start, tz='UTC'), pd.Timestamp(end, tz='UTC') - pd.Timedelta(seconds=1), freq='M')
    counts = ts.dt.to_period('M').value_counts()
    numeric = frame.select_dtypes('number')
    spacing = ts.sort_values().diff().dropna()
    spacing = spacing[spacing > pd.Timedelta(0)]
    cadence = str(spacing.median()) if len(spacing) else 'SINGLE_OR_NONE'
    return {'time_column': col, 'rows': int(len(frame)), 'first': ts.min().isoformat() if len(ts) else None,
            'last': ts.max().isoformat() if len(ts) else None, 'inferred_median_spacing': cadence,
            'unparseable_timestamps': int(ts.isna().sum()),
            'nonfinite_cells': int((~np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan))).sum()) if not numeric.empty else 0,
            'duplicate_timestamps': int(ts.duplicated().sum()),
            'monthly_coverage': [{'month': str(m), 'observed_rows': int(counts.get(m, 0))} for m in months]}


def _time_column(frame):
    for name in ('timestamp', 'datetime', 'date', 'Date', 'observation_date', 'DateTime', 'time'):
        if name in frame.columns:
            return name
    for name in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[name]):
            return name
    for name in frame.columns:
        if frame[name].dtype == object:
            parsed = pd.to_datetime(frame[name].head(50), utc=True, errors='coerce')
            if parsed.notna().mean() > 0.9:
                return name
    return None


def build(repo_root, native_cfg, model_candidates, lake_root=None, chunk=(0, 1), availability=None):
    repo_root = Path(repo_root)
    docs = repo_root / 'features/cross_source_docs'
    variables = []
    slugs = sorted(p.name for p in docs.iterdir() if (p / 'provenance.json').is_file()) if docs.is_dir() else []
    for slug in slugs:
        prov = json.loads((docs / slug / 'provenance.json').read_text())
        variables.append({'variable_id': f'catalog:{slug}', 'group': 'ALL_CATALOG_VARIABLES', 'dataset_path': prov['source'],
                          'columns': prov.get('columns'), 'declared_rows_native': prov.get('rows_native'),
                          'declared_start': prov.get('start'), 'declared_end': prov.get('end'),
                          'native_cadence': 'DECLARED_IN_DATA_DICTIONARY_NOT_VERIFIED', 'timezone': 'UTC_TARGET_GRID_PER_DICTIONARY',
                          'quote_side': 'N/A_OR_UNSTATED', 'units': 'SOURCE_UNITS_UNSTATED',
                          'revision_availability': 'UNDECLARED_IN_CATALOG', 'role': 'RAW_SOURCE'})
    for pair in native_cfg['pairs']:
        for side in ('BID', 'ASK'):
            variables.append({'variable_id': f'native:{pair}:{native_cfg["periodicity"]}:{side}', 'group': 'TRADING_REQUIRED',
                              'dataset_path': f'<native recovery output>/<year>/{pair}/<year>-1h.parquet',
                              'columns': [side.title() + k for k in ('Open', 'High', 'Low', 'Close')],
                              'native_cadence': 'H1', 'timezone': 'UTC bar START; available_at = bar end (parser)',
                              'quote_side': side if side == 'BID' else 'ASK_RETAINED_NOT_EXECUTABLE_SPREAD',
                              'units': f'{pair[:3].upper()} quoted in {pair[3:].upper()}', 'revision_availability': 'bar end, no revision',
                              'required_start': native_cfg['required_start'], 'required_end_exclusive': native_cfg['required_end_exclusive'],
                              'role': 'RAW_PRICE', 'provider': native_cfg['provider'],
                              'configured_view': native_cfg['quote_view']})
    variables.append({'variable_id': 'calendar:fx_session', 'group': 'TRADING_REQUIRED', 'dataset_path': None,
                      'native_cadence': 'weekly session', 'timezone': 'America/New_York (assumed 17:00 open/close)',
                      'quote_side': 'N/A', 'units': 'N/A', 'revision_availability': 'versioned calendar required',
                      'role': 'CALENDAR', 'status': native_cfg.get('calendar_basis', 'ASSUMED_NOT_CERTIFIED')})
    for name in model_candidates:
        prefix = next((p for p in PREFIX_DEPENDENCY if name.startswith(p)), None)
        dep = PREFIX_DEPENDENCY.get(prefix, ('UNKNOWN', 'UNKNOWN', 'UNKNOWN'))
        decl = (availability or {}).get(name, {})
        variables.append({'variable_id': f'model:{name}', 'group': 'MODEL_CANDIDATES', 'role': 'DERIVED_FEATURE',
                          'raw_dependency': dep[0], 'native_cadence': dep[1], 'revision_availability': dep[2],
                          'availability_source': decl.get('availability_source', 'NOT_DECLARED'),
                          'timezone': 'UTC decision grid', 'quote_side': 'BID (px/rg/fx) or N/A', 'units': 'transformed'})
    if lake_root is not None:
        lake_root = Path(lake_root)
        paths = [v for v in variables if v.get('dataset_path') and not v['dataset_path'].startswith('<')]
        i, n = chunk
        for k, v in enumerate(paths):
            target = lake_root / v['dataset_path']
            v['file_status'] = 'PRESENT' if target.is_file() else 'MISSING'
            if v['file_status'] == 'PRESENT' and k % n == i:
                try:
                    v['sha256'] = sha(target)
                    v['bytes'] = target.stat().st_size
                    v.update(monthly(target))
                except Exception as exc:
                    v['coverage_error'] = f'{type(exc).__name__}:{exc}'[:200]
    groups = {}
    for v in variables:
        groups[v['group']] = groups.get(v['group'], 0) + 1
    present = sum(1 for v in variables if v.get('file_status') == 'PRESENT')
    missing = sum(1 for v in variables if v.get('file_status') == 'MISSING')
    return {'schema': 'financial_data.required_variable_inventory.candidate.v1', 'state': 'CANDIDATE_NOT_ADMITTED',
            'admitted': False, 'selection_complete': False,
            'denominator': {'all_catalog_variables': groups.get('ALL_CATALOG_VARIABLES', 0),
                            'trading_required': groups.get('TRADING_REQUIRED', 0),
                            'model_candidates': groups.get('MODEL_CANDIDATES', 0), 'total_records': len(variables),
                            'files_present': present, 'files_missing': missing},
            'hardcoded_population_sizes': [], 'chunk': list(chunk), 'variables': variables}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--repo-root', required=True)
    parser.add_argument('--native-config', required=True)
    parser.add_argument('--model-manifest', help='JSON list of model-candidate feature names', default=None)
    parser.add_argument('--availability-contract', default=None)
    parser.add_argument('--lake-root', default=None)
    parser.add_argument('--chunk', default='0/1', help='i/n: compute coverage for files with index %% n == i')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    cfg = json.loads(Path(args.native_config).read_text())
    candidates = json.loads(Path(args.model_manifest).read_text()) if args.model_manifest else []
    availability = None
    if args.availability_contract:
        contract = json.loads(Path(args.availability_contract).read_text())
        availability = {d['feature']: d for d in contract.get('declarations', [])}
    i, n = (int(x) for x in args.chunk.split('/'))
    result = build(args.repo_root, cfg, candidates, args.lake_root, (i, n), availability)
    out = Path(args.output)
    tmp = out.with_suffix('.partial')
    tmp.write_text(json.dumps(result, sort_keys=True, indent=1, default=str) + '\n')
    os.replace(tmp, out)
    print(json.dumps(result['denominator']))


if __name__ == '__main__':
    main()
