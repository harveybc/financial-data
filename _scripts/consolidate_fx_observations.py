"""Consolidate verified observed bid candles and expose every unresolved hour."""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from native_fx_recovery import audit, weekly_open_grid
from normalize_histdata_observed_clock import status as normalized_status
from publish_native_fx_quality import file_sha, write_json
from recover_fxcm_boundary import status as boundary_status

BID = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']


def combine_sources(sources):
    accepted, seen, counts = [], set(), {}
    for identity, source in sources:
        frame = source[['timestamp', 'available_at', *BID]].copy()
        if frame.timestamp.duplicated().any():
            raise ValueError('SOURCE_DUPLICATE_TIMESTAMPS')
        for column in ('timestamp', 'available_at'):
            if str(getattr(frame[column].dtype, 'tz', None)) != 'UTC' or frame[column].isna().any():
                raise ValueError('UTC_SOURCE_CLOCK_REQUIRED')
        if not frame.timestamp.eq(frame.timestamp.dt.floor('h')).all():
            raise ValueError('HOURLY_SOURCE_CLOCK_REQUIRED')
        if not frame.available_at.eq(frame.timestamp + pd.Timedelta(hours=1)).all():
            raise ValueError('SOURCE_AVAILABILITY_MISMATCH')
        values = frame[BID].to_numpy(float)
        if not np.isfinite(values).all() or (values <= 0).any():
            raise ValueError('INVALID_SOURCE_PRICE')
        if ((frame.BidHigh < frame[BID].max(axis=1)).any()
                or (frame.BidLow > frame[BID].min(axis=1)).any()):
            raise ValueError('INVALID_SOURCE_OHLC')
        selected = frame[~frame.timestamp.isin(seen)].copy()
        selected['source_id'] = identity
        counts[identity] = len(selected)
        seen.update(selected.timestamp)
        accepted.append(selected)
    if not accepted:
        raise ValueError('NO_OBSERVATIONS')
    result = pd.concat(accepted, ignore_index=True).sort_values('timestamp').reset_index(drop=True)
    return result, counts


def transitions(frame):
    changed = frame.source_id.ne(frame.source_id.shift()) & frame.source_id.shift().notna()
    rows = []
    for i in np.flatnonzero(changed.to_numpy()):
        previous, current = frame.iloc[i-1], frame.iloc[i]
        rows.append(dict(timestamp=current.timestamp.isoformat(), previous_source=previous.source_id,
                         source=current.source_id,
                         elapsed_hours=float((current.timestamp-previous.timestamp).total_seconds()/3600),
                         observed_log_return=float(np.log(current.BidClose/previous.BidClose))))
    return rows


def immutable_parquet(path, frame):
    if path.exists():
        pd.testing.assert_frame_equal(pd.read_parquet(path), frame, check_exact=True)
    else:
        temporary = path.with_suffix('.partial')
        frame.to_parquet(temporary, index=False)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)


