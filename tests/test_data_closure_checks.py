"""D6 tests, written before the checks they govern (SATOSHI_DATA_AND_RL_ORDER_2026_10_18 D.6).

Synthetic frames only; no provider access, no lake read, no admission."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).parents[1] / f'_scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checks = load('data_closure_checks')
schedule = load('native_session_schedule')
inventory = load('required_variable_inventory')
witness = load('clock_witness_by_date')


def hourly(start, end, drop=()):
    index = pd.date_range(start, end, freq='h', tz='UTC', inclusive='left')
    index = index[~index.isin(pd.to_datetime(list(drop), utc=True))]
    close = 1.1 + np.arange(len(index)) * 1e-5
    return pd.DataFrame({'timestamp': index, 'BidOpen': close, 'BidHigh': close + 1e-4,
                         'BidLow': close - 1e-4, 'BidClose': close,
                         'available_at': index + pd.Timedelta(hours=1)})


# ---------------------------------------------------------------- missing month, 100% finite rows

def test_missing_month_is_in_the_denominator_despite_fully_finite_rows():
    frame = hourly('2021-01-01', '2021-04-01', drop=pd.date_range('2021-02-01', '2021-03-01', freq='h', tz='UTC'))
    assert np.isfinite(frame.BidClose).all()
    report = checks.monthly_coverage(frame.timestamp, '2021-01-01', '2021-04-01')
    assert [m['month'] for m in report] == ['2021-01', '2021-02', '2021-03']
    assert report[1]['observed_rows'] == 0 and report[1]['status'] == 'MONTH_ABSENT'
    assert checks.finite_fraction(frame.BidClose) == 1.0          # finite fraction cannot excuse it


# ---------------------------------------------------------------- missing file

def test_missing_file_is_in_the_denominator(tmp_path):
    (tmp_path / 'present.parquet').write_bytes(b'x')
    status = checks.required_files_status(['present.parquet', 'absent.parquet'], tmp_path)
    assert status['denominator'] == 2 and status['present'] == 1
    assert status['missing'] == ['absent.parquet']


# ---------------------------------------------------------------- timezone / DST shift

def minutes(start_native, n=60, close=1.1):
    return pd.DataFrame({'timestamp_native': pd.date_range(start_native, periods=n, freq='min'),
                         'TICKER': 'EURUSD', 'CLOSE': close})


def test_dst_shift_is_detected_not_fitted():
    # Candidate minutes stamped in Europe/Berlin summer time (UTC+2) ending 12:00 local = 10:00Z.
    candidate = minutes('2023-07-03 11:01', close=1.2)
    primary = pd.DataFrame({'available_at': pd.to_datetime(['2023-07-03 10:00', '2023-07-03 11:00'], utc=True),
                            'BidClose': [1.2, 1.9], 'AskClose': [1.2001, 1.9001]})
    table = witness.hypothesis_table(primary, candidate)
    by = {row['clock_hypothesis']: row for row in table}
    assert by['EUROPE_BERLIN']['bid']['max_abs'] == pytest.approx(0.0)
    assert by['FIXED_UTC_PLUS_60']['bid']['max_abs'] == pytest.approx(0.7)   # one hour off in summer
    assert all(row['clock_verified'] is False for row in table)                # a score is not verification
    assert 'fitted_offset' not in json.dumps(table)


# ---------------------------------------------------------------- incomplete minute / hour

def test_incomplete_hour_is_excluded_and_counted():
    candidate = minutes('2023-01-03 11:01').drop(index=7)
    primary = pd.DataFrame({'available_at': pd.to_datetime(['2023-01-03 11:00'], utc=True),
                            'BidClose': [1.1], 'AskClose': [1.1001]})
    table = witness.hypothesis_table(primary, candidate)
    assert all(row['support']['incomplete_hours'] == 1 and row['bid']['paired_hours'] == 0 for row in table)


# ---------------------------------------------------------------- conflicting duplicate

def test_conflicting_duplicate_fails_and_identical_duplicate_is_counted():
    frame = hourly('2021-01-04', '2021-01-05')
    identical = pd.concat([frame, frame.iloc[:1]])
    assert checks.duplicate_report(identical) == {'identical': 1, 'conflicting': 0}
    conflicting = pd.concat([frame, frame.iloc[:1].assign(BidClose=9.9)])
    with pytest.raises(ValueError, match='CONFLICTING_DUPLICATE'):
        checks.duplicate_report(conflicting, strict=True)


# ---------------------------------------------------------------- impossible OHLC versus real extreme

def test_impossible_ohlc_fails_but_a_real_extreme_is_only_flagged():
    frame = hourly('2021-01-04', '2021-01-06')
    bad = frame.copy(); bad.loc[3, 'BidHigh'] = bad.loc[3, 'BidLow'] - 1e-3
    with pytest.raises(ValueError, match='INVALID_OHLC'):
        checks.ohlc_report(bad, 'Bid')
    extreme = frame.copy()
    extreme.loc[20:, ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']] *= 0.97     # a 3% crash, coherent OHLC
    assert checks.ohlc_report(extreme, 'Bid') == {'invalid_rows': 0}
    flags = checks.return_flags(extreme, train_end='2021-01-05')
    assert flags['state'] == 'FLAGGED_NOT_REMOVED' and flags['count'] >= 1
    assert len(flags['retained_rows']) == len(extreme)                           # nothing removed


def test_zero_scale_reference_is_not_estimable():
    flat = hourly('2021-01-04', '2021-01-05'); flat[['BidOpen', 'BidHigh', 'BidLow', 'BidClose']] = 1.1
    assert checks.return_flags(flat, train_end='2021-01-05')['state'] == 'NOT_ESTIMABLE'


# ---------------------------------------------------------------- release after t

def test_value_released_after_decision_time_is_not_consumable():
    t = pd.Timestamp('2021-03-02 09:00Z')
    assert checks.consumable(event_time=pd.Timestamp('2021-03-01', tz='UTC'), available_at=pd.Timestamp('2021-03-02 08:00Z'), t=t)
    assert not checks.consumable(event_time=pd.Timestamp('2021-03-01', tz='UTC'), available_at=pd.Timestamp('2021-03-02 10:00Z'), t=t)
    with pytest.raises(ValueError, match='AVAILABILITY_BEFORE_EVENT'):
        checks.consumable(event_time=pd.Timestamp('2021-03-03', tz='UTC'), available_at=pd.Timestamp('2021-03-02', tz='UTC'), t=t)


# ---------------------------------------------------------------- gap not compressed into a fixed tick

def test_open_session_gap_keeps_its_elapsed_hours():
    frame = hourly('2021-01-04', '2021-01-05', drop=['2021-01-04 05:00Z', '2021-01-04 06:00Z'])
    steps = checks.elapsed_steps(frame.timestamp)
    assert steps['max_elapsed_hours'] == 3 and steps['steps_over_one_hour'] == 1
    assert steps['one_hour_returns_defined'] == len(frame) - 2                   # the 3 h jump is not a 1 h return


# ---------------------------------------------------------------- session schedule and missing-run classification

def test_missing_runs_separate_source_closure_file_absence_and_missing_quote():
    failed_weeks = {('eurusd', 2024, 35)}
    runs = [{'start': '2024-08-25T21:00:00+00:00', 'end': '2024-08-30T20:00:00+00:00', 'hours': 120},
            {'start': '2024-12-25T00:00:00+00:00', 'end': '2024-12-25T21:00:00+00:00', 'hours': 22},
            {'start': '2024-03-13T07:00:00+00:00', 'end': '2024-03-13T07:00:00+00:00', 'hours': 1}]
    out = schedule.classify_runs('eurusd', runs, failed_weeks)
    assert [r['class'] for r in out] == ['SOURCE_FILE_ABSENT', 'CALENDAR_RESOLUTION_CANDIDATE', 'MISSING_QUOTE_OPEN_SESSION']
    assert all(r['closure_verified'] is False for r in out)                      # never auto-closed


def test_weekly_open_close_are_observed_not_assumed():
    frame = hourly('2021-01-03 22:00', '2021-01-08 21:00')                      # Sun 22:00Z .. Fri 20:00Z bar start
    weeks = schedule.weekly_schedule(frame.timestamp)
    assert weeks[0]['first_bar_utc'] == '2021-01-03T22:00:00+00:00'
    assert weeks[0]['first_bar_ny_local'] == '2021-01-03T17:00:00-05:00'
    assert weeks[0]['last_bar_ny_local'] == '2021-01-08T15:00:00-05:00'


# ---------------------------------------------------------------- inventory denominator

def test_inventory_keeps_every_configured_variable_and_counts_missing_files(tmp_path):
    docs = tmp_path / 'features/cross_source_docs'
    for slug, src in (('a', 'macro_economic/x/a.parquet'), ('b', 'market_data/forex/g10/eurusd/daily.parquet')):
        (docs / slug).mkdir(parents=True)
        (docs / slug / 'provenance.json').write_text(json.dumps(
            {'source': src, 'slug': slug, 'status': 'ok', 'rows_native': 10, 'columns': ['value'],
             'start': '2020-01-01T00:00:00+00:00', 'end': '2025-12-01T00:00:00+00:00', 'timeframes': {}}))
    (tmp_path / 'macro_economic/x').mkdir(parents=True)
    pd.DataFrame({'timestamp': pd.date_range('2020-01-01', periods=3, freq='MS', tz='UTC'), 'value': [1.0, 2.0, 3.0]}
                 ).to_parquet(tmp_path / 'macro_economic/x/a.parquet', index=False)
    cfg = {'pairs': ['eurusd'], 'quote_view': 'BID', 'periodicity': 'H1', 'provider': 'FXCM',
           'required_start': '2020-01-01T00:00:00Z', 'required_end_exclusive': '2026-01-01T00:00:00Z'}
    inv = inventory.build(tmp_path, cfg, model_candidates=['fred.rates.dgs5.level', 'px.close_loc'],
                          lake_root=tmp_path, chunk=(0, 1))
    ids = {r['variable_id'] for r in inv['variables']}
    assert {'catalog:a', 'catalog:b', 'native:eurusd:H1:BID', 'model:fred.rates.dgs5.level', 'model:px.close_loc'} <= ids
    assert inv['denominator']['all_catalog_variables'] == 2
    assert inv['denominator']['trading_required'] >= 1 and inv['denominator']['model_candidates'] == 2
    byid = {r['variable_id']: r for r in inv['variables']}
    assert byid['catalog:b']['file_status'] == 'MISSING' and byid['catalog:a']['file_status'] == 'PRESENT'
    assert byid['catalog:a']['monthly_coverage'][1]['observed_rows'] == 1
    assert byid['catalog:a']['monthly_coverage'][-1]['observed_rows'] == 0           # 2025-12 absent, still listed
    assert inv['hardcoded_population_sizes'] == []
