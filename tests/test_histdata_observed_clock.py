import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('observed_clock', SCRIPTS / 'normalize_histdata_observed_clock.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def minute_frame():
    ts = pd.date_range('2023-07-03 10:00', periods=120, freq='min')
    close = 1 + np.arange(len(ts)) / 100000
    return pd.DataFrame(dict(native=ts, open=close-.00001, high=close+.00002,
                             low=close-.00002, close=close, volume=0))


def test_complete_bars_preserve_ohlc_and_availability():
    f = minute_frame()
    actual, incomplete = module.complete_bars(f)
    assert incomplete == 0 and len(actual) == 2
    assert actual.timestamp.iloc[0] == pd.Timestamp('2023-07-03 14:00Z')
    assert actual.available_at.iloc[0] == pd.Timestamp('2023-07-03 15:00Z')
    assert actual.BidOpen.iloc[0] == f.open.iloc[0]
    assert actual.BidClose.iloc[0] == f.close.iloc[59]
    assert actual.BidHigh.iloc[0] == f.high.iloc[:60].max()
    assert actual.BidLow.iloc[0] == f.low.iloc[:60].min()
    assert actual.observed_minutes.tolist() == [60, 60]
    changed = f.copy()
    changed.loc[60:, ['open', 'high', 'low', 'close']] += .1
    pd.testing.assert_frame_equal(module.complete_bars(changed)[0].iloc[:1], actual.iloc[:1])


def test_missing_minute_cannot_be_an_hourly_replacement():
    actual, incomplete = module.complete_bars(minute_frame().drop(index=10))
    assert incomplete == 1 and len(actual) == 1
    assert actual.timestamp.iloc[0] == pd.Timestamp('2023-07-03 15:00Z')


def test_returns_do_not_bridge_missing_minutes():
    ts = pd.DatetimeIndex(['2023-01-03T00:00Z', '2023-01-03T00:01Z',
                           '2023-01-03T05:00Z', '2023-01-03T05:01Z'])
    f = pd.DataFrame({'endpoint': ts, 'reference': [1., 2., 100., 101.],
                      'aligned': [1., 2., 100., 101.]})
    result = module.return_statistics(f)
    assert result['consecutive_pairs'] == 2
    assert result['correlations']['aligned'] is None  # constant differences


def test_alignment_controls_fail_for_one_minute_lag():
    rng = np.random.default_rng(21)
    ts = pd.date_range('2023-07-03T00:00Z', periods=900, freq='min')
    values = 1 + np.cumsum(rng.normal(0, .00002, len(ts)))
    candidate = pd.DataFrame({'endpoint': ts, 'close': values})
    reference = pd.DataFrame({'endpoint': ts, 'close': values+.0001})
    good = module.witness_statistics(reference, candidate)
    module.require_witness(good)
    candidate.endpoint += pd.Timedelta(minutes=1)
    with pytest.raises(ValueError, match='CLOCK_WITNESS'):
        module.require_witness(module.witness_statistics(reference, candidate))


def test_seasonal_rule_and_ambiguous_time():
    from histdata_clock_resolution import clock
    wall = pd.DatetimeIndex(['2023-03-24 12:00', '2023-03-27 12:00',
                             '2023-10-27 12:00', '2023-10-30 12:00'])
    assert clock(wall, module.HYPOTHESIS).hour.tolist() == [17, 16, 16, 17]
    with pytest.raises(Exception):
        clock(pd.DatetimeIndex(['2023-10-28 20:30']), module.HYPOTHESIS)


def test_status_checks_retained_contract_and_output_bytes(tmp_path):
    import json
    from publish_native_fx_quality import file_sha
    (tmp_path / 'CLOCK_CONTRACT.json').write_text('{}')
    bars, _ = module.complete_bars(minute_frame())
    path = tmp_path / 'candidate.parquet'
    bars.to_parquet(path, index=False)
    report = dict(schema='financial_data.histdata_observed_normalization.v1', admitted=False,
                  state='NORMALIZING', clock_verified=False,
                  binding={'config_sha256': file_sha(tmp_path / 'CLOCK_CONTRACT.json')},
                  files=[dict(output_file=path.name, output_sha256=file_sha(path), rows=len(bars))])
    (tmp_path / 'STATUS.json').write_text(json.dumps(report))
    assert module.status(tmp_path)['clock_verified'] is False
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='OUTPUT_CHANGED'):
        module.status(tmp_path)
    (tmp_path / 'CLOCK_CONTRACT.json').write_text('{"changed":true}')
    with pytest.raises(ValueError, match='CONTRACT_CHANGED'):
        module.status(tmp_path)


def test_verified_clock_requires_full_reviewed_scope(tmp_path):
    import json
    from publish_native_fx_quality import file_sha
    (tmp_path / 'CLOCK_CONTRACT.json').write_text('{}')
    report = dict(schema='financial_data.histdata_observed_normalization.v1', admitted=False,
                  state='CLOCK_CORRECTED_COMPLETE_HOUR_CANDIDATES', clock_verified=True,
                  binding={'config_sha256': file_sha(tmp_path / 'CLOCK_CONTRACT.json')},
                  files=[], witnesses=[])
    (tmp_path / 'STATUS.json').write_text(json.dumps(report))
    with pytest.raises(ValueError, match='COHORT_INCOMPLETE'):
        module.status(tmp_path)