def run(primary, normalized, boundary, output, config_path):
    correction = normalized_status(normalized)
    if not correction.get('clock_verified'):
        raise ValueError('VERIFIED_CLOCK_CORRECTION_REQUIRED')
    boundary_status(boundary)
    recovered = json.loads((boundary / 'MANIFEST.json').read_text())
    config = json.loads(config_path.read_text())
    binding = dict(config_sha256=file_sha(config_path), code_sha256=file_sha(__file__),
                   quality_code_sha256=file_sha(Path(__file__).with_name('native_fx_recovery.py')),
                   normalized_receipt_sha256=file_sha(normalized / 'STATUS.json'),
                   boundary_receipt_sha256=file_sha(boundary / 'MANIFEST.json'))
    if any(output.resolve().is_relative_to(p.resolve()) for p in (primary, normalized, boundary)):
        raise ValueError('OUTPUT_OVERLAPS_INPUT')
    output.mkdir(parents=True, exist_ok=True)
    seal = output / 'BINDING.json'
    if seal.exists() and json.loads(seal.read_text()) != binding:
        raise ValueError('CONSOLIDATION_IDENTITY_CHANGED')
    write_json(seal, binding)
    result = dict(schema='financial_data.observed_fx_consolidation.v1',
                  state='CONSOLIDATING', admitted=False, clock_verified=True,
                  calendar_holidays_certified=False, interpolated_values=0, pairs={}, binding=binding)
    for pair in config['pairs']:
        sources, source_files = [], []
        for year in range(pd.Timestamp(config['required_start']).year,
                          pd.Timestamp(config['required_end_exclusive']).year):
            path = primary / str(year) / pair / f'{year}-1h.parquet'
            digest = file_sha(path)
            expected = next(b['sha256'] for b in recovered['pairs'][pair]['baselines']
                            if b['file'] == str(path.relative_to(primary)))
            if digest != expected:
                raise ValueError('PRIMARY_SOURCE_CHANGED')
            source_files.append((path, digest))
            sources.append((f'fxcm:{pair}:{year}:{digest}', pd.read_parquet(path)))
        item = recovered['pairs'][pair]
        path = boundary / item['candidate_file']
        source_files.append((path, item['candidate_sha256']))
        sources.append((f'fxcm:boundary:{pair}:{item["source_sha256"]}', pd.read_parquet(path)))
        for item in correction['files']:
            if item['pair'] != pair:
                continue
            path = normalized / item['output_file']
            source_files.append((path, item['output_sha256']))
            sources.append((f'histdata:{pair}:{item["year"]}:{item["source_sha256"]}', pd.read_parquet(path)))
        frame, counts = combine_sources(sources)
        frame = frame[frame.timestamp.ge(pd.Timestamp(config['required_start']))
                      & frame.timestamp.lt(pd.Timestamp(config['required_end_exclusive']))].reset_index(drop=True)
        closed = ~frame.timestamp.isin(weekly_open_grid(config))
        closed_rows = int(closed.sum())
        frame = frame.loc[~closed].reset_index(drop=True)
        quality = audit(frame, config, bid_only=True)
        quality['source_sha256'] = {f'{pair}.parquet': ''}
        target = output / f'{pair}.parquet'
        immutable_parquet(target, frame)
        quality['source_sha256'][target.name] = file_sha(target)
        write_json(output / f'QUALITY.{pair}.json', quality)
        if any(file_sha(path) != digest for path, digest in source_files):
            raise ValueError('SOURCE_CHANGED_DURING_CONSOLIDATION')
        result['pairs'][pair] = dict(rows=len(frame), output_file=target.name, output_sha256=file_sha(target),
            observations_excluded_by_closed_weekly_schedule=closed_rows,
            source_row_counts=frame.groupby('source_id').size().to_dict(),
            source_transitions=transitions(frame), missing_expected_open_hours=quality['missing_expected_open_hours'],
            outside_assumed_open_schedule_rows=quality['outside_assumed_open_schedule_rows'],
            quality_sha256=file_sha(output / f'QUALITY.{pair}.json'))
        write_json(output / 'STATUS.json', result)
    result['state'] = 'OBSERVATIONS_CONSOLIDATED_REQUIRES_CALENDAR_AND_COVERAGE'
    write_json(output / 'STATUS.json', result)
    return status(output)


def status(root):
    result = json.loads((root / 'STATUS.json').read_text())
    for pair, item in result['pairs'].items():
        path = root / item['output_file']
        if path.resolve().parent != root.resolve() or file_sha(path) != item['output_sha256']:
            raise ValueError('CONSOLIDATED_OUTPUT_CHANGED')
        if file_sha(root / f'QUALITY.{pair}.json') != item['quality_sha256']:
            raise ValueError('CONSOLIDATED_QUALITY_CHANGED')
    return result


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--primary-root', type=Path)
    parser.add_argument('--normalized-root', type=Path)
    parser.add_argument('--boundary-root', type=Path)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=Path(__file__).parents[1] / 'configs/native_fx_recovery.v1.json')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if not args.status and any(p is None for p in (args.primary_root, args.normalized_root, args.boundary_root)):
        parser.error('consolidation requires all three input roots')
    result = status(args.output_root) if args.status else run(
        args.primary_root, args.normalized_root, args.boundary_root, args.output_root, args.config)
    print(json.dumps(dict(state=result['state'], clock_verified=result['clock_verified'], admitted=False,
        pairs={p: {k: v[k] for k in ('rows', 'missing_expected_open_hours')}
               for p, v in result['pairs'].items()})))


if __name__ == '__main__':
    main()
