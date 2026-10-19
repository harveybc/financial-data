"""Four governed FX quality reports, never admission or per-row price publication.

Main must commit the actual producer/publisher files before running this CLI.
Inputs must remain immutable during verification and publication. Queue/locks
live on ext4; closed physical evidence copies use the existing publisher path.
"""
import argparse
import fcntl
import hashlib
import inspect
import json
import math
from pathlib import Path
import re
import subprocess
import sys

import pandas as pd

import consolidate_fx_observations as consolidator
import normalize_histdata_observed_clock as normalized_helper
import publish_native_fx_quality as native
from publish_native_fx_quality import copy_closed, file_sha, mirror_closed, snapshot, write_json

PAIRS = ('eurusd', 'gbpusd')
CODE_FILES = tuple('_scripts/' + name for name in (
    'publish_consolidated_fx.py', 'publish_native_fx_quality.py',
    'normalize_histdata_observed_clock.py', 'consolidate_fx_observations.py',
    'histdata_clock_resolution.py', 'recover_forexite_observations.py',
    'native_fx_recovery.py', 'recover_fxcm_boundary.py'))


def verify_pinned(repo, commit, names):
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
        raise ValueError('FULL_CODE_COMMIT_REQUIRED')
    for name in names:
        path = (Path(repo) / name).resolve()
        if not path.is_relative_to(Path(repo).resolve()):
            raise ValueError('CODE_PATH_ESCAPE')
        blob = subprocess.run(['git', '-C', str(repo), 'show', commit + ':' + name],
                              capture_output=True, check=True).stdout
        if hashlib.sha256(blob).hexdigest() != file_sha(path):
            raise ValueError('PUBLICATION_CODE_NOT_PINNED')


def _digest(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('EVIDENCE_DIGEST_REQUIRED')
    return value


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError('NONNEGATIVE_INTEGER_COUNT_REQUIRED')
    return value


def _number(value, correlation=False):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or (not -1 <= value <= 1 if correlation else value < 0)):
        raise ValueError('INVALID_COMPARISON_STATISTIC')
    return value


def _dataset(name, digest, role):
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError('EVIDENCE_RESOURCE_PATH_ESCAPE')
    return dict(lake='acquisition-not-admitted', resource=name, sha256=_sha(digest), role=role,
                lineage='UNVERIFIED', reason='Quality evidence only; no data admission')


def _metric(name, value, unit):
    return dict(metric=name, value=value, unit=unit, split='quality', horizon=None)


