import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('admit_core', SCRIPTS / 'admit_core_fx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_calendar_removes_only_declared_holidays_and_weekly_closures():
    cfg = dict(required_start='2024-12-23T00:00Z', required_end_exclusive='2024-12-28T00:00Z',
               closed_intervals=[dict(start='2024-12-24T20:00Z', end='2024-12-26T06:00Z')])
    grid = module.required_hours(cfg)
    assert pd.Timestamp('2024-12-24T19:00Z') in grid
    assert pd.Timestamp('2024-12-25T12:00Z') not in grid
    assert pd.Timestamp('2024-12-26T06:00Z') in grid
    assert pd.Timestamp('2024-12-27T22:00Z') not in grid


def test_one_missing_operating_hour_prevents_admission():
    ts = pd.date_range('2023-07-03T10:00Z', periods=3, freq='h')
    frame = pd.DataFrame({'timestamp': ts, 'available_at': ts+pd.Timedelta(hours=1),
        'BidOpen': 1., 'BidHigh': 1.1, 'BidLow': .9, 'BidClose': 1.})
    assert module.require_complete(frame, ts) is None
    with pytest.raises(ValueError, match='MISSING_REQUIRED_OPERATING_HOURS'):
        module.require_complete(frame.drop(index=1), ts)
    frame.loc[0, 'BidLow'] = -1.
    with pytest.raises(ValueError, match='INVALID'):
        module.require_complete(frame, ts)


def test_declared_clock_requires_clear_independent_agreement():
    offsets = [dict(offset_hours=k, common_support_hours=2000,
                    ohlc_median_abs_diff_pips=.1 if k == 0 else 5.,
                    ohlc_p95_abs_diff_pips=.5 if k == 0 else 20.) for k in range(-3, 4)]
    module.require_declared_clock({'offsets': offsets})
    offsets[4]['ohlc_median_abs_diff_pips'] = .1
    with pytest.raises(ValueError, match='CLOCK'):
        module.require_declared_clock({'offsets': offsets})


def test_consumed_hourly_and_half_hour_files_must_both_be_in_receipt(tmp_path):
    with pytest.raises(ValueError, match='RECEIPT_COVERAGE'):
        module.verify_downloads(tmp_path, {'downloads': []}, ['eurusd'])
    for name in ('EURUSD_H1.parquet', 'EURUSD_M30.parquet'):
        (tmp_path/name).write_bytes(b'observed')
    entries = [{'file': name, 'sha256': module.file_sha(tmp_path/name)}
               for name in ('EURUSD_H1.parquet', 'EURUSD_M30.parquet')]
    assert len(module.verify_downloads(tmp_path, {'downloads': entries}, ['eurusd'])) == 2
    with pytest.raises(ValueError, match='RECEIPT_COVERAGE'):
        module.verify_downloads(tmp_path, {'downloads': entries+entries}, ['eurusd'])


def test_open_and_closed_intervals_are_unambiguous_complements():
    grid = pd.DatetimeIndex(['2024-01-05T20:00Z', '2024-01-05T21:00Z',
                             '2024-01-07T22:00Z', '2024-01-07T23:00Z'])
    opened = module.session_intervals(grid)
    assert opened == [['2024-01-05T20:00:00+00:00', '2024-01-05T22:00:00+00:00'],
                      ['2024-01-07T22:00:00+00:00', '2024-01-08T00:00:00+00:00']]
    assert module.closure_intervals(opened) == [
        ['2024-01-05T22:00:00+00:00', '2024-01-07T22:00:00+00:00']]
