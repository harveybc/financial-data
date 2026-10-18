"""Compare native quotes under explicit clock hypotheses; never admit or splice.

Minute timestamps are completed-minute endpoints. Primary H1 prices use their
recorded bar-end availability. Candidate clock hypotheses are diagnostics,
not estimates that this tool promotes to canonical source metadata.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


CLOCKS = ('FIXED_UTC_PLUS_60', 'FIXED_UTC_PLUS_120', 'EUROPE_BERLIN')


def complete_hour_closes(frame, clock):
    if clock not in CLOCKS:
        raise ValueError('UNKNOWN_CLOCK')
    if 'TICKER' in frame and frame.TICKER.nunique() > 1:
        raise ValueError('PAIR_MIXTURE')
    native = pd.DatetimeIndex(pd.to_datetime(frame.timestamp_native, errors='raise'))
    if native.tz is not None:
        raise ValueError('NATIVE_CLOCK_ALREADY_AWARE')
    if native.isna().any() or (native != native.floor('min')).any():
        raise ValueError('NOT_MINUTE_ENDPOINTS')
    if native.has_duplicates:
        raise ValueError('DUPLICATE_MINUTES')
    values = frame.CLOSE.to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('INVALID_PRICE')
    if clock == 'EUROPE_BERLIN':
        utc = native.tz_localize('Europe/Berlin', ambiguous='NaT', nonexistent='NaT').tz_convert('UTC')
    else:
        offset = int(clock.rsplit('_', 1)[1])
        utc = (native - pd.Timedelta(minutes=offset)).tz_localize('UTC')
    quotes = pd.DataFrame({'endpoint': utc, 'CLOSE': values}).dropna().sort_values('endpoint')
    quotes['available_at'] = (quotes.endpoint - pd.Timedelta(minutes=1)).dt.floor('h') + pd.Timedelta(hours=1)
    counts = quotes.groupby('available_at', sort=True).size()
    # Distinct, minute-aligned observations in a 60-minute interval: exactly 60
    # proves full support. A close alone must not stand in for missing minutes.
    complete = counts[counts == 60].index
    closes = quotes[quotes.available_at.isin(complete)].groupby('available_at', as_index=False).tail(1)
    return closes[['available_at', 'CLOSE']].reset_index(drop=True), {
        'observed_minutes': len(frame), 'unresolved_dst_minutes': int(utc.isna().sum()),
        'complete_hours': len(complete), 'incomplete_hours': int((counts != 60).sum())}


def compare(primary, candidate):
    if primary.available_at.duplicated().any() or candidate.available_at.duplicated().any():
        raise ValueError('DUPLICATE_HOURS')
    values = primary.BidClose.to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('INVALID_PRIMARY_PRICE')
    joined = primary[['available_at', 'BidClose']].merge(candidate, on='available_at', validate='one_to_one')
    delta = (joined.BidClose - joined.CLOSE).abs()
    return {'paired_hours': len(joined),
            'candidate_hours_absent_from_primary': len(candidate) - len(joined),
            'median_absolute_quote_difference': float(delta.median()) if len(delta) else None,
            'p95_absolute_quote_difference': float(delta.quantile(.95)) if len(delta) else None,
            'max_absolute_quote_difference': float(delta.max()) if len(delta) else None,
            'rounded_4dp_agreement': int((joined.BidClose.round(4) == joined.CLOSE.round(4)).sum())}


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def run(primary_root, candidate_root):
    primary_root, candidate_root = Path(primary_root), Path(candidate_root)
    files = sorted(candidate_root.glob('*.parquet'))
    if not files:
        raise ValueError('NO_CANDIDATE_FILES')
    primary_files = {pair: sorted(primary_root.glob(f'*/{pair}/*-1h.parquet'))
                     for pair in ('eurusd', 'gbpusd')}
    if any(not paths for paths in primary_files.values()):
        raise ValueError('NO_PRIMARY_FILES_FOR_PAIR')
    report = {'schema': 'financial_data.native_source_clock_diagnostic.v1',
              'state': 'DIAGNOSTIC_NOT_ADMITTED', 'admitted': False,
              'clock_verified': False, 'prices_spliced': False,
              'automatic_clock_selection': False,
              'candidate_quote_side': 'UNVERIFIED_TRADE_ARCHIVE_NOT_ASSUMED_BID',
              'candidate_minute_timestamp': 'COMPLETED_MINUTE_ENDPOINT',
              'code_sha256': sha(Path(__file__)), 'files': [], 'comparisons': []}
    for root, paths, kind in [(candidate_root, files, 'candidate')] + [
            (primary_root, paths, 'primary_' + pair) for pair, paths in primary_files.items()]:
        for path in paths:
            report['files'].append({'kind': kind, 'relative_path': str(path.relative_to(root)),
                                    'sha256': sha(path)})
    candidate = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    for pair, paths in primary_files.items():
        primary = pd.concat([pd.read_parquet(p, columns=['available_at', 'BidClose'])
                             for p in paths], ignore_index=True)
        primary['available_at'] = pd.to_datetime(primary.available_at, utc=True)
        selected = candidate[candidate.TICKER == pair.upper()]
        for clock in CLOCKS:
            bars, diagnostic = complete_hour_closes(selected, clock)
            report['comparisons'].append({'pair': pair, 'clock_hypothesis': clock,
                                          'support': diagnostic, 'overall': compare(primary, bars)})
            for month in sorted(bars.available_at.dt.strftime('%Y-%m').unique()):
                month_bars = bars[bars.available_at.dt.strftime('%Y-%m') == month]
                report['comparisons'].append({'pair': pair, 'clock_hypothesis': clock,
                                              'month_utc': month, 'metrics': compare(primary, month_bars)})
    # Detect replacement during reading, not only byte identity after the fact.
    roots = {'candidate': candidate_root, 'primary_eurusd': primary_root, 'primary_gbpusd': primary_root}
    for record in report['files']:
        if sha(roots[record['kind']] / record['relative_path']) != record['sha256']:
            raise ValueError('SOURCE_CHANGED_DURING_DIAGNOSTIC')
    return report


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--primary-root', required=True)
    parser.add_argument('--candidate-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.primary_root, args.candidate_root)
    output = Path(args.output)
    payload = json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n'
    if output.exists():
        if output.read_text() != payload:
            raise ValueError('DIAGNOSTIC_OUTPUT_CONFLICT')
    else:
        temp = output.with_suffix('.partial')
        try:
            with temp.open('x') as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            os.replace(temp, output)
        finally:
            temp.unlink(missing_ok=True)
    print(json.dumps({'state': result['state'], 'comparisons': len(result['comparisons']),
                      'admitted': False, 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
