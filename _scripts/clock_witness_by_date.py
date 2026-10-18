"""Per-date clock and quote-side witness for the Forexite candidate against the native FXCM H1 feed.

Diagnostic only: every hypothesis is scored, none is selected, no offset is fitted, no price is
spliced. A lower difference under one hypothesis is evidence for a human ruling, not a verified
timezone or quote side. Outputs aggregate differences and hashes, never provider rows."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location('native_comparison', Path(__file__).with_name('compare_native_fx_sources.py'))
compare_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(compare_module)
CLOCKS = compare_module.CLOCKS
SIDES = ('bid', 'ask', 'mid')


def _side_series(primary, side):
    if side == 'bid':
        return primary.BidClose
    if side == 'ask':
        return primary.AskClose
    return (primary.BidClose + primary.AskClose) / 2


def _stats(delta):
    if not len(delta):
        return {'paired_hours': 0, 'median_abs': None, 'p95_abs': None, 'max_abs': None, 'agree_4dp': 0}
    return {'paired_hours': int(len(delta)), 'median_abs': float(delta.abs().median()),
            'p95_abs': float(delta.abs().quantile(.95)), 'max_abs': float(delta.abs().max()),
            'agree_4dp': int((delta.abs() < 5e-5).sum())}


def hypothesis_table(primary, candidate):
    """One row per clock hypothesis with bid/ask/mid differences; clock_verified is always False."""
    primary = primary.copy()
    primary['available_at'] = pd.to_datetime(primary.available_at, utc=True)
    rows = []
    for clock in CLOCKS:
        bars, support = compare_module.complete_hour_closes(candidate, clock)
        joined = primary.merge(bars, on='available_at', validate='one_to_one')
        row = {'clock_hypothesis': clock, 'support': support, 'clock_verified': False, 'quote_side_verified': False}
        for side in SIDES:
            if side != 'bid' and 'AskClose' not in primary:
                continue
            row[side] = _stats(_side_series(joined, side) - joined.CLOSE)
        rows.append(row)
    return rows


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(primary_root, candidate_root, histdata_1h=None):
    primary_root, candidate_root = Path(primary_root), Path(candidate_root)
    report = {'schema': 'financial_data.clock_witness_by_date.v1', 'state': 'DIAGNOSTIC_NOT_ADMITTED',
              'admitted': False, 'clock_verified': False, 'quote_side_verified': False,
              'automatic_selection': False, 'code_sha256': sha(__file__), 'files': [], 'dates': [], 'summary': {}}
    primaries = {}
    for pair in ('eurusd', 'gbpusd'):
        paths = sorted(primary_root.glob(f'*/{pair}/*-1h.parquet'))
        if not paths:
            raise ValueError('NO_PRIMARY_FILES_FOR_PAIR')
        frame = pd.concat([pd.read_parquet(p, columns=['available_at', 'BidClose', 'AskClose']) for p in paths], ignore_index=True)
        frame['available_at'] = pd.to_datetime(frame.available_at, utc=True)
        primaries[pair] = frame
        report['files'] += [{'kind': f'primary_{pair}', 'relative_path': str(p.relative_to(primary_root)), 'sha256': sha(p)} for p in paths]
    files = sorted(candidate_root.glob('*.parquet'))
    if not files:
        raise ValueError('NO_CANDIDATE_FILES')
    totals = {}
    for path in files:
        report['files'].append({'kind': 'candidate', 'relative_path': path.name, 'sha256': sha(path)})
        day = pd.read_parquet(path)
        native_date = str(pd.Timestamp(day.timestamp_native.min()).date())
        for pair in ('eurusd', 'gbpusd'):
            selected = day[day.TICKER == pair.upper()]
            if selected.empty:
                continue
            table = hypothesis_table(primaries[pair], selected)
            report['dates'].append({'archive': path.name, 'native_date': native_date, 'pair': pair, 'hypotheses': table})
            for row in table:
                for side in SIDES:
                    key = (pair, row['clock_hypothesis'], side)
                    if side in row and row[side]['paired_hours']:
                        totals.setdefault(key, []).append((row[side]['paired_hours'], row[side]['p95_abs'], row[side]['max_abs']))
    for (pair, clock, side), values in sorted(totals.items()):
        hours = np.array([v[0] for v in values])
        report['summary'][f'{pair}|{clock}|{side}'] = {
            'dates_with_pairs': int(len(values)), 'paired_hours': int(hours.sum()),
            'worst_date_max_abs': float(max(v[2] for v in values)),
            'median_of_daily_p95': float(np.median([v[1] for v in values]))}
    if histdata_1h:
        report['histdata_lake_1h'] = histdata_overlap(histdata_1h, primaries)
    for record in report['files']:
        root = candidate_root if record['kind'] == 'candidate' else primary_root
        if sha(root / record['relative_path']) != record['sha256']:
            raise ValueError('SOURCE_CHANGED_DURING_DIAGNOSTIC')
    return report


def histdata_overlap(path, primaries):
    """Existing lake HistData EURUSD 1h (labelled UTC) versus the native feed under two label hypotheses.

    HistData documents EST without DST; the lake file carries a UTC label. Both readings are scored;
    neither is selected. Reused existing data: no acquisition request is made."""
    frame = pd.read_parquet(path, columns=['datetime', 'close'])
    out = {'file_sha256': sha(path), 'rows': int(len(frame)), 'label_hypotheses': {}}
    stamp = pd.to_datetime(frame.datetime, utc=True)
    for label, offset in (('AS_LABELLED_UTC_BAR_START', 0), ('LABEL_IS_EST_FIXED_BAR_START', 5)):
        available = stamp + pd.Timedelta(hours=1 + offset)
        bars = pd.DataFrame({'available_at': available, 'CLOSE': frame.close.to_numpy(float)})
        joined = primaries['eurusd'].merge(bars, on='available_at', validate='one_to_one')
        out['label_hypotheses'][label] = {side: _stats(_side_series(joined, side) - joined.CLOSE) for side in SIDES}
    return out


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--primary-root', required=True)
    parser.add_argument('--candidate-root', required=True)
    parser.add_argument('--histdata-1h', default=None)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.primary_root, args.candidate_root, args.histdata_1h)
    payload = json.dumps(result, sort_keys=True, indent=1, allow_nan=False) + '\n'
    output = Path(args.output)
    if output.exists() and output.read_text() != payload:
        raise ValueError('DIAGNOSTIC_OUTPUT_CONFLICT')
    temp = output.with_suffix('.partial')
    temp.write_text(payload)
    os.replace(temp, output)
    print(json.dumps({'state': result['state'], 'dates': len(result['dates']), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
