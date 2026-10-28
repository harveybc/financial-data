"""Synthetic builder validation only; no warehouse, credentials or publication."""
import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('publish_consolidated_fx', SCRIPTS / 'publish_consolidated_fx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, body):
    path.write_text(json.dumps(body, sort_keys=True))
    return module.file_sha(path)


def edit(path, change):
    body = json.loads(path.read_text())
    change(body)
    write(path, body)


@pytest.fixture
def evidence(tmp_path):
    bulk = tmp_path / 'bulk'
    normalized = bulk / 'histdata-clock-corrected-v2'
    consolidated = bulk / 'fx-consolidated-v2'
    normalized.mkdir(parents=True)
    consolidated.mkdir()
    sources, files, witnesses = [], [], []
    for pair in ('eurusd', 'gbpusd'):
        for year in (2023, 2024, 2025):
            source = bulk / f'histdata/{pair}-{year}/source.zip'
            source.parent.mkdir(parents=True)
            source.write_bytes(f'synthetic original archive {pair} {year}'.encode())
            source_id = module.file_sha(source)
            source_name = str(source.relative_to(bulk))
            sources.append(dict(pair=pair, year=year, file=source_name, sha256=source_id))
            ts = pd.date_range(f'{year}-07-03T10:00Z', periods=2, freq='h')
            bars = pd.DataFrame(dict(timestamp=ts, available_at=ts + pd.Timedelta(hours=1),
                BidOpen=1.1, BidHigh=1.2, BidLow=1., BidClose=1.1, observed_minutes=60))
            target = normalized / f'{pair}-{year}.parquet'
            bars.to_parquet(target, index=False)
            files.append(dict(pair=pair, year=year, source_file=source_name,
                source_sha256=source_id, raw_minutes=125, identical_duplicates_removed=1,
                incomplete_hours=1, output_file=target.name, output_sha256=module.file_sha(target), rows=2,
                primary_check=dict(source_sha256=('a' if pair == 'eurusd' else 'b') * 64,
                    paired_hours=2, median_absolute_quote_difference=.00001,
                    p95_absolute_quote_difference=.00002)))
        for date in ('2023-01-03', '2023-06-30', '2023-07-10'):
            witness = bulk / 'forexite' / (date + '.zip')
            witness.parent.mkdir(exist_ok=True)
            witness.write_bytes(b'synthetic independent witness archive')
            witnesses.append(dict(pair=pair, date=date,
                source_file=str(witness.relative_to(bulk)), source_sha256=module.file_sha(witness),
                consecutive_pairs=200, common_minutes=205,
                p95_absolute_quote_difference=.00003,
                correlations={'-60': .1, '-1': .05, '0': .99, '1': -.02, '60': .08}))
    config = dict(schema='financial_data.histdata_observed_clock.v1', sources=sources,
                  hypothesis='EUROPEAN_DST_COHORT_HYPOTHESIS', quote_view='BID',
                  witness_dates=['2023-01-03', '2023-06-30', '2023-07-10'])
    config.update(module.normalized_helper.DEFAULTS)
    contract_sha = write(normalized / 'CLOCK_CONTRACT.json', config)
    binding = dict(config_sha256=contract_sha,
        code_sha256=module.file_sha(SCRIPTS / 'normalize_histdata_observed_clock.py'),
        parser_sha256=module.file_sha(SCRIPTS / 'histdata_clock_resolution.py'),
        witness_parser_sha256=module.file_sha(SCRIPTS / 'recover_forexite_observations.py'))
    write(normalized / 'BINDING.json', binding)
    receipt = dict(schema='financial_data.histdata_observed_normalization.v1',
        state='CLOCK_CORRECTED_COMPLETE_HOUR_CANDIDATES', clock_verified=True, admitted=False,
        provider_clock_confirmed=False, interpolated_values=0,
        basis='EMPIRICAL_COHORT_CORRECTION_WITH_INDEPENDENT_CONTROLS',
        files=files, witnesses=witnesses, binding=binding)
    receipt_sha = write(normalized / 'STATUS.json', receipt)
    binding = dict(normalized_receipt_sha256=receipt_sha,
        code_sha256=module.file_sha(SCRIPTS / 'consolidate_fx_observations.py'),
        quality_code_sha256=module.file_sha(SCRIPTS / 'native_fx_recovery.py'),
        config_sha256='c' * 64, boundary_receipt_sha256='d' * 64)
    write(consolidated / 'BINDING.json', binding)
    pairs = {}
    for pair in ('eurusd', 'gbpusd'):
        frames = [pd.read_parquet(normalized / f'{pair}-{year}.parquet') for year in (2023, 2024, 2025)]
        frame = pd.concat(frames, ignore_index=True)
        frame['source_id'] = f'fxcm:{pair}:2023:' + 'e' * 64
        target = consolidated / f'{pair}.parquet'
        frame.to_parquet(target, index=False)
        quality = dict(schema='financial_data.native_fx_quality.v1', admitted=False,
            quote_view='BID', interpolated_values=0, source_sha256={target.name: module.file_sha(target)},
            calendar_basis='ASSUMED_WEEKLY_OPEN_NOT_HOLIDAY_ADMISSION', observed_rows=6,
            missing_expected_open_hours=10, identical_duplicates_removed=0,
            outside_assumed_open_schedule_rows=0, crossed_side_bar_endpoints=None,
            months=[dict(month=f'{year}-07', observed_rows=2, expected_open_hours=5,
                         missing_expected_open_hours=3) for year in (2023, 2024, 2025)],
            return_outliers=dict(state='NOT_ESTIMABLE', count=None,
                                 reference=dict(n=0, median=None, mad=None)))
        quality_sha = write(consolidated / f'QUALITY.{pair}.json', quality)
        pairs[pair] = dict(rows=6, output_file=target.name, output_sha256=module.file_sha(target),
            quality_sha256=quality_sha, source_row_counts={f'fxcm:{pair}:2023:' + 'e' * 64: 6},
            source_transitions=[], missing_expected_open_hours=10,
            outside_assumed_open_schedule_rows=0, observations_excluded_by_closed_weekly_schedule=1)
    write(consolidated / 'STATUS.json', dict(schema='financial_data.observed_fx_consolidation.v1',
        state='OBSERVATIONS_CONSOLIDATED_REQUIRES_CALENDAR_AND_COVERAGE', admitted=False,
        clock_verified=True, calendar_holidays_certified=False, interpolated_values=0,
        pairs=pairs, binding=binding))
    return normalized, consolidated, bulk


def build(evidence):
    return module.build_verified_reports(*evidence, 'f' * 40)


def test_exact_four_quality_reports_and_precise_statistical_units(evidence):
    reports = build(evidence)
    assert len(reports) == len({r['experiment_key'] for r in reports}) == 4
    assert [r['tags']['pair'] for r in reports] == ['eurusd', 'gbpusd', 'eurusd', 'gbpusd']
    assert all(r['tags']['admission'] == 'NOT_ADMITTED' and r['tags']['model_training'] == 'false'
               and all(m['split'] == 'quality' for m in r['metrics']) for r in reports)
    clock = reports[0]
    rows = {m['metric']: m for m in clock['metrics']}
    assert rows['raw_minutes']['value'] == 375
    assert rows['complete_hours']['value'] == 6
    assert rows['incomplete_hours']['value'] == 3
    assert rows['raw_minutes']['unit'] == 'minute_bar_count'
    assert rows['primary.2023.p95_absolute_quote_difference']['unit'] == 'USD_per_EUR'
    assert rows['witness.2023-01-03.correlation.shift_0_minutes']['unit'] == 'dimensionless_correlation'
    assert 'quote_first_difference' in clock['tags']['witness_signal']
    assert reports[1]['metrics'][next(i for i, m in enumerate(reports[1]['metrics'])
        if m['metric'] == 'primary.2023.p95_absolute_quote_difference')]['unit'] == 'USD_per_GBP'
    consolidated = reports[2]
    assert next(m for m in consolidated['metrics'] if m['metric'] == 'clock_cohort.raw_minutes')['value'] == 375
    assert next(m for m in consolidated['metrics'] if m['metric'] ==
                'clock_cohort.witness.2023-01-03.correlation.shift_0_minutes')['unit'] == 'dimensionless_correlation'
    assert any(m['metric'] == 'coverage.2025-07.observed_rows' for m in consolidated['metrics'])
    assert next(m for m in consolidated['metrics'] if m['metric'] == 'return_outlier_count')['value'] is None
    assert any(d['role'] == 'primary_hourly_bid_comparison' and d['sha256'] == 'a' * 64
               for d in clock['datasets'])
    assert any(d['resource'].endswith('fxcm:eurusd:2023:' + 'e' * 64) for d in consolidated['datasets'])
    text = json.dumps(reports, allow_nan=False)
    assert str(evidence[2]) not in text and 'BidClose' not in text and 'observed_log_return' not in text
    assert '/home/' not in text and '://' not in text
    assert reports == build(evidence)


@pytest.mark.parametrize('target', ['raw', 'witness', 'normalized', 'consolidated', 'quality'])
def test_real_helper_hash_checks_reject_changed_bytes(evidence, target):
    normalized, consolidated, bulk = evidence
    path = {'raw': bulk / 'histdata/eurusd-2023/source.zip',
            'witness': bulk / 'forexite/2023-01-03.zip',
            'normalized': normalized / 'eurusd-2023.parquet',
            'consolidated': consolidated / 'eurusd.parquet',
            'quality': consolidated / 'QUALITY.eurusd.json'}[target]
    path.write_bytes(b'tampered synthetic evidence')
    with pytest.raises(ValueError):
        build(evidence)


@pytest.mark.parametrize('change', ['admitted', 'unverified', 'incomplete', 'binding', 'receipt_link',
                                   'source_escape', 'primary_digest', 'witness_signal', 'counts'])
def test_false_claims_or_broken_lineage_refused(evidence, change):
    normalized, consolidated, bulk = evidence
    path = normalized / 'STATUS.json'
    if change == 'admitted':
        edit(path, lambda x: x.update(admitted=True))
    if change == 'unverified':
        edit(path, lambda x: x.update(clock_verified=False))
    if change == 'incomplete':
        edit(path, lambda x: x.update(state='NORMALIZING'))
    if change == 'binding':
        edit(consolidated / 'BINDING.json', lambda x: x.update(config_sha256='0' * 64))
    if change == 'receipt_link':
        for p in (consolidated / 'BINDING.json', consolidated / 'STATUS.json'):
            edit(p, lambda x: (x.get('binding', x)).update(normalized_receipt_sha256='0' * 64))
    if change == 'source_escape':
        edit(path, lambda x: x['files'][0].update(source_file='../escape.zip'))
    if change == 'primary_digest':
        edit(path, lambda x: x['files'][0]['primary_check'].update(source_sha256='invalid'))
    if change == 'witness_signal':
        edit(path, lambda x: x['witnesses'][0]['correlations'].update({'0': None}))
    if change == 'counts':
        edit(path, lambda x: x['files'][0].update(raw_minutes=1))
    if change in ('source_escape', 'primary_digest', 'witness_signal', 'counts'):
        # Keep the outer binding valid so each inner validation is actually exercised.
        receipt_sha = module.file_sha(path)
        for p in (consolidated / 'BINDING.json', consolidated / 'STATUS.json'):
            edit(p, lambda x: (x.get('binding', x)).update(normalized_receipt_sha256=receipt_sha))
    expected = {'primary_digest': 'EVIDENCE_DIGEST', 'witness_signal': 'CLOCK_WITNESS',
                'counts': 'RAW_MINUTE'}.get(change)
    with pytest.raises(ValueError, match=expected):
        build(evidence)


def test_consolidated_quality_builder_and_source_verifier_are_reused(evidence, monkeypatch):
    calls = []
    original = module.native.build_report
    def report(*args):
        calls.append(args[0])
        return original(*args)
    monkeypatch.setattr(module.native, 'build_report', report)
    build(evidence)
    assert calls == ['eurusd', 'gbpusd']


def test_pinning_compares_actual_file_bytes_to_requested_git_commit(tmp_path, monkeypatch):
    source = tmp_path / '_scripts/helper.py'
    source.parent.mkdir()
    source.write_text('synthetic pinned code\n')
    commands = []
    def git(command, **kwargs):
        commands.append(command)
        return type('Result', (), {'stdout': source.read_bytes()})()
    monkeypatch.setattr(module.subprocess, 'run', git)
    module.verify_pinned(tmp_path, 'f' * 40, ['_scripts/helper.py'])
    assert commands[0][-1] == 'f' * 40 + ':_scripts/helper.py'
    monkeypatch.setattr(module.subprocess, 'run', lambda *a, **kw: type('Result', (), {'stdout': b'drift'})())
    with pytest.raises(ValueError, match='CODE_NOT_PINNED'):
        module.verify_pinned(tmp_path, 'f' * 40, ['_scripts/helper.py'])


@pytest.mark.parametrize('field,value', [('admitted', True), ('clock_verified', False),
    ('calendar_holidays_certified', True), ('interpolated_values', 1), ('state', 'CONSOLIDATING')])
def test_consolidation_cannot_promote_or_hide_partial_state(evidence, field, value):
    edit(evidence[1] / 'STATUS.json', lambda x: x.update({field: value}))
    with pytest.raises(ValueError, match='UNADMITTED_CONSOLIDATION'):
        build(evidence)


def test_changed_quality_is_checked_even_if_resealed_and_never_relabelled_admitted(evidence):
    normalized, consolidated, _ = evidence
    quality = consolidated / 'QUALITY.eurusd.json'
    edit(quality, lambda x: x.update(admitted=True))
    edit(consolidated / 'STATUS.json', lambda x: x['pairs']['eurusd'].update(
        quality_sha256=module.file_sha(quality)))
    with pytest.raises(ValueError, match='UNADMITTED_OBSERVED_BID'):
        build(evidence)
