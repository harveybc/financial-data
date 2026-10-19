"""Apply a bounded, independently checked clock correction to observed raw bars."""
import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from histdata_clock_resolution import clock, raw_minutes
from publish_native_fx_quality import copy_closed, file_sha, write_json
from recover_forexite_observations import parse as parse_forexite

HYPOTHESIS = 'EUROPEAN_DST_COHORT_HYPOTHESIS'
CONTROLS = (-60, -1, 0, 1, 60)
DEFAULTS = dict(minimum_consecutive_pairs=120, minimum_return_correlation=.75,
                minimum_control_margin=.25, maximum_witness_p95_quote_difference=.0006)


def return_statistics(joined):
    ordered = joined.sort_values('endpoint')
    changes = ordered.drop(columns='endpoint').diff()
    changes = changes[ordered.endpoint.diff().eq(pd.Timedelta(minutes=1))]
    correlations = {}
    for column in changes.columns:
        if column == 'reference':
            continue
        usable = (len(changes) > 1 and changes.reference.std() > 0 and changes[column].std() > 0)
        value = changes.reference.corr(changes[column]) if usable else np.nan
        correlations[column] = float(value) if np.isfinite(value) else None
    return dict(consecutive_pairs=len(changes), correlations=correlations)


def witness_statistics(reference, candidate):
    if reference.endpoint.duplicated().any() or candidate.endpoint.duplicated().any():
        raise ValueError('DUPLICATE_WITNESS_ENDPOINT')
    joined = reference.rename(columns={'close': 'reference'})[['endpoint', 'reference']]
    for shift in CONTROLS:
        other = candidate[['endpoint', 'close']].copy()
        other.endpoint -= pd.Timedelta(minutes=shift)
        joined = joined.merge(other.rename(columns={'close': str(shift)}), on='endpoint', validate='one_to_one')
    stats = return_statistics(joined)
    delta = (joined.reference - joined['0']).abs()
    stats.update(common_minutes=len(joined), p95_absolute_quote_difference=float(delta.quantile(.95))
                 if len(delta) else None)
    return stats


def require_witness(stats, limits=None):
    limits = limits or DEFAULTS
    aligned = stats['correlations'].get('0')
    controls = [stats['correlations'].get(str(k)) for k in CONTROLS if k != 0]
    if (stats['consecutive_pairs'] < limits['minimum_consecutive_pairs'] or aligned is None
            or any(value is None for value in controls)
            or aligned < limits['minimum_return_correlation']
            or aligned - max(controls) < limits['minimum_control_margin']
            or stats['p95_absolute_quote_difference'] is None
            or stats['p95_absolute_quote_difference'] > limits['maximum_witness_p95_quote_difference']):
        raise ValueError('CLOCK_WITNESS_FAILED')


