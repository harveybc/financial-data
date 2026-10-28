import importlib.util
from pathlib import Path
import sys

import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('hist_clock', SCRIPTS / 'histdata_clock_resolution.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_clock_hypotheses_distinguish_us_and_european_transitions():
    wall = pd.DatetimeIndex(['2023-03-10 12:00', '2023-03-13 12:00', '2023-03-27 12:00',
                             '2023-10-27 12:00', '2023-10-30 12:00', '2023-11-06 12:00'])
    assert module.clock(wall, 'DECLARED_FIXED_EST').hour.tolist() == [17] * 6
    assert module.clock(wall, 'US_EASTERN_CONTROL').hour.tolist() == [17, 16, 16, 16, 16, 17]
    assert module.clock(wall, 'EUROPEAN_DST_COHORT_HYPOTHESIS').hour.tolist() == [17, 17, 16, 16, 17, 17]


def test_hourly_bars_never_fill_an_absent_minute():
    ts = pd.date_range('2023-07-03 12:00', periods=120, freq='min')
    frame = pd.DataFrame({'native': ts, 'close': range(1, 121)})
    frame = frame.drop(index=10)
    result = module.complete_closes(frame, 'DECLARED_FIXED_EST')
    assert len(result) == 1
    assert result.close.iloc[0] == 120
    assert result.available_at.iloc[0] == pd.Timestamp('2023-07-03 19:00Z')


def test_all_hypotheses_use_identical_comparison_rows():
    base = pd.date_range('2023-01-03', periods=5, freq='h', tz='UTC')
    primary = pd.DataFrame({'available_at': base, 'BidClose': [1., 2., 3., 4., 5.]})
    candidates = {'A': pd.DataFrame({'available_at': base[:4], 'close': [1., 2., 3., 4.]}),
                  'B': pd.DataFrame({'available_at': base[1:], 'close': [2., 3., 4., 5.]})}
    rows = module.compare_common(primary, candidates)
    assert len(rows) == 2
    assert {r['n'] for r in rows} == {3}
    assert len({r['support_sha256'] for r in rows}) == 1
    assert all(r['median_abs'] == 0 for r in rows)


def test_duplicate_or_invalid_quote_is_not_accepted():
    frame = pd.DataFrame({'native': ['2023-01-03 12:00'] * 2, 'close': [1., 1.]})
    with pytest.raises(ValueError, match='INVALID_MINUTE'):
        module.complete_closes(frame, 'DECLARED_FIXED_EST')


def test_unknown_clock_is_not_guessed():
    with pytest.raises(ValueError, match='UNKNOWN_CLOCK'):
        module.clock(pd.DatetimeIndex(['2023-01-03']), 'best_fit')


def test_empty_common_support_is_not_completed_evidence():
    base = pd.date_range('2023-01-03', periods=2, freq='h', tz='UTC')
    primary = pd.DataFrame({'available_at': base[:1], 'BidClose': [1.]})
    candidate = pd.DataFrame({'available_at': base[1:], 'close': [1.]})
    with pytest.raises(ValueError, match='NO_COMMON_SUPPORT'):
        module.compare_common(primary, {'A': candidate})


def test_publication_recomputes_raw_evidence_before_building_metrics(tmp_path, monkeypatch):
    report = dict(schema='financial_data.histdata_clock_resolution.v1', admitted=False,
                  year=2023, files=[], pairs={'eurusd': {'comparisons': [dict(
                      date='2023-01-03', hypothesis='DECLARED_FIXED_EST', n=5,
                      support_sha256='a'*64, median_abs=.1, p95_abs=.2, max_abs=.3,
                      median_signed=-.1)]}})
    path = tmp_path / 'RESULT.json'
    import json
    path.write_text(json.dumps(report))
    monkeypatch.setattr(module, 'run', lambda *args: report)
    rows = module.build_verified_reports(path, tmp_path, tmp_path, 'commit')
    assert len(rows) == 1 and len(rows[0]['metrics']) == 5
    assert rows[0]['tags']['admission'] == 'NOT_ADMITTED'
    assert rows[0]['metrics'][0]['unit'] == 'count'
    assert rows[0]['metrics'][1]['unit'] == 'quote_difference'
    report['pairs']['eurusd']['comparisons'][0]['n'] = 6
    with pytest.raises(ValueError, match='REPLAY_MISMATCH'):
        module.build_verified_reports(path, tmp_path, tmp_path, 'commit')
