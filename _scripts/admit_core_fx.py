"""Admit observed core FX prices on an explicit, source-backed operating calendar."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from consolidate_fx_observations import combine_sources, immutable_parquet, status as consolidated_status, transitions
from native_fx_recovery import audit, weekly_open_grid
from publish_native_fx_quality import copy_closed, file_sha, write_json
from recover_independent_hf_fx import audit_source, compare, verify_m30

BID = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']


def required_hours(config):
    grid = weekly_open_grid(config)
    for item in config.get('closed_intervals', []):
        start, end = pd.Timestamp(item['start']), pd.Timestamp(item['end'])
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError('INVALID_CALENDAR_EXCLUSION')
        grid = grid[~((grid >= start) & (grid < end))]
    return grid


def require_complete(frame, expected):
    values = frame[BID].to_numpy(float)
    if (frame.timestamp.duplicated().any() or not frame.timestamp.is_monotonic_increasing
            or not np.isfinite(values).all() or (values <= 0).any()
            or (frame.BidLow > frame[BID].min(axis=1)).any()
            or (frame.BidHigh < frame[BID].max(axis=1)).any()
            or not frame.available_at.eq(frame.timestamp+pd.Timedelta(hours=1)).all()):
        raise ValueError('INVALID_CORE_OBSERVATIONS')
    if len(expected.difference(pd.DatetimeIndex(frame.timestamp))):
        raise ValueError('MISSING_REQUIRED_OPERATING_HOURS')
    if len(pd.DatetimeIndex(frame.timestamp).difference(expected)):
        raise ValueError('OBSERVATIONS_OUTSIDE_OPERATING_CALENDAR')


def require_declared_clock(comparison):
    rows = comparison['offsets']
    selected = next(r for r in rows if r['offset_hours'] == 0)
    if (selected['common_support_hours'] < 2000
            or selected['ohlc_median_abs_diff_pips'] is None
            or selected['ohlc_median_abs_diff_pips'] > .5
            or selected['ohlc_p95_abs_diff_pips'] > 2
            or any(r['ohlc_median_abs_diff_pips'] < selected['ohlc_median_abs_diff_pips']+2
                   for r in rows if r['offset_hours'] != 0)):
        raise ValueError('DECLARED_UTC_CLOCK_NOT_CORROBORATED')


def session_intervals(grid):
    result = []
    for _, chunk in pd.Series(grid, index=grid).groupby(
            pd.Series(grid, index=grid).diff().ne(pd.Timedelta(hours=1)).cumsum()):
        result.append([chunk.iloc[0].isoformat(), (chunk.iloc[-1]+pd.Timedelta(hours=1)).isoformat()])
    return result


def closure_intervals(opened):
    return [[left[1], right[0]] for left, right in zip(opened, opened[1:])]


def verify_downloads(independent, report, pairs):
    entries = report.get('downloads', [])
    names = [item['file'] for item in entries]
    required = {f'{pair.upper()}_{cadence}.parquet' for pair in pairs for cadence in ('H1', 'M30')}
    if len(names) != len(set(names)) or not required.issubset(names):
        raise ValueError('INDEPENDENT_SOURCE_RECEIPT_COVERAGE_MISSING')
    verified = {}
    for item in entries:
        path = independent/item['file']
        if path.resolve().parent != independent.resolve() or file_sha(path) != item['sha256']:
            raise ValueError('INDEPENDENT_SOURCE_DIGEST_MISMATCH')
        verified[path] = item['sha256']
    return verified


def run(independent, primary, consolidated, output, calendar_path, native_config, pairs=None):
    source_report = json.loads((independent/'report.json').read_text())
    consolidated_status(consolidated)
    calendar = json.loads(calendar_path.read_text())
    config = json.loads(native_config.read_text())
    if pairs is not None:
        if not pairs or len(set(pairs)) != len(pairs) or not set(pairs).issubset(config['pairs']):
            raise ValueError('INVALID_ADMISSION_PAIR_SCOPE')
        config['pairs'] = list(pairs)
    if (calendar.get('schema') != 'financial_data.fx_business_calendar.v1'
            or calendar.get('scope') != 'DECLARED_CONSERVATIVE_BUSINESS_OPERATING_CALENDAR'
            or calendar.get('forced_flatten_hours') != 12 or calendar.get('reopen_min_hours') != 12):
        raise ValueError('BUSINESS_CALENDAR_CONTRACT_REQUIRED')
    config['closed_intervals'] = calendar['closed_intervals']
    expected = required_hours(config)
    before = verify_downloads(independent, source_report, config['pairs'])
    binding = dict(code_sha256=file_sha(__file__), calendar_sha256=file_sha(calendar_path),
        native_config_sha256=file_sha(native_config), independent_report_sha256=file_sha(independent/'report.json'),
        consolidated_receipt_sha256=file_sha(consolidated/'STATUS.json'), pairs=config['pairs'])
    if output.resolve().is_relative_to(independent.resolve()) or output.resolve().is_relative_to(primary.resolve()):
        raise ValueError('OUTPUT_OVERLAPS_SOURCE')
    output.mkdir(parents=True, exist_ok=True)
    if (output/'BINDING.json').exists() and json.loads((output/'BINDING.json').read_text()) != binding:
        raise ValueError('CORE_ADMISSION_IDENTITY_CHANGED')
    write_json(output/'BINDING.json', binding)
    copy_closed(calendar_path, output/'CALENDAR.json')
    write_json(output/'OPEN_SESSION_INTERVALS.json', session_intervals(expected))
    extended = dict(config)
    extended['required_start'] = (pd.Timestamp(config['required_start'])-pd.Timedelta(days=7)).isoformat()
    extended['required_end_exclusive'] = (pd.Timestamp(config['required_end_exclusive'])+pd.Timedelta(days=7)).isoformat()
    closed_path = output/'CLOSURE_INTERVALS.json'
    write_json(closed_path, closure_intervals(session_intervals(required_hours(extended))))
    receipt = dict(schema='financial_data.core_price_inventory.v1', status='PREPARING', admitted=False,
        scope='CORE_PRICES_ONLY', feature_selection_complete=False,
        quote_view='BID_COMPATIBLE_NON_EXECUTABLE_PRICE_REFERENCE',
        coverage_scope=calendar['scope'], global_venue_calendar_certified=False,
        expected_operating_hours=len(expected), binding=binding,
        closure_intervals_file=closed_path.name, closure_intervals_sha256=file_sha(closed_path), pairs={})
    for pair in config['pairs']:
        raw = pd.read_parquet(independent/f'{pair.upper()}_H1.parquet')
        source_audit, hourly = audit_source(raw)
        if (source_audit['in_scope_invalid_or_ambiguous_rows'] != 0
                or not source_audit['monotonic_increasing'] or source_audit['timestamp_timezone'] != 'UTC'
                or source_audit.get('timestamp_ms_disagreements', 0)):
            raise ValueError('INDEPENDENT_SOURCE_QUALITY_FAILED')
        lineage, verified = verify_m30(hourly, pd.read_parquet(independent/f'{pair.upper()}_M30.parquet'))
        if lineage['ohlc_mismatch_hours']:
            raise ValueError('INDEPENDENT_HOURLY_LINEAGE_MISMATCH')
        native = []
        for year in range(2020, 2026):
            path = primary/str(year)/pair/f'{year}-1h.parquet'
            before[path] = file_sha(path)
            metadata = json.loads((path.parent/'MANIFEST.json').read_text())
            if (metadata['files'].get(path.name) != before[path] or metadata['pair'] != pair
                    or metadata['year'] != year or metadata['periodicity'] != 'H1'):
                raise ValueError('NATIVE_SOURCE_CUSTODY_MISMATCH')
            native.append(pd.read_parquet(path).set_index('timestamp'))
        native = pd.concat(native).sort_index()
        comparison, monthly, _ = compare(hourly, native[BID].rename(columns=dict(zip(BID,
            ['open', 'high', 'low', 'close']))), pd.DatetimeIndex([], tz='UTC'))
        require_declared_clock(comparison)
        for month, group in monthly.groupby('month'):
            correct = group[group.offset_hours.eq(0)].iloc[0]
            wrong = group[~group.offset_hours.eq(0)]
            if (correct.common_support_hours < 100 or correct.ohlc_median_abs_diff_pips > .5
                    or correct.ohlc_p95_abs_diff_pips > 2
                    or (wrong.ohlc_median_abs_diff_pips <= correct.ohlc_median_abs_diff_pips+.1).any()):
                raise ValueError('MONTHLY_CLOCK_CORROBORATION_FAILED:'+month)
        good = verified.loc[verified.exactly_verified, 'source_h1_comparison_label']
        chosen = hourly.loc[hourly.index.isin(good), ['open', 'high', 'low', 'close']].copy()
        chosen.columns = BID
        chosen.index.name = 'timestamp'
        chosen = chosen.reset_index()
        chosen['available_at'] = chosen.timestamp+pd.Timedelta(hours=1)
        coherent_id = 'independent-hf:'+pair+':'+file_sha(independent/f'{pair.upper()}_H1.parquet')
        fallback_path = consolidated/f'{pair}.parquet'
        before[fallback_path] = file_sha(fallback_path)
        fallback = pd.read_parquet(fallback_path)
        frame, _ = combine_sources([(coherent_id, chosen), ('verified-fallback:'+pair, fallback)])
        fallback_rows = frame.source_id.eq('verified-fallback:'+pair)
        frame.loc[fallback_rows, 'source_id'] = frame.loc[fallback_rows, 'timestamp'].map(
            fallback.set_index('timestamp').source_id)
        frame = frame[frame.timestamp.isin(expected)].reset_index(drop=True)
        require_complete(frame, expected)
        baseline = audit(frame, config, bid_only=True)
        target = output/f'{pair}.parquet'
        immutable_parquet(target, frame)
        monthly_counts = frame.groupby(frame.timestamp.dt.strftime('%Y-%m')).size().to_dict()
        if set(monthly_counts) != set(pd.period_range('2020-01', '2025-12', freq='M').astype(str)):
            raise ValueError('REQUIRED_MONTH_ABSENT')
        write_json(output/f'QUALITY.{pair}.json', dict(schema='financial_data.core_price_quality.v1',
            operating_hours_verified=True, missing_required_operating_hours=0,
            observed_rows=len(frame), monthly_rows=monthly_counts, outliers=baseline['return_outliers'],
            independent_source_audit=source_audit, independent_lineage=lineage,
            declared_clock_comparison=comparison, source_transitions=transitions(frame)))
        receipt['pairs'][pair] = dict(file=target.name, sha256=file_sha(target), rows=len(frame),
            missing_required_operating_hours=0, monthly_rows=monthly_counts,
            quality_file=f'QUALITY.{pair}.json', quality_sha256=file_sha(output/f'QUALITY.{pair}.json'),
            coherent_source_rows=int(frame.source_id.eq(coherent_id).sum()),
            fallback_rows=int(frame.source_id.ne(coherent_id).sum()),
            availability_semantics='UTC_NATIVE_BAR_START_PLUS_ONE_HOUR')
        write_json(output/'STATUS.json', receipt)
    if any(file_sha(path) != digest for path, digest in before.items()):
        raise ValueError('INPUT_CHANGED_DURING_ADMISSION')
    receipt.update(status='ADMITTED', admitted=True)
    write_json(output/'ADMISSION.json', receipt)
    write_json(output/'STATUS.json', receipt)
    return receipt


def main():
    p = argparse.ArgumentParser(__doc__)
    for name in ('independent-root', 'primary-root', 'consolidated-root', 'output-root'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--calendar', type=Path, default=Path(__file__).parents[1]/'configs/fx_business_calendar.v1.json')
    p.add_argument('--native-config', type=Path, default=Path(__file__).parents[1]/'configs/native_fx_recovery.v1.json')
    p.add_argument('--pairs', nargs='+', choices=['eurusd', 'gbpusd'])
    a = p.parse_args()
    receipt = run(a.independent_root, a.primary_root, a.consolidated_root, a.output_root,
                  a.calendar, a.native_config, a.pairs)
    print(json.dumps(dict(status=receipt['status'], scope=receipt['scope'],
        expected_operating_hours=receipt['expected_operating_hours'], pairs=receipt['pairs'])))


if __name__ == '__main__':
    main()