def _cohort_report(pair, receipt, receipt_sha, contract, code_commit):
    files = sorted((f for f in receipt['files'] if f['pair'] == pair), key=lambda f: f['year'])
    metrics, datasets = [], []
    quote_unit = 'USD_per_EUR' if pair == 'eurusd' else 'USD_per_GBP'
    for item in files:
        year = item['year']
        raw, complete, incomplete = (_count(item[k]) for k in ('raw_minutes', 'rows', 'incomplete_hours'))
        if not complete * 60 + incomplete <= raw <= complete * 60 + incomplete * 59:
            raise ValueError('RAW_MINUTE_COMPLETE_INCOMPLETE_COUNTS_MISMATCH')
        for name, value, unit in (('raw_minutes', raw, 'minute_bar_count'),
                                  ('complete_hours', complete, 'hour_bar_count'),
                                  ('incomplete_hours', incomplete, 'incomplete_hour_bin_count'),
                                  ('identical_duplicates_removed', _count(item['identical_duplicates_removed']),
                                   'minute_row_count')):
            metrics.append(_metric(f'cohort.{year}.{name}', value, unit))
        check = item['primary_check']
        paired = _count(check['paired_hours'])
        if not 0 < paired <= complete:
            raise ValueError('PRIMARY_PAIRED_SUPPORT_INVALID')
        metrics.append(_metric(f'primary.{year}.paired_hours', paired, 'paired_hour_bar_count'))
        for field in ('median_absolute_quote_difference', 'p95_absolute_quote_difference'):
            metrics.append(_metric(f'primary.{year}.{field}', _number(check[field]), quote_unit))
        datasets.extend([
            _dataset('histdata-original/' + item['source_file'], item['source_sha256'], 'original_histdata_zip'),
            _dataset('clock-corrected/' + item['output_file'], item['output_sha256'], 'complete_hour_bid_candidate'),
            _dataset(f'primary-comparison/{year}/{pair}/{year}-1h.parquet',
                     check['source_sha256'], 'primary_hourly_bid_comparison')])
    for name, field, unit in (('raw_minutes', 'raw_minutes', 'minute_bar_count'),
                              ('complete_hours', 'rows', 'hour_bar_count'),
                              ('incomplete_hours', 'incomplete_hours', 'incomplete_hour_bin_count')):
        metrics.append(_metric(name, sum(f[field] for f in files), unit))
    for item in sorted((w for w in receipt['witnesses'] if w['pair'] == pair), key=lambda w: w['date']):
        normalized_helper.require_witness(item, contract)
        prefix = 'witness.' + item['date']
        common, consecutive = _count(item['common_minutes']), _count(item['consecutive_pairs'])
        if not 0 < consecutive < common or set(item['correlations']) != {'-60', '-1', '0', '1', '60'}:
            raise ValueError('WITNESS_SUPPORT_OR_CONTROLS_INVALID')
        metrics.extend([_metric(prefix + '.common_minutes', common, 'paired_minute_bar_count'),
                        _metric(prefix + '.consecutive_pairs', consecutive, 'consecutive_minute_pair_count'),
                        _metric(prefix + '.p95_absolute_quote_difference',
                                _number(item['p95_absolute_quote_difference']), quote_unit)])
        for shift in normalized_helper.CONTROLS:
            metrics.append(_metric(f'{prefix}.correlation.shift_{shift}_minutes',
                                   _number(item['correlations'][str(shift)], correlation=True),
                                   'dimensionless_correlation'))
        datasets.append(_dataset('clock-witness/' + item['source_file'], item['source_sha256'],
                                 'independent_clock_witness_zip'))
    datasets.extend([
        _dataset('histdata-clock-corrected/STATUS.json', receipt_sha, 'normalized_cohort_receipt'),
        _dataset('histdata-clock-corrected/CLOCK_CONTRACT.json', receipt['binding']['config_sha256'],
                 'reviewed_clock_contract')])
    return dict(experiment_key=f'histdata-corrected-cohort:{pair}:{receipt_sha}',
        experiment_set_key='canonical-native-fx-recovery', actor='canonical-data-curation',
        lake='acquisition-not-admitted', lineage='UNVERIFIED', project='financial-data',
        phase='HISTDATA_CORRECTED_COHORT_QUALITY', config_sha256=receipt['binding']['config_sha256'],
        code_commit=code_commit, tags=dict(kind='corrected_histdata_cohort_quality', pair=pair,
            admission='NOT_ADMITTED', model_training='false', clock_verified='true',
            receipt_sha256=receipt_sha, quote_view='BID', calendar_holidays_certified='false',
            provider_clock_confirmed='false', raw_minutes_basis='deduplicated_observed_minutes',
            clock_verification_scope='empirical_histdata_2023_2025_cohort_not_provider_declaration',
            witness_signal='one_minute_close_quote_first_difference_not_percentage_or_log_return',
            witness_reference_quote_side='UNRESOLVED', witness_shift_unit='minute',
            witness_shift_convention='candidate_endpoint_minus_shift_minutes',
            primary_source_verification='receipt_digest_labels_retained_not_replayed'),
        datasets=datasets, metrics=metrics)