def complete_bars(frame):
    native = pd.DatetimeIndex(frame.native)
    if native.has_duplicates or native.isna().any() or not native.equals(native.floor('min')):
        raise ValueError('INVALID_NATIVE_MINUTES')
    values = frame[['open', 'high', 'low', 'close']].to_numpy(float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('INVALID_PRICE')
    if ((frame.high < frame[['open', 'low', 'close']].max(axis=1)).any()
            or (frame.low > frame[['open', 'high', 'close']].min(axis=1)).any()):
        raise ValueError('INVALID_OHLC')
    source = frame[['open', 'high', 'low', 'close']].copy()
    source.index = clock(native, HYPOTHESIS)
    source = source.sort_index()
    counts = source.groupby(source.index.floor('h')).size()
    bars = source.resample('h').agg(dict(open='first', high='max', low='min', close='last'))
    bars = bars.loc[counts[counts.eq(60)].index].rename(columns={
        'open': 'BidOpen', 'high': 'BidHigh', 'low': 'BidLow', 'close': 'BidClose'})
    bars.index.name = 'timestamp'
    bars = bars.reset_index()
    bars['available_at'] = bars.timestamp + pd.Timedelta(hours=1)
    bars['observed_minutes'] = 60
    return bars, int(counts.ne(60).sum())


def safe_member(root, name):
    path = (root / name).resolve()
    if Path(name).is_absolute() or not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('MISSING_OR_ESCAPING_INPUT')
    return path


def corroborate(minutes, pair, bulk, config):
    candidate = pd.DataFrame(dict(endpoint=clock(minutes.native, HYPOTHESIS)
                                 + pd.Timedelta(minutes=1), close=minutes.close.to_numpy()))
    reports = []
    for date in config['witness_dates']:
        day = pd.Timestamp(date)
        source = safe_member(bulk, 'forexite/' + day.strftime('%d%m%y') + '.zip')
        before = file_sha(source)
        reference = parse_forexite(source.read_bytes(), day)
        reference = reference[reference.TICKER.eq(pair.upper())]
        reference = pd.DataFrame(dict(endpoint=reference.timestamp_native.dt.tz_localize(
            'Europe/Berlin', ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC'),
            close=reference.CLOSE.to_numpy()))
        stats = witness_statistics(reference, candidate)
        require_witness(stats, config)
        if file_sha(source) != before:
            raise ValueError('WITNESS_CHANGED')
        reports.append(dict(pair=pair, date=date, source_file=str(source.relative_to(bulk)),
                            source_sha256=before, **stats))
    return reports


def primary_check(bars, path, config):
    before = file_sha(path)
    primary = pd.read_parquet(path, columns=['available_at', 'BidClose'])
    joined = primary.merge(bars[['available_at', 'BidClose']], on='available_at',
                           suffixes=('_primary', '_candidate'), validate='one_to_one')
    delta = (joined.BidClose_primary - joined.BidClose_candidate).abs()
    stats = dict(paired_hours=len(delta), median_absolute_quote_difference=float(delta.median()),
                 p95_absolute_quote_difference=float(delta.quantile(.95)))
    if (len(delta) < config['minimum_primary_paired_hours']
            or not np.isfinite(delta).all()
            or stats['median_absolute_quote_difference'] > config['maximum_primary_median_quote_difference']
            or stats['p95_absolute_quote_difference'] > config['maximum_primary_p95_quote_difference']):
        raise ValueError('PRIMARY_CLOCK_CORROBORATION_FAILED')
    if file_sha(path) != before:
        raise ValueError('PRIMARY_CHANGED')
    return dict(source_sha256=before, **stats)


def status(root):
    result = json.loads((root / 'STATUS.json').read_text())
    if (result.get('schema') != 'financial_data.histdata_observed_normalization.v1'
            or result.get('admitted') is not False
            or file_sha(root / 'CLOCK_CONTRACT.json') != result['binding']['config_sha256']):
        raise ValueError('NORMALIZED_CONTRACT_CHANGED')
    if result.get('clock_verified'):
        scope = {(f['pair'], f['year']) for f in result['files']}
        if (result['state'] != 'CLOCK_CORRECTED_COMPLETE_HOUR_CANDIDATES'
                or len(result['files']) != 6 or scope != {(p, y) for p in ('eurusd', 'gbpusd')
                                                         for y in (2023, 2024, 2025)}
                or len(result['witnesses']) != 6):
            raise ValueError('NORMALIZED_COHORT_INCOMPLETE')
    for item in result['files']:
        path = safe_member(root, item['output_file'])
        if file_sha(path) != item['output_sha256']:
            raise ValueError('NORMALIZED_OUTPUT_CHANGED')
        frame = pd.read_parquet(path)
        if (len(frame) != item['rows'] or not frame.observed_minutes.eq(60).all()
                or not frame.available_at.eq(frame.timestamp + pd.Timedelta(hours=1)).all()):
            raise ValueError('NORMALIZED_OUTPUT_COUNTS_OR_CLOCK_CHANGED')
    return result


def run(bulk, primary, output, config_path):
    config = json.loads(config_path.read_text())
    if (config.get('schema') != 'financial_data.histdata_observed_clock.v1'
            or config.get('hypothesis') != HYPOTHESIS or config.get('quote_view') != 'BID'):
        raise ValueError('OBSERVED_CLOCK_CONTRACT_REQUIRED')
    if (len(config['sources']) != 6 or {(s['pair'], s['year']) for s in config['sources']}
            != {(p, y) for p in ('eurusd', 'gbpusd') for y in (2023, 2024, 2025)}):
        raise ValueError('EXACT_REVIEWED_COHORT_REQUIRED')
    binding = dict(config_sha256=file_sha(config_path), code_sha256=file_sha(__file__),
                   parser_sha256=file_sha(Path(__file__).with_name('histdata_clock_resolution.py')),
                   witness_parser_sha256=file_sha(Path(__file__).with_name('recover_forexite_observations.py')),
                   versions=dict(python=sys.version.split()[0], pandas=pd.__version__, numpy=np.__version__))
    if output.resolve().is_relative_to(primary.resolve()):
        raise ValueError('OUTPUT_OVERLAPS_PRIMARY')
    output.mkdir(parents=True, exist_ok=True)
    seal = output / 'BINDING.json'
    if seal.exists() and json.loads(seal.read_text()) != binding:
        raise ValueError('NORMALIZATION_BINDING_CHANGED')
    retained_config = output / 'CLOCK_CONTRACT.json'
    if retained_config.exists() and file_sha(retained_config) != binding['config_sha256']:
        raise ValueError('RETAINED_CLOCK_CONTRACT_CHANGED')
    if not retained_config.exists():
        copy_closed(config_path, retained_config)
    write_json(seal, binding)
    report = dict(schema='financial_data.histdata_observed_normalization.v1',
                  state='NORMALIZING', clock_verified=False, admitted=False,
                  provider_clock_confirmed=False, basis=config['basis'], interpolated_values=0,
                  files=[], witnesses=[], binding=binding)
    for item in config['sources']:
        path = safe_member(bulk, item['file'])
        if file_sha(path) != item['sha256']:
            raise ValueError('RAW_SOURCE_DIGEST_MISMATCH')
        minutes, duplicates = raw_minutes(path, item['pair'], item['year'])
        if item['year'] == 2023:
            report['witnesses'].extend(corroborate(minutes, item['pair'], bulk, config))
        bars, incomplete = complete_bars(minutes)
        check = primary_check(bars, primary / str(item['year']) / item['pair']
                              / f"{item['year']}-1h.parquet", config)
        bars['source_id'] = f"histdata:{item['pair']}:{item['year']}:{item['sha256']}"
        target = output / f"{item['pair']}-{item['year']}.parquet"
        if target.exists():
            pd.testing.assert_frame_equal(pd.read_parquet(target), bars, check_exact=True)
        else:
            temporary = target.with_suffix('.partial')
            bars.to_parquet(temporary, index=False)
            with temporary.open('rb') as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        if file_sha(path) != item['sha256']:
            raise ValueError('RAW_SOURCE_CHANGED')
        report['files'].append(dict(pair=item['pair'], year=item['year'],
            source_file=item['file'], source_sha256=item['sha256'], raw_minutes=len(minutes),
            identical_duplicates_removed=duplicates, incomplete_hours=incomplete,
            output_file=target.name, output_sha256=file_sha(target), rows=len(bars), primary_check=check))
        write_json(output / 'STATUS.json', report)
    if len(report['witnesses']) != 6 or len(report['files']) != 6:
        raise ValueError('FULL_COHORT_AND_WITNESSES_REQUIRED')
    report.update(state='CLOCK_CORRECTED_COMPLETE_HOUR_CANDIDATES', clock_verified=True)
    write_json(output / 'STATUS.json', report)
    return status(output)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--bulk-root', type=Path)
    parser.add_argument('--primary-root', type=Path)
    parser.add_argument('--config', type=Path, default=Path(__file__).parents[1] / 'configs/histdata_observed_clock.v1.json')
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if not args.status and (args.bulk_root is None or args.primary_root is None):
        parser.error('normalization requires bulk-root and primary-root')
    result = status(args.output_root) if args.status else run(
        args.bulk_root, args.primary_root, args.output_root, args.config)
    print(json.dumps(dict(state=result['state'], clock_verified=result['clock_verified'],
                          admitted=False, completed_files=len(result['files']),
                          complete_hours=sum(f['rows'] for f in result['files']))))


if __name__ == '__main__':
    main()
