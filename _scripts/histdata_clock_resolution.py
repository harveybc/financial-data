"""Compare raw HistData clocks on common support; never silently shift or admit."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from publish_native_fx_quality import file_sha, write_json

CLOCKS = ('DECLARED_FIXED_EST', 'US_EASTERN_CONTROL', 'EUROPEAN_DST_COHORT_HYPOTHESIS')


def clock(native, hypothesis):
    native = pd.DatetimeIndex(native)
    if native.tz is not None or native.isna().any():
        raise ValueError('NAIVE_VALID_NATIVE_TIME_REQUIRED')
    if hypothesis == 'DECLARED_FIXED_EST':
        return (native + pd.Timedelta(hours=5)).tz_localize('UTC')
    if hypothesis == 'US_EASTERN_CONTROL':
        return native.tz_localize('America/New_York', ambiguous='raise', nonexistent='raise').tz_convert('UTC')
    if hypothesis == 'EUROPEAN_DST_COHORT_HYPOTHESIS':
        return (native + pd.Timedelta(hours=5)).tz_localize(
            'Europe/London', ambiguous='raise', nonexistent='raise').tz_convert('UTC')
    raise ValueError('UNKNOWN_CLOCK')


def raw_minutes(path, pair, year):
    with zipfile.ZipFile(path) as archive:
        names = [n for n in archive.namelist() if n.upper() == f'DAT_ASCII_{pair.upper()}_M1_{year}.CSV']
        if len(names) != 1 or sum(i.file_size for i in archive.infolist()) > 160 * 1024**2:
            raise ValueError('RAW_ARCHIVE_CONTRACT')
        with archive.open(names[0]) as stream:
            frame = pd.read_csv(stream, sep=';', header=None,
                                names=['native', 'open', 'high', 'low', 'close', 'volume'])
    frame.native = pd.to_datetime(frame.native, format='%Y%m%d %H%M%S', errors='raise')
    if frame.empty or not frame.native.dt.year.eq(year).all():
        raise ValueError('RAW_PERIOD_CONTRACT')
    values = frame[['open', 'high', 'low', 'close']]
    if (not np.isfinite(values.to_numpy(float)).all() or (values <= 0).any().any()
            or (frame.high < values.max(axis=1)).any() or (frame.low > values.min(axis=1)).any()):
        raise ValueError('INVALID_RAW_OHLC')
    duplicates = int(frame.duplicated().sum())
    frame = frame.drop_duplicates()
    if frame.native.duplicated().any():
        raise ValueError('CONFLICTING_NATIVE_MINUTES')
    return frame.sort_values('native'), duplicates


def complete_closes(frame, hypothesis):
    native = pd.DatetimeIndex(pd.to_datetime(frame.native))
    values = frame.close.to_numpy(float)
    if (native.has_duplicates or native.isna().any() or (native != native.floor('min')).any()
            or not np.isfinite(values).all() or (values <= 0).any()):
        raise ValueError('INVALID_MINUTE')
    ts = clock(native, hypothesis)
    result = pd.DataFrame({'available_at': ts.floor('h') + pd.Timedelta(hours=1),
                           'minute': ts, 'close': values}).sort_values('minute')
    counts = result.groupby('available_at').size()
    return result[result.available_at.isin(counts[counts.eq(60)].index)].groupby(
        'available_at', as_index=False).tail(1)[['available_at', 'close']].reset_index(drop=True)


def compare_common(primary, candidates):
    if primary.available_at.duplicated().any():
        raise ValueError('PRIMARY_DUPLICATES')
    joined = primary[['available_at', 'BidClose']].copy()
    for name, candidate in candidates.items():
        joined = joined.merge(candidate.rename(columns={'close': name}),
                              on='available_at', validate='one_to_one')
    if not candidates or joined.empty:
        raise ValueError('NO_COMMON_SUPPORT')
    if not np.isfinite(joined.drop(columns='available_at').to_numpy(float)).all():
        raise ValueError('INVALID_COMPARISON_PRICE')
    rows = []
    for day, group in joined.groupby(joined.available_at.dt.strftime('%Y-%m-%d')):
        support = '\n'.join(group.available_at.sort_values().astype(str))
        digest = hashlib.sha256(support.encode()).hexdigest()
        for name in candidates:
            delta = group[name] - group.BidClose
            rows.append(dict(date=day, hypothesis=name, n=len(group), support_sha256=digest,
                             median_abs=float(delta.abs().median()), p95_abs=float(delta.abs().quantile(.95)),
                             max_abs=float(delta.abs().max()), median_signed=float(delta.median())))
    return rows


def run(primary_root, histdata_root, year):
    report = dict(schema='financial_data.histdata_clock_resolution.v1',
                  state='DIAGNOSTIC_COMPLETE_NOT_ADMITTED', admitted=False,
                  automatic_clock_selection=False, year=year, code_sha256=file_sha(__file__),
                  files=[], pairs={})
    for pair in ('eurusd', 'gbpusd'):
        raw = histdata_root / f'{pair}-{year}' / 'source.zip'
        primary_path = primary_root / str(year) / pair / f'{year}-1h.parquet'
        records = [(raw, 'histdata_raw/' + raw.parent.name + '/' + raw.name),
                   (primary_path, 'fxcm/' + str(primary_path.relative_to(primary_root)))]
        before = {p: file_sha(p) for p, _ in records}
        minutes, duplicates = raw_minutes(raw, pair, year)
        primary = pd.read_parquet(primary_path, columns=['available_at', 'BidClose'])
        candidates = {hyp: complete_closes(minutes, hyp) for hyp in CLOCKS}
        comparisons = compare_common(primary, candidates)
        report['pairs'][pair] = dict(raw_minutes=len(minutes), identical_duplicates_removed=duplicates,
                                    complete_hours={h: len(f) for h, f in candidates.items()}, comparisons=comparisons)
        for p, name in records:
            if file_sha(p) != before[p]:
                raise ValueError('SOURCE_CHANGED_DURING_READ')
            report['files'].append(dict(name=name, sha256=before[p]))
    return report


def build_verified_reports(path, primary_root, histdata_root, code_commit):
    retained = json.loads(Path(path).read_text())
    replay = run(Path(primary_root), Path(histdata_root), retained['year'])
    if retained != replay:
        raise ValueError('HISTDATA_DIAGNOSTIC_REPLAY_MISMATCH')
    identity = file_sha(path)
    reports = []
    for pair, data in retained['pairs'].items():
        metrics = []
        for row in data['comparisons']:
            for field in ('n', 'median_abs', 'p95_abs', 'max_abs', 'median_signed'):
                metrics.append(dict(metric=f"{row['hypothesis']}.{row['date']}.{field}",
                    value=row[field], split='quality', horizon=None,
                    unit='count' if field == 'n' else 'quote_difference'))
        reports.append(dict(experiment_key=f'histdata-clock:{pair}:{identity}',
            experiment_set_key='canonical-native-fx-recovery', actor='canonical-data-curation',
            lake='acquisition-not-admitted', lineage='UNVERIFIED', project='financial-data',
            phase='HISTDATA_RAW_CLOCK_DIAGNOSTIC', config_sha256=identity, code_commit=code_commit,
            tags=dict(pair=pair, admission='NOT_ADMITTED', clock_selection='NONE',
                      model_training='false', receipt_sha256=identity),
            datasets=[dict(lake='acquisition-not-admitted', resource=f['name'], sha256=f['sha256'],
                           role='clock_diagnostic_source', lineage='UNVERIFIED',
                           reason='Raw source comparison; not admitted') for f in retained['files']],
            metrics=metrics))
    return reports


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--primary-root', type=Path, required=True)
    parser.add_argument('--histdata-root', type=Path, required=True)
    parser.add_argument('--year', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run(args.primary_root, args.histdata_root, args.year)
    if args.output.exists() and json.loads(args.output.read_text()) != report:
        raise ValueError('OUTPUT_CONFLICT')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(json.dumps(dict(state=report['state'], comparisons=sum(
        len(p['comparisons']) for p in report['pairs'].values()), sha256=file_sha(args.output))))


if __name__ == '__main__':
    main()
