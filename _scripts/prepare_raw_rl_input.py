"""Render owner-admitted EURUSD prices as a causal, non-selected raw RL control.

No fitting, filling, interpolation, network, training, or 2025 sample export.
The first source bar is an explicit one-row warm-up, never a fabricated return.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

BID = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']
PRICES = ['OPEN', 'HIGH', 'LOW', 'CLOSE']
FEATURES = PRICES + ['RAW_BAR_LOG_RETURN', 'RAW_LOG_RANGE', 'RAW_CLOSE_LOG_RETURN', 'RAW_ELAPSED_HOURS']
ASSUMED_SPREAD = 0.00010
SPREAD_POLICY = dict(column='ASSUMED_SPREAD', constant=ASSUMED_SPREAD, units='USD_PER_EUR',
    provenance='ASSUMED_FIXED_SPREAD_1_PIP_NOT_BROKER_VERIFIED', observed=False,
    usage='SESSION_STABILITY_COST_MODEL_ONLY', feature=False, validation_tuned=False,
    ask_ohlc_fabricated=False, transaction_cost_authority='existing guarded cost profile, not this column')
PERIODS = dict(train=('2020-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00'),
               validation=('2024-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00'))
POLICY = dict(schema='financial_data.raw_baseline_input_policy.v1', scope='RAW_BASELINE',
    pair='EURUSD', timeframe='H1', timestamp_semantics='completed_bar_available_at',
    feature_columns=FEATURES, feature_selection_complete=False, price_fill=False, interpolation=False,
    formulas=dict(RAW_BAR_LOG_RETURN='log(CLOSE / OPEN)', RAW_LOG_RANGE='log(HIGH / LOW)',
                  RAW_CLOSE_LOG_RETURN='log(CLOSE / previous observed CLOSE)',
                  RAW_ELAPSED_HOURS='(available_at - previous observed available_at).total_seconds / 3600'),
    close_return_semantics='actual elapsed observation interval, not assumed one-hour or normalized',
    previous_context='strictly earlier source bar; allowed across train/validation boundary',
    warmup='exclude exactly first source bar because previous close and elapsed time are undefined',
    eligibility='every declared operating-hour source row except explicit initial warm-up, split by availability',
    periods=PERIODS, fitting='NONE', final_selection_claim=False,
    calendar_semantics='declared business policy, not universal venue certification',
    nonfeature_columns=dict(ASSUMED_SPREAD=SPREAD_POLICY))


def digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def write_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def utc_index(values):
    index = pd.DatetimeIndex(values)
    if str(index.tz) != 'UTC' or index.isna().any():
        raise ValueError('EXPLICIT_UTC_TIMESTAMPS_REQUIRED')
    return index


def calendar_hours(calendar):
    grid = pd.date_range(calendar['coverage_start'], calendar['coverage_end_exclusive'], freq='h', inclusive='left')
    utc_index(grid)
    local = grid.tz_convert(calendar['timezone'])
    position = local.dayofweek * 24 + local.hour
    opened = calendar['weekly_open_day'] * 24 + calendar['weekly_open_hour']
    closed = calendar['weekly_close_day'] * 24 + calendar['weekly_close_hour']
    good = ((position >= opened) & (position < closed)) if opened < closed else ((position >= opened) | (position < closed))
    for item in calendar['closed_intervals']:
        start, end = pd.Timestamp(item['start']), pd.Timestamp(item['end'])
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            raise ValueError('INVALID_CALENDAR_EXCLUSION')
        good &= ~((grid >= start) & (grid < end))
    return grid[good]


def derive(raw):
    times, available = utc_index(raw.timestamp), utc_index(raw.available_at)
    values = raw[BID].to_numpy(float)
    if (len(raw) < 2 or times.has_duplicates or not times.is_monotonic_increasing
            or not times.equals(times.floor('h')) or not available.equals(times + pd.Timedelta(hours=1))
            or not np.isfinite(values).all() or (values <= 0).any()
            or (raw.BidHigh < raw[BID].max(axis=1)).any() or (raw.BidLow > raw[BID].min(axis=1)).any()):
        raise ValueError('INVALID_CAUSAL_SOURCE_ROWS')
    frame = raw[BID].rename(columns=dict(zip(BID, PRICES))).reset_index(drop=True)
    frame.insert(0, 'DATE_TIME', available)
    frame['RAW_BAR_LOG_RETURN'] = np.log(frame.CLOSE / frame.OPEN)
    frame['RAW_LOG_RANGE'] = np.log(frame.HIGH / frame.LOW)
    frame['RAW_CLOSE_LOG_RETURN'] = np.log(frame.CLOSE / frame.CLOSE.shift(1))
    frame['RAW_ELAPSED_HOURS'] = frame.DATE_TIME.diff().dt.total_seconds() / 3600
    frame['ASSUMED_SPREAD'] = ASSUMED_SPREAD
    frame = frame.iloc[1:].reset_index(drop=True)
    if not np.isfinite(frame[FEATURES].to_numpy()).all() or not frame.RAW_ELAPSED_HOURS.gt(0).all():
        raise ValueError('INVALID_RAW_FEATURES')
    return frame


def split_frames(frame):
    return {split: frame.loc[frame.DATE_TIME.ge(pd.Timestamp(start)) & frame.DATE_TIME.lt(pd.Timestamp(end))].reset_index(drop=True)
            for split, (start, end) in PERIODS.items()}


def timestamp_sha(timestamps):
    value = hashlib.sha256()
    for stamp in timestamps:
        value.update((stamp.to_pydatetime().isoformat() + '\n').encode())
    return value.hexdigest()


def load_validator(path):
    spec = importlib.util.spec_from_file_location('raw_rl_external_validator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_split(output, split, frame, pins, lineage):
    if frame.empty:
        raise ValueError('EMPTY_SPLIT')
    if not frame.ASSUMED_SPREAD.eq(ASSUMED_SPREAD).all():
        raise ValueError('FIXED_NONFEATURE_COST_ASSUMPTION_REQUIRED')
    start, end = PERIODS[split]
    path = output / f'{split}.csv'
    exported = frame.copy()
    exported['DATE_TIME'] = exported.DATE_TIME.map(lambda t: t.to_pydatetime().isoformat())
    exported.to_csv(path, index=False, float_format='%.17g', lineterminator='\n')
    # Python float is also the consumer's parser; verify price-bit round trips.
    with path.open(newline='') as handle:
        for position, row in enumerate(csv.DictReader(handle)):
            if any(float(row[c]) != frame.iloc[position][c] for c in PRICES):
                raise ValueError('PRICE_ROUNDTRIP_MISMATCH')
    manifest = dict(schema='curated_rl_input.v1', status='ADMITTED', split=split,
        availability_verified=True, open_session_coverage_verified=True,
        timestamp_semantics='completed_bar_available_at', period_start=start, period_end=end,
        period_end_semantics='EXCLUSIVE_COMPLETED_AVAILABILITY', row_count=len(frame),
        input_sha256=digest(path), feature_columns=FEATURES, expected_timestamps_sha256=timestamp_sha(frame.DATE_TIME),
        first_timestamp=exported.DATE_TIME.iloc[0], last_timestamp=exported.DATE_TIME.iloc[-1],
        monthly_rows={str(k): int(v) for k, v in frame.groupby(frame.DATE_TIME.dt.strftime('%Y-%m')).size().items()},
        scope='RAW_BASELINE', admission_basis='OWNER_ISSUED_CORE_PRICES_ONLY_ADMISSION',
        selection_semantics='RAW_BASELINE_INPUT_POLICY_NOT_FINAL_SELECTION', feature_selection_complete=False,
        price_fill=False, interpolation=False, lineage=lineage,
        nonfeature_columns=['ASSUMED_SPREAD'], assumed_spread_policy=SPREAD_POLICY,
        observed_spread_available=False, ask_ohlc_fabricated=False, **pins)
    manifest_path = output / f'{split}.manifest.json'
    write_json(manifest_path, manifest)
    config = dict(require_curated_rl_input=True, curated_input_manifest=str(manifest_path.resolve()),
        curated_input_manifest_sha256=digest(manifest_path), curated_input_split=split,
        input_data_file=str(path.resolve()), feature_columns=FEATURES, date_column='DATE_TIME', headers=True, max_rows=None,
        session_spread_column='ASSUMED_SPREAD')
    write_json(output / f'{split}.validator_config.json', config)
    return manifest, config


def safe_member(root, name):
    path = root / name
    if path.resolve().parent != root.resolve():
        raise ValueError('SOURCE_MEMBER_OUTSIDE_ADMISSION')
    return path


def prepare(admission_root, output, validator_path, data_commit='HEAD'):
    repo = Path(__file__).resolve().parents[1]
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', '--verify', data_commit + '^{commit}'], text=True).strip()
    source_paths = [admission_root / name for name in ['ADMISSION.json', 'STATUS.json', 'BINDING.json', 'CALENDAR.json']]
    receipt = json.loads(source_paths[0].read_text())
    if (receipt.get('schema') != 'financial_data.core_price_inventory.v1'
            or receipt.get('status') != 'ADMITTED' or receipt.get('admitted') is not True
            or receipt.get('scope') != 'CORE_PRICES_ONLY'
            or receipt.get('coverage_scope') != 'DECLARED_CONSERVATIVE_BUSINESS_OPERATING_CALENDAR'
            or json.loads(source_paths[1].read_text()) != receipt
            or json.loads(source_paths[2].read_text()) != receipt['binding']):
        raise ValueError('OWNER_CORE_PRICE_ADMISSION_REQUIRED')
    item = receipt['pairs']['eurusd']
    price_path, quality_path = (safe_member(admission_root, item[k]) for k in ('file', 'quality_file'))
    if (digest(price_path) != item['sha256'] or digest(quality_path) != item['quality_sha256']
            or digest(source_paths[3]) != receipt['binding']['calendar_sha256']
            or item['availability_semantics'] != 'UTC_NATIVE_BAR_START_PLUS_ONE_HOUR'
            or item['missing_required_operating_hours'] != 0):
        raise ValueError('ADMISSION_SOURCE_DIGEST_OR_SEMANTICS_MISMATCH')
    source_paths.extend([price_path, quality_path])
    source_admit_code = subprocess.check_output(['git', '-C', str(repo), 'show', commit + ':_scripts/admit_core_fx.py'])
    if hashlib.sha256(source_admit_code).hexdigest() != receipt['binding']['code_sha256']:
        raise ValueError('DATA_COMMIT_ADMISSION_CODE_MISMATCH')
    calendar = json.loads(source_paths[3].read_text())
    expected = calendar_hours(calendar)
    times = pd.read_parquet(price_path, columns=['timestamp', 'available_at'])
    if (not utc_index(times.timestamp).equals(expected)
            or not utc_index(times.available_at).equals(expected + pd.Timedelta(hours=1))
            or len(times) != item['rows'] or len(times) != receipt['expected_operating_hours']
            or item['monthly_rows'] != {str(k): int(v) for k, v in times.groupby(times.timestamp.dt.strftime('%Y-%m')).size().items()}):
        raise ValueError('ADMITTED_SOURCE_POPULATION_MISMATCH')
    interval_refs = {}
    for field, default in [('open_session_intervals_file', 'OPEN_SESSION_INTERVALS.json'),
                           ('closure_intervals_file', 'CLOSURE_INTERVALS.json')]:
        path = safe_member(admission_root, receipt.get(field, default))
        if path.exists():
            key = field.replace('_file', '_sha256')
            if key in receipt and digest(path) != receipt[key]:
                raise ValueError('ADMISSION_INTERVAL_DIGEST_MISMATCH')
            interval_refs[field] = dict(path=str(path.resolve()), sha256=digest(path),
                                       timestamp_basis='original bar-time business policy; not shifted to availability')
            source_paths.append(path)
    tracked = {path: digest(path) for path in source_paths + [Path(__file__), validator_path]}
    cutoff = pd.Timestamp(PERIODS['validation'][1])
    # Filter prices at the parquet reader: no 2025 prices enter feature derivation.
    raw = pd.read_parquet(price_path, columns=['timestamp', 'available_at'] + BID,
                          filters=[('available_at', '<', cutoff)])
    if raw.empty or pd.Timestamp(calendar['coverage_start']) > pd.Timestamp(PERIODS['train'][0]) or pd.Timestamp(calendar['coverage_end_exclusive']) < cutoff:
        raise ValueError('REQUESTED_SPLIT_OUTSIDE_ADMITTED_COVERAGE')
    frame = derive(raw)
    splits = split_frames(frame)
    expected_available = pd.DatetimeIndex(times.available_at).drop(pd.Timestamp(raw.available_at.iloc[0]))
    for split, subset in splits.items():
        start, end = map(pd.Timestamp, PERIODS[split])
        support = expected_available[(expected_available >= start) & (expected_available < end)]
        if not pd.DatetimeIndex(subset.DATE_TIME).equals(support):
            raise ValueError('SPLIT_ELIGIBILITY_SUPPORT_MISMATCH')
        months = set(pd.period_range(start.tz_localize(None), (end - pd.Timedelta(seconds=1)).tz_localize(None), freq='M').astype(str))
        if set(subset.DATE_TIME.dt.strftime('%Y-%m')) != months:
            raise ValueError('SILENT_MONTH_LOSS')
    if output.resolve().is_relative_to(admission_root.resolve()):
        raise ValueError('OUTPUT_OVERLAPS_ADMISSION')
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('OUTPUT_MUST_BE_EMPTY_NO_OVERWRITE')
    write_json(output / 'RAW_BASELINE.policy.json', POLICY)
    pins = dict(selection_sha256=digest(output / 'RAW_BASELINE.policy.json'),
                inventory_sha256=tracked[source_paths[0]], calendar_sha256=receipt['binding']['calendar_sha256'])
    lineage = dict(owner_admission_file=str(source_paths[0].resolve()), owner_admission_scope='CORE_PRICES_ONLY',
        source_price_sha256=item['sha256'], source_quality_sha256=item['quality_sha256'],
        data_git_commit=commit, renderer_sha256=tracked[Path(__file__)], validator_sha256=tracked[validator_path],
        source_pins={p.name: h for p, h in tracked.items()}, admission_binding=receipt['binding'],
        calendar_scope=receipt['coverage_scope'], global_venue_calendar_certified=False,
        interval_references=interval_refs, warmup_excluded_source_bar_start=raw.timestamp.iloc[0].isoformat(),
        warmup_excluded_available_at=raw.available_at.iloc[0].isoformat(), warmup_rows_excluded=1,
        derivation='deterministic causal raw transforms only; no fit or feature selection')
    validator = load_validator(validator_path)
    summary = dict(schema='financial_data.raw_rl_preparation_receipt.v1', status='PREPARED_AND_VALIDATED',
                   scope='RAW_BASELINE', feature_selection_complete=False, owner_admission_sha256=pins['inventory_sha256'],
                   source_lineage=lineage, policy_sha256=pins['selection_sha256'], splits={},
                   no_2025_sample_output=True, price_fill=False, interpolation=False,
                   method=dict(stage='ALPHA_VALIDATED', next_action='owner-run independent EURUSD raw control; no final-selection claim'))
    for split, subset in splits.items():
        manifest, config = write_split(output, split, subset, pins, lineage)
        checked = validator.validate_curated_rl_input(config)
        summary['splits'][split] = dict(validator_result=checked,
            expected_timestamps_sha256=manifest['expected_timestamps_sha256'],
            first_timestamp=manifest['first_timestamp'], last_timestamp=manifest['last_timestamp'],
            monthly_rows=manifest['monthly_rows'], manifest_file=f'{split}.manifest.json', csv_file=f'{split}.csv')
    if any(digest(path) != before for path, before in tracked.items()):
        raise ValueError('SOURCE_OR_CODE_CHANGED_DURING_RENDER')
    write_json(output / 'RECEIPT.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--admission-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--validator', type=Path, required=True)
    parser.add_argument('--data-commit', default='HEAD')
    args = parser.parse_args()
    result = prepare(args.admission_root.resolve(), args.output_root.resolve(), args.validator.resolve(), args.data_commit)
    print(json.dumps(dict(status=result['status'], policy_sha256=result['policy_sha256'],
        splits={k: v['validator_result']['row_count'] for k, v in result['splits'].items()})))


if __name__ == '__main__':
    main()
