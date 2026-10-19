import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('consolidate', SCRIPTS / 'consolidate_fx_observations.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def quotes(hours, close=1.1):
    ts = pd.date_range('2023-07-03T10:00Z', periods=hours, freq='h')
    frame = pd.DataFrame({'timestamp': ts, 'available_at': ts+pd.Timedelta(hours=1),
                          'BidOpen': close, 'BidHigh': close+.001,
                          'BidLow': close-.001, 'BidClose': close})
    return frame


def test_source_priority_and_original_values_are_preserved():
    native = quotes(3).drop(index=1)
    recovered = quotes(3, 1.10002)
    frame, counts = module.combine_sources([('native', native), ('recovered', recovered)])
    assert len(frame) == 3
    assert frame.source_id.tolist() == ['native', 'recovered', 'native']
    assert frame.BidClose.tolist() == [1.1, 1.10002, 1.1]
    assert counts == {'native': 2, 'recovered': 1}
    assert not any(c.startswith('Ask') for c in frame.columns)


def test_conflicting_duplicates_and_false_availability_are_rejected():
    frame = pd.concat([quotes(2), quotes(2, 1.2)], ignore_index=True)
    with pytest.raises(ValueError, match='DUPLICATE'):
        module.combine_sources([('native', frame)])
    frame = quotes(2)
    frame.loc[0, 'available_at'] -= pd.Timedelta(hours=1)
    with pytest.raises(ValueError, match='AVAILABILITY'):
        module.combine_sources([('native', frame)])


def test_unexplained_missing_hours_stay_missing():
    frame, _ = module.combine_sources([('native', quotes(3).drop(index=1))])
    assert len(frame) == 2
    assert pd.Timestamp('2023-07-03T11:00Z') not in set(frame.timestamp)


def test_bid_only_quality_does_not_invent_ask_or_spread():
    from native_fx_recovery import audit
    config = dict(required_start='2023-01-01T00:00Z', required_end_exclusive='2024-01-01T00:00Z',
                  train_start='2020-01-01T00:00Z', train_end_exclusive='2024-01-01T00:00Z',
                  quote_view='BID', calendar_basis='ASSUMED_WEEKLY_OPEN_NOT_HOLIDAY_ADMISSION')
    q = audit(quotes(3), config, bid_only=True)
    assert q['observed_rows'] == 3
    assert q['crossed_side_bar_endpoints'] is None
    assert q['executable_spread_eligible'] is False
    assert q['missing_expected_open_hours'] > 0
    assert len(q['months']) == 12


def test_closed_weekly_quotes_never_count_as_input_bars():
    from native_fx_recovery import weekly_open_grid
    config = dict(required_start='2023-07-07T00:00Z', required_end_exclusive='2023-07-10T00:00Z')
    grid = weekly_open_grid(config)
    assert pd.Timestamp('2023-07-07T20:00Z') in grid
    assert pd.Timestamp('2023-07-07T21:00Z') not in grid
    assert pd.Timestamp('2023-07-08T10:00Z') not in grid
    assert pd.Timestamp('2023-07-09T20:00Z') not in grid
    assert pd.Timestamp('2023-07-09T21:00Z') in grid