def build_verified_reports(normalized, consolidated, bulk_root, code_commit):
    """Read/verify retained evidence and return four aggregate reports; no I/O publication."""
    normalized, consolidated, bulk_root = map(lambda p: Path(p).resolve(),
                                             (normalized, consolidated, bulk_root))
    metadata = [normalized / name for name in ('STATUS.json', 'BINDING.json', 'CLOCK_CONTRACT.json')]
    metadata += [consolidated / name for name in ('STATUS.json', 'BINDING.json',
                                                 'QUALITY.eurusd.json', 'QUALITY.gbpusd.json')]
    before = {p: file_sha(p) for p in metadata}
    receipt = normalized_helper.status(normalized)
    state = consolidator.status(consolidated)
    if (receipt.get('state') != 'CLOCK_CORRECTED_COMPLETE_HOUR_CANDIDATES'
            or receipt.get('clock_verified') is not True or receipt.get('admitted') is not False
            or receipt.get('provider_clock_confirmed') is not False or receipt.get('interpolated_values') != 0):
        raise ValueError('VERIFIED_UNADMITTED_NORMALIZED_COHORT_REQUIRED')
    if (state.get('schema') != 'financial_data.observed_fx_consolidation.v1'
            or state.get('state') != 'OBSERVATIONS_CONSOLIDATED_REQUIRES_CALENDAR_AND_COVERAGE'
            or state.get('clock_verified') is not True or state.get('admitted') is not False
            or state.get('calendar_holidays_certified') is not False or state.get('interpolated_values') != 0
            or set(state['pairs']) != set(PAIRS)):
        raise ValueError('COMPLETE_UNADMITTED_CONSOLIDATION_REQUIRED')
    for root, body in ((normalized, receipt), (consolidated, state)):
        if json.loads((root / 'BINDING.json').read_text()) != body['binding']:
            raise ValueError('RETAINED_BINDING_MISMATCH')
    if state['binding']['normalized_receipt_sha256'] != before[normalized / 'STATUS.json']:
        raise ValueError('CONSOLIDATED_NORMALIZED_RECEIPT_MISMATCH')
    for binding, fields in ((receipt['binding'], {'code_sha256': 'normalize_histdata_observed_clock.py',
            'parser_sha256': 'histdata_clock_resolution.py',
            'witness_parser_sha256': 'recover_forexite_observations.py'}),
            (state['binding'], {'code_sha256': 'consolidate_fx_observations.py',
                               'quality_code_sha256': 'native_fx_recovery.py'})):
        if any(binding[key] != file_sha(Path(__file__).with_name(name)) for key, name in fields.items()):
            raise ValueError('PRODUCER_CODE_BINDING_CHANGED')
    contract = json.loads((normalized / 'CLOCK_CONTRACT.json').read_text())
    sources = {(s['pair'], s['year'], s['file'], s['sha256']) for s in contract['sources']}
    expected = {(f['pair'], f['year'], f['source_file'], f['source_sha256']) for f in receipt['files']}
    if len(sources) != 6 or sources != expected:
        raise ValueError('RAW_SOURCE_CONTRACT_MISMATCH')
    scope = {(p, date) for p in PAIRS for date in contract['witness_dates']}
    if len(scope) != 6 or {(w['pair'], w['date']) for w in receipt['witnesses']} != scope:
        raise ValueError('INDEPENDENT_WITNESS_COHORT_MISMATCH')
    raw_sources = {}
    for item in receipt['files'] + receipt['witnesses']:
        name, digest = item['source_file'], _sha(item['source_sha256'])
        if name in raw_sources and raw_sources[name] != digest:
            raise ValueError('CONFLICTING_RAW_SOURCE_IDENTITIES')
        raw_sources[name] = digest
    native.verify_sources({'source_sha256': raw_sources}, bulk_root)
    reports = [_cohort_report(pair, receipt, before[normalized / 'STATUS.json'], contract, code_commit)
               for pair in PAIRS]
    for pair in PAIRS:
        quality = json.loads((consolidated / f'QUALITY.{pair}.json').read_text())
        item = state['pairs'][pair]
        if quality['source_sha256'] != {item['output_file']: item['output_sha256']}:
            raise ValueError('CONSOLIDATED_QUALITY_SOURCE_MISMATCH')
        native.verify_sources(quality, consolidated)
        labels = pd.read_parquet(consolidated / item['output_file'], columns=['source_id'])
        if (len(labels) != _count(item['rows']) or len(labels) != quality['observed_rows']
                or labels.source_id.isna().any() or labels.groupby('source_id').size().to_dict() != item['source_row_counts']
                or quality['missing_expected_open_hours'] != item['missing_expected_open_hours']):
            raise ValueError('CONSOLIDATED_COUNTS_MISMATCH')
        report = native.build_report(pair, quality, before[consolidated / 'STATUS.json'], code_commit)
        report.update(experiment_key=f'consolidated-bid-quality:{pair}:' + _digest({
            'quality': before[consolidated / f'QUALITY.{pair}.json'],
            'receipt': before[consolidated / 'STATUS.json']}), phase='CONSOLIDATED_BID_QUALITY')
        report['tags'].update(kind='consolidated_bid_quality', clock_verified='true',
            normalized_receipt_sha256=before[normalized / 'STATUS.json'],
            consolidation_receipt_sha256=before[consolidated / 'STATUS.json'],
            calendar_holidays_certified='false')
        for metric in report['metrics']:
            metric['split'] = 'quality'
        cohort = next(r for r in reports if r['tags']['kind'] == 'corrected_histdata_cohort_quality'
                      and r['tags']['pair'] == pair)
        report['metrics'].extend(_metric('clock_cohort.' + m['metric'], m['value'], m['unit'])
                                 for m in cohort['metrics'])
        report['datasets'].extend(cohort['datasets'])
        for key in ('witness_signal', 'witness_reference_quote_side', 'witness_shift_unit',
                    'witness_shift_convention', 'clock_verification_scope', 'primary_source_verification'):
            report['tags'][key] = cohort['tags'][key]
        for label, count in sorted(item['source_row_counts'].items()):
            if not re.fullmatch(r'(?:fxcm:(?:' + pair + r':\d{4}|boundary:' + pair + r')|histdata:'
                                + pair + r':\d{4}):[0-9a-f]{64}', label):
                raise ValueError('CONSOLIDATED_SOURCE_LABEL_INVALID')
            report['datasets'].append(_dataset('consolidation-source/' + label, label.rsplit(':', 1)[1],
                                              'retained_source_identity'))
            report['metrics'].append(_metric('source_rows.' + label, _count(count), 'hour_bar_count'))
        report['datasets'].extend([
            _dataset('consolidated/STATUS.json', before[consolidated / 'STATUS.json'], 'consolidation_receipt'),
            _dataset('consolidated/BINDING.json', before[consolidated / 'BINDING.json'], 'consolidation_binding'),
            _dataset('consolidated/QUALITY.' + pair + '.json', before[consolidated / f'QUALITY.{pair}.json'],
                     'consolidated_quality_receipt')])
        reports.append(report)
    if any(file_sha(path) != digest for path, digest in before.items()):
        raise ValueError('EVIDENCE_CHANGED_DURING_BUILD')
    return reports


