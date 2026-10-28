"""Prepare a scoped, admitted-price candidate population for the existing selector."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd


RAW = ['OPEN', 'HIGH', 'LOW', 'CLOSE', 'RAW_BAR_LOG_RETURN', 'RAW_LOG_RANGE',
       'RAW_CLOSE_LOG_RETURN', 'RAW_ELAPSED_HOURS']
TARGETS = [('RETURN_4H', 4), ('RETURN_12H', 12), ('ABS_RETURN_12H', 12)]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def save(path, value):
    data = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n'
    path = Path(path)
    if path.exists():
        if path.read_text() != data:
            raise ValueError('OUTPUT_IDENTITY_CHANGED: ' + path.name)
        return
    temp = path.with_suffix(path.suffix + '.partial')
    with temp.open('w') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def candidate_frame(bars, generator, technical_columns):
    x = generator(bars.copy())
    if not x.DATE_TIME.equals(bars.DATE_TIME):
        raise ValueError('GENERATOR_CHANGED_KEYS')
    x['RAW_BAR_LOG_RETURN'] = np.log(x.CLOSE / x.OPEN)
    x['RAW_LOG_RANGE'] = np.log(x.HIGH / x.LOW)
    x['RAW_CLOSE_LOG_RETURN'] = np.log(x.CLOSE / x.CLOSE.shift(1))
    x['RAW_ELAPSED_HOURS'] = x.DATE_TIME.diff().dt.total_seconds() / 3600
    return x[['DATE_TIME'] + RAW + list(technical_columns)]


def trim_warmup(frame):
    finite = np.isfinite(frame.drop(columns='DATE_TIME').to_numpy(dtype=float)).all(axis=1)
    positions = np.flatnonzero(finite)
    if not len(positions):
        raise ValueError('NO_FINITE_CANDIDATE_ROWS')
    first = int(positions[0])
    if not finite[first:].all():
        raise ValueError('INTERIOR_NONFINITE_CANDIDATE')
    return frame.iloc[first:].reset_index(drop=True), first


def business_targets(frame, closures, *, end, cutoffs):
    times = pd.DatetimeIndex(frame.DATE_TIME)
    close = pd.Series(frame.CLOSE.to_numpy(), index=times)
    result = pd.DataFrame({'DATE_TIME': frame.DATE_TIME})
    for name, hours in TARGETS:
        endpoint = times + pd.Timedelta(hours=hours)
        labels = np.log(close.reindex(endpoint).to_numpy() / close.to_numpy())
        eligible = (times < pd.Timestamp(end)) & (endpoint < pd.Timestamp(end))
        for start, stop in closures:
            forced = pd.Timestamp(start) - pd.Timedelta(hours=12)
            resumed = pd.Timestamp(stop) + pd.Timedelta(hours=12)
            eligible &= ~((times < resumed) & (endpoint >= forced))
        for cutoff in cutoffs:
            eligible &= ~((times < cutoff) & (endpoint >= cutoff))
        labels[~eligible] = np.nan
        result[name] = np.abs(labels) if name.startswith('ABS_') else labels
    return result


def build(admission_root, generator_root, output):
    admission_root, generator_root, output = map(Path, (admission_root, generator_root, output))
    receipt_path = admission_root / 'ADMISSION.json'
    receipt = json.loads(receipt_path.read_text())
    if not (receipt.get('schema') == 'financial_data.core_price_inventory.v1'
            and receipt.get('admitted') is True and receipt.get('status') == 'ADMITTED'):
        raise ValueError('CORE_ADMISSION_REQUIRED')
    entry = receipt['pairs']['eurusd']
    source = admission_root / entry['file']
    closures_path = admission_root / receipt['closure_intervals_file']
    if (source.parent.resolve() != admission_root.resolve()
            or digest(source) != entry['sha256']
            or digest(closures_path) != receipt['closure_intervals_sha256']):
        raise ValueError('CORE_ADMISSION_HASH_MISMATCH')
    if entry['availability_semantics'] != 'UTC_NATIVE_BAR_START_PLUS_ONE_HOUR':
        raise ValueError('UNSUPPORTED_SOURCE_CLOCK')
    module_path = generator_root / 'normalize_phase1b.py'
    head = subprocess.check_output(['git', '-C', str(generator_root), 'rev-parse', 'HEAD'], text=True).strip()
    expected = subprocess.check_output(['git', '-C', str(generator_root), 'show', 'HEAD:normalize_phase1b.py'])
    if module_path.read_bytes() != expected:
        raise ValueError('GENERATOR_DIFFERS_FROM_COMMIT')
    binding = {'schema': 'financial_data.core_selection_binding.v1',
               'admission_sha256': digest(receipt_path), 'source_sha256': digest(source),
               'closures_sha256': digest(closures_path), 'generator_commit': head,
               'generator_sha256': digest(module_path), 'preparer_sha256': digest(__file__),
               'scope': 'ADMITTED_EURUSD_CORE_DERIVED_CANDIDATES',
               'full_inventory_complete': False, 'selection_policy': 'MRMR_K12_UNION_THREE_TARGETS_TRAIN_ONLY'}
    output.mkdir(parents=True, exist_ok=True)
    save(output / 'BINDING.json', binding)
    # Arrow predicate excludes TEST values; hashing source bytes above is not evaluation.
    frame = pd.read_parquet(source, filters=[('available_at', '<', pd.Timestamp('2025-01-01', tz='UTC'))])
    if not (frame.available_at == frame.timestamp + pd.Timedelta(hours=1)).all():
        raise ValueError('SOURCE_AVAILABILITY_MISMATCH')
    bars = frame.rename(columns={'available_at': 'DATE_TIME', 'BidOpen': 'OPEN',
                                 'BidHigh': 'HIGH', 'BidLow': 'LOW', 'BidClose': 'CLOSE'})
    bars = bars[['DATE_TIME', 'OPEN', 'HIGH', 'LOW', 'CLOSE']]
    if not bars.DATE_TIME.is_unique or not bars.DATE_TIME.is_monotonic_increasing:
        raise ValueError('SOURCE_KEYS_INVALID')
    spec = importlib.util.spec_from_file_location('core_selection_technical_generator', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    generated = candidate_frame(bars, module.add_derived_features, module.FEATURE_COLS)
    for stop in (512, 4096):
        prefix = candidate_frame(bars.iloc[:stop], module.add_derived_features, module.FEATURE_COLS)
        pd.testing.assert_frame_equal(generated.iloc[:stop], prefix, check_exact=True)
    generated, removed = trim_warmup(generated)
    ids = [c for c in generated if c != 'DATE_TIME']
    train = generated.loc[generated.DATE_TIME < pd.Timestamp('2024-01-01', tz='UTC')].reset_index(drop=True)
    if train.DATE_TIME.dt.strftime('%Y-%m').nunique() != 48:
        raise ValueError('TRAIN_MONTHS_INCOMPLETE')
    folds = []
    cutoffs = []
    for year in (2022, 2023):
        stop = int(train.DATE_TIME.searchsorted(pd.Timestamp(f'{year}-01-01', tz='UTC')))
        folds.append({'fold_id': f'prefix_before_{year}', 'train_rows': [0, stop]})
        cutoffs.append(train.DATE_TIME.iloc[stop])
    closures = json.loads(closures_path.read_text())
    y = business_targets(train, closures, end='2024-01-01T00:00:00Z', cutoffs=cutoffs)
    keys = pd.DataFrame({'row_id': np.arange(len(train)), 'timestamp': train.DATE_TIME})
    x = pd.concat([keys, train[ids]], axis=1)
    labels = pd.concat([keys, y.drop(columns='DATE_TIME')], axis=1)
    available = keys.copy()
    for fid in ids:
        available[fid] = keys.timestamp
    for name, data in [('features_train.parquet', x), ('targets_train.parquet', labels),
                       ('availability_train.parquet', available)]:
        path = output / name
        if path.exists():
            pd.testing.assert_frame_equal(pd.read_parquet(path), data, check_exact=True)
        else:
            data.to_parquet(path, index=False)
    for name in ('ADMISSION.json', 'CLOSURE_INTERVALS.json'):
        dst = output / ('SOURCE_' + name)
        src = admission_root / name
        if dst.exists() and digest(dst) != digest(src):
            raise ValueError('RETAINED_SOURCE_PROOF_CHANGED')
        if not dst.exists():
            shutil.copyfile(src, dst)
    derived = {**binding, 'schema': 'financial_data.derived_candidate_admission.v1',
               'admitted': True, 'variable_ids': ids, 'leading_warmup_rows_removed': removed,
               'train_rows': len(train), 'prefix_checks_exact': [512, 4096],
               'selection_complete': False, 'causal_effects_identified': False,
               'input_closed_hours_fabricated': 0, 'interpolation': False}
    save(output / 'DERIVED_ADMISSION.json', derived)
    features = [dict(feature_id=fid, availability_time=fid, family='price' if fid in RAW else 'technical_seasonal',
                     source='admitted_eurusd_core', transform='identity' if fid in RAW[:4] else 'causal_recipe',
                     unit='price' if fid in RAW[:4] else 'recipe_native_units', clock='OBSERVED',
                     support_h=None, train_coverage=1.0, source_bytes=source.stat().st_size) for fid in ids]
    handoff = {'schema': 'feature_selector.rebuild_input.v1', 'scope': 'ADMITTED_TRAIN',
               'created_at': '2026-10-19T00:00:00Z', 'target_clock': 'HOURLY_ELAPSED',
               'train_period': ['2020-01-01T00:00:00Z', '2024-01-01T00:00:00Z'],
               'expected_monthly_rows': {str(k): int(v) for k, v in train.DATE_TIME.dt.strftime('%Y-%m').value_counts().items()},
               'admission': {'authority': 'financial-data', 'disposition': 'ADMITTED', 'variable_ids': ids,
                             'evidence': [{'file': n, 'sha256': digest(output/n)} for n in
                                          ('SOURCE_ADMISSION.json', 'SOURCE_CLOSURE_INTERVALS.json', 'DERIVED_ADMISSION.json')]},
               'availability': {'file': 'availability_train.parquet', 'sha256': digest(output/'availability_train.parquet')},
               'population': {'population_id': 'EURUSD_CORE_DERIVED_20261019', 'contract_source': 'core_selection_comparison_design.v1',
                              'features': features, 'targets': [dict(target_id=n, column=n, horizon_hours=h,
                                                                  family='risk' if n.startswith('ABS_') else 'return', head='regression') for n,h in TARGETS],
                              'folds': folds, 'data': {'features_file': 'features_train.parquet',
                              'features_sha256': digest(output/'features_train.parquet'), 'targets_file': 'targets_train.parquet',
                              'targets_sha256': digest(output/'targets_train.parquet'), 'row_id_column': 'row_id',
                              'timestamp_column': 'timestamp', 'train_rows': len(train), 'bar_hours': 1}}}
    save(output/'REBUILD_INPUT.json', handoff)
    cfg = dict(schema='feature_selector.rebuild_config.v1', phase1_mode='PROFILE_ONLY', target_pack_id='EURUSD',
               calendar='observed_only', max_file_bytes=67108864, max_rows=100000, max_features=512,
               max_attempts=2, worker_timeout_seconds=600, n_shards=4, pairwise_params={'dcor_max_rows': 512})
    save(output/'REBUILD_CONFIG.json', cfg)
    # This artifact contains candidate inputs, not selected inputs or a final admission claim.
    full_path = output/'candidates_train_validation.parquet'
    if full_path.exists():
        pd.testing.assert_frame_equal(pd.read_parquet(full_path), generated, check_exact=True)
    else:
        generated.to_parquet(full_path, index=False)
    save(output/'STATUS.json', {'state': 'CANDIDATE_BUNDLE_READY_NOT_SELECTED', 'candidates': len(ids),
                              'train_rows': len(train), 'validation_rows': int((generated.DATE_TIME >= pd.Timestamp('2024-01-01', tz='UTC')).sum()),
                              'warmup_rows_removed': removed, 'full_inventory_complete': False,
                              'train_bundle_sha256': digest(output/'REBUILD_INPUT.json')})
    return json.loads((output/'STATUS.json').read_text())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--admission-root', type=Path, required=True)
    parser.add_argument('--generator-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.admission_root, args.generator_root, args.output), indent=2))