def main(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--status', action='store_true')
    for name in ('bulk-root', 'normalized-root', 'consolidated-root', 'predictor-root', 'local-copy'):
        parser.add_argument('--' + name, type=Path)
    for name in ('code-commit', 'runtime-code-commit', 'warehouse-url', 'mirror-host', 'mirror-relative-path'):
        parser.add_argument('--' + name)
    parser.add_argument('--token-env', default='DATA_GOV_LAKE_TOKEN')
    args = parser.parse_args(argv)
    target = args.root / 'PUBLICATION_STATUS.json'
    if args.status:
        state = json.loads(target.read_text())
        print(json.dumps(state, indent=2))
        return 0 if state['state'] == 'CONSOLIDATED_QUALITY_PUBLISHED_NOT_ADMITTED' else 2
    if any(getattr(args, key) is None for key in ('bulk_root', 'predictor_root', 'code_commit',
            'warehouse_url', 'local_copy', 'mirror_host', 'mirror_relative_path')):
        parser.error('publication requires bulk-root, predictor-root, code-commit, warehouse, copy and mirror arguments')
    repo, runtime = Path(__file__).resolve().parents[1], args.predictor_root.resolve()
    verify_pinned(repo, args.code_commit, CODE_FILES)
    runtime_commit = args.runtime_code_commit or subprocess.run(
        ['git', '-C', str(runtime), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    verify_pinned(runtime, runtime_commit,
                  ('tools/i6dmo/outbox.py', 'olap/store/src/predictor_olap_store/query.py'))
    normalized = args.normalized_root or args.bulk_root / 'histdata-clock-corrected-v2'
    consolidated = args.consolidated_root or args.bulk_root / 'fx-consolidated-v2'
    root = args.root.resolve()
    if root.is_relative_to(args.bulk_root.resolve()) or root.is_relative_to(repo):
        raise ValueError('OPERATIONAL_ROOT_MUST_BE_SEPARATE')
    ancestor = root
    while not ancestor.exists():
        ancestor = ancestor.parent
    filesystem = subprocess.run(['findmnt', '-n', '-o', 'FSTYPE', '--target', str(ancestor)],
                                capture_output=True, text=True, check=True).stdout.strip()
    if filesystem != 'ext4':
        raise ValueError('EXT4_OPERATIONAL_ROOT_REQUIRED')
    root.mkdir(parents=True, exist_ok=True)
    with (root / 'publication.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        box = None
        try:
            new_reports = build_verified_reports(normalized, consolidated, args.bulk_root, args.code_commit)
            sys.path.insert(0, str(runtime))
            sys.path.insert(0, str(runtime / 'olap/store/src'))
            from tools.i6dmo.outbox import HttpWarehouse, Outbox
            from predictor_olap_store.query import normalise_report
            for obj, relative in ((Outbox, 'tools/i6dmo/outbox.py'),
                                  (HttpWarehouse, 'tools/i6dmo/outbox.py'),
                                  (normalise_report, 'olap/store/src/predictor_olap_store/query.py')):
                if Path(inspect.getfile(obj)).resolve() != runtime / relative:
                    raise ValueError('PUBLICATION_RUNTIME_IMPORT_MISMATCH')
            box = Outbox(root / 'consolidated-quality-outbox.sqlite')
            for report in new_reports:
                box.enqueue(report, source_unit=report['tags']['kind'] + ':' + report['tags']['pair'])
            reports = [json.loads(item['body']) for item in box.items()]
            if (len(reports) != 4 or {r['experiment_key'] for r in reports}
                    != {r['experiment_key'] for r in new_reports}):
                raise ValueError('MIXED_OR_STALE_PUBLICATION_OUTBOX')
            delivery = box.pump(HttpWarehouse(args.warehouse_url, args.token_env))
            physical = root / 'consolidated_fx_quality.duckdb'
            digest = snapshot(physical, reports)
            if copy_closed(physical, args.local_copy) != digest:
                raise ValueError('LOCAL_MIRROR_MISMATCH')
            mirror = mirror_closed(physical, args.mirror_host, args.mirror_relative_path)
            complete = (len(reports) == 4 and delivery['pending'] == delivery['mismatch'] == 0
                        and delivery['delivered'] == 4)
            write_json(target, dict(state='CONSOLIDATED_QUALITY_PUBLISHED_NOT_ADMITTED' if complete
                                    else 'QUALITY_PUBLICATION_PENDING', admitted=False, expected_reports=4,
                warehouse=delivery, physical_sha256=digest, second_machine=mirror,
                runtime_code_commit=runtime_commit))
            return 0 if complete else 2
        except Exception as exc:
            write_json(target, dict(state='PUBLICATION_RETRY_PENDING', admitted=False,
                                    error_type=type(exc).__name__))
            raise
        finally:
            if box is not None:
                box.close()


if __name__ == '__main__':
    raise SystemExit(main())
