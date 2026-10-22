"""Crosses recovery gates: injected fetcher (no network), lake-clock corroboration with negative controls,
exact-hour returns, listed missing hours, TEST exclusion, no admission."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('recover_independent_hf_crosses', SCRIPTS / 'recover_independent_hf_crosses.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)
REV = '4e694887c7f63d7e2c15a66aeebc4f45450cb381'


def business_hours(start, end):
    grid = pd.date_range(start, end, freq='h', tz='UTC', inclusive='left')
    ny = grid.tz_convert('America/New_York')
    return grid[(ny.dayofweek < 4) | ((ny.dayofweek == 4) & (ny.hour < 17)) | ((ny.dayofweek == 6) & (ny.hour >= 17))]


def walk(index, seed=0, level=1.1, scale=5e-4):
    rng = np.random.default_rng(seed)
    close = level * np.exp(rng.normal(0, scale, len(index)).cumsum())
    opn = np.roll(close, 1)
    return pd.DataFrame({'open': opn, 'high': np.maximum(opn, close) * 1.0004, 'low': np.minimum(opn, close) * 0.9996,
                         'close': close}, index=index)


def producer_frame(utc_index, prices, cadence='h'):
    """Producer schema (Time UTC bar open, OHLC, Volume, timestamp_ms)."""
    return pd.DataFrame({'Time': utc_index, 'Open': prices['open'].to_numpy(), 'High': prices['high'].to_numpy(),
                         'Low': prices['low'].to_numpy(), 'Close': prices['close'].to_numpy(), 'Volume': 10,
                         'timestamp_ms': utc_index.asi8 // 1_000_000})


def to_lake_label(utc_index):
    """Inverse of the lake rule: UTC bar start -> Europe/London wall - 5 h, stamped as if UTC."""
    london = utc_index.tz_convert('Europe/London').tz_localize(None)
    return (london - pd.Timedelta(hours=5)).tz_localize('UTC')


def h1_from_m30(m30):
    g = m30.groupby(m30.index.floor('h'))
    return g.agg(open=('open', 'first'), high=('high', 'max'), low=('low', 'min'), close=('close', 'last'))


def parquet_bytes(frame):
    buf = io.BytesIO()
    frame.to_parquet(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def world(tmp_path):
    """Two pairs, 2020-01-06..2020-07-01 business hours, one hour missing from the producer, 2025 rows in the raw,
    a lake witness on the lake clock, an admitted core equal to the producer for eurusd."""
    hours = business_hours('2020-01-06', '2020-07-01')
    files, lake_root = {}, tmp_path / 'lake'
    truth = {}
    for i, pair in enumerate(['eurusd', 'usdjpy']):
        m30_idx = pd.DatetimeIndex(sorted(list(hours) + list(hours + pd.Timedelta(minutes=30))))
        m30 = walk(m30_idx, seed=i, level=1.1 if pair == 'eurusd' else 110.0)
        h1 = h1_from_m30(m30)
        truth[pair] = h1
        h1_src = h1.drop(index=pd.Timestamp('2020-03-10 10:00', tz='UTC'))          # one producer hour absent
        extra = pd.date_range('2025-01-06', periods=5, freq='h', tz='UTC')            # TEST rows in the raw
        h1_src = pd.concat([h1_src, walk(extra, seed=9)])
        up = pair.upper()
        files[f'{up}_H1.parquet'] = parquet_bytes(producer_frame(pd.DatetimeIndex(h1_src.index), h1_src))
        files[f'{up}_M30.parquet'] = parquet_bytes(producer_frame(pd.DatetimeIndex(m30.index), m30))
        d = lake_root / 'market_data' / 'forex' / 'g10' / pair
        d.mkdir(parents=True)
        lake = h1.reset_index(names='datetime')
        lake['datetime'] = to_lake_label(pd.DatetimeIndex(lake['datetime']))
        lake.to_parquet(d / '1h.parquet', index=False)
    adm = truth['eurusd'].rename(columns={'open': 'BidOpen', 'high': 'BidHigh', 'low': 'BidLow', 'close': 'BidClose'})
    adm = adm.reset_index(names='timestamp')
    adm['available_at'] = adm.timestamp + pd.Timedelta(hours=1)
    adm.to_parquet(tmp_path / 'admitted.parquet', index=False)
    calendar = {'schema': 'financial_data.fx_business_calendar.v1', 'calendar_id': 'fixture',
                'closed_intervals': [{'start': '2020-01-01T00:00:00Z', 'end': '2020-01-02T00:00:00Z'}]}
    (tmp_path / 'calendar.json').write_text(json.dumps(calendar))
    (tmp_path / 'native.json').write_text(json.dumps({'pairs': ['eurusd'], 'required_start': '2020-01-01T00:00:00Z',
                                                      'required_end_exclusive': '2026-01-01T00:00:00Z'}))
    return dict(tmp=tmp_path, files=files, lake_root=lake_root, truth=truth, hours=hours)


class Fetcher:
    def __init__(self, files):
        self.files, self.calls = files, []

    def __call__(self, url, path, limit=m.LIMIT):
        self.calls.append(url)
        assert url.startswith(f'{m.BASE}/{REV}/') and 'token' not in url
        name = url.rsplit('/', 1)[1]
        data = self.files[name]
        path.write_bytes(data)
        return dict(url=url, file=name, state='DOWNLOADED', bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                    digest_scope='complete_original_file', headers={'x-repo-commit': REV})


def test_end_to_end_with_injected_fetcher_no_network(world):
    root = world['tmp'] / 'out'
    fetch = Fetcher(world['files'])
    status = m.run(root, fetch, REV, ['eurusd', 'usdjpy'], world['lake_root'], world['tmp'] / 'calendar.json',
                   world['tmp'] / 'native.json', core_root=None, admitted_path=world['tmp'] / 'admitted.parquet')
    assert len(fetch.calls) == 4 and len(set(fetch.calls)) == 4                      # one GET per file, no retry
    assert status['admitted'] is False and status['admitted_to_lake'] is False
    for pair in ('eurusd', 'usdjpy'):
        r = status['pairs'][pair]
        assert r['state'] == 'RECOVERED_NOT_ADMITTED', r
        assert r['m30_lineage']['ohlc_mismatch_hours'] == 0
        assert r['clock']['passed'] and r['clock']['selected_offset_hours'] == 0
        out = pd.read_parquet(root / f'{pair}.parquet')
        assert list(out.columns) == ['timestamp', 'open', 'high', 'low', 'close', 'm30_exact', 'source']
        assert (out.timestamp < pd.Timestamp('2025-01-01', tz='UTC')).all()         # TEST rows excluded
        assert out.source.eq(f'independent-hf:{REV}').all()
        assert out.m30_exact.all()
        assert pd.Timestamp('2020-03-10 10:00', tz='UTC') not in set(out.timestamp)  # never invented
    assert status['pairs']['eurusd']['admitted_core']['identical_rows'] == status['pairs']['eurusd']['admitted_core']['common_support_hours']
    missing = pd.read_csv(root / 'MISSING_HOURS.csv')
    inside = missing[(missing.missing_timestamp_utc >= '2020-01-06') & (missing.missing_timestamp_utc < '2020-07-01')]
    assert sorted(inside.missing_timestamp_utc.unique()) == ['2020-03-10T10:00:00+00:00']   # listed, never filled
    assert (missing.missing_timestamp_utc >= '2020-01-02').all()                           # calendar blackout excluded
    cov = pd.read_csv(root / 'COVERAGE.csv')
    march = cov[(cov.pair == 'usdjpy') & (cov.month == '2020-03')].iloc[0]
    assert march.missing_hours == 1 and march.required_hours == march.observed_hours + 1
    assert set(cov.month) == set(m.MONTHS)
    clock = json.loads((root / 'CLOCK.json').read_text())
    for pair in ('eurusd', 'usdjpy'):
        scores = {s['offset_hours']: s for s in clock['pairs'][pair]['exact_hour_return_offsets']}
        assert scores[0]['return_corr'] > 0.999
        assert all(scores[k]['return_corr'] < 0.3 for k in scores if k)
        pips = {s['offset_hours']: s for s in clock['pairs'][pair]['ohlc_pip_offsets']}
        assert pips[0]['ohlc_median_abs_diff_pips'] == pytest.approx(0)
        assert all(pips[k]['ohlc_median_abs_diff_pips'] > 2 for k in pips if k)      # pip-scaled also for JPY
    assert clock['all_corroborated_pairs_selected_offset_0'] is True
    # the raw files keep their 2025 rows untouched
    raw = pd.read_parquet(root / 'EURUSD_H1.parquet')
    assert (raw.Time >= pd.Timestamp('2025-01-01', tz='UTC')).sum() == 5


def test_lake_clock_shifted_witness_fails_the_gate_and_names_the_offset(world):
    """A witness whose labels are one hour late must select offset +1 in the scores and fail at offset 0."""
    h1 = world['truth']['usdjpy']
    lake = h1.copy()
    lake.index = lake.index + pd.Timedelta(hours=1)
    cand = h1.copy()
    verdict, _, _ = m.clock_against_lake('usdjpy', cand, lake)
    assert verdict['passed'] is False
    assert verdict['exact_hour_return_rule']['best_offset_hours'] == 1
    assert 'DECLARED_UTC_CLOCK_NOT_CORROBORATED' in verdict['ohlc_pip_rule']['reasons']


def test_relocalize_lake_matches_feature_eng_rule():
    lab = pd.to_datetime(['2024-01-15 07:00', '2024-07-15 07:00', '2024-03-12 07:00']).tz_localize('UTC')
    out = m.relocalize_lake(pd.DataFrame({'datetime': lab, 'close': [1.0, 1.1, 1.2]}))
    assert list(out.index.strftime('%Y-%m-%d %H:%M')) == ['2024-01-15 12:00', '2024-03-12 12:00', '2024-07-15 11:00']


def test_exact_hour_returns_never_span_a_missing_interval():
    idx = pd.DatetimeIndex(['2024-01-02 00:00', '2024-01-02 01:00', '2024-01-02 03:00', '2024-01-02 04:00'], tz='UTC')
    r = m.exact_hour_returns(pd.Series([1.0, 1.01, 1.03, 1.04], index=idx))
    assert np.isnan(r.iloc[0]) and np.isnan(r.iloc[2])
    assert r.iloc[1] == pytest.approx(np.log(1.01)) and r.iloc[3] == pytest.approx(np.log(1.04 / 1.03))


def test_return_rule_requires_support_and_margin():
    def scores(c0, ctrl):
        return [dict(offset_hours=k, joint_exact_hour_returns=3000, return_corr=c0 if k == 0 else ctrl) for k in m.OFFSETS]
    empty = pd.DataFrame(columns=['month', 'offset_hours', 'joint_exact_hour_returns', 'return_corr'])
    assert m.return_rule(scores(0.99, 0.1), empty)['passed']
    assert m.return_rule(scores(0.99, 0.6), empty)['reasons'] == [f'CONTROL_{k:+d}H_WITHIN_MARGIN' for k in m.OFFSETS if k]
    assert m.return_rule(scores(0.9, 0.0), empty)['reasons'] == ['OFFSET0_CORRELATION_BELOW_MINIMUM']
    short = scores(0.99, 0.0)
    short[3]['joint_exact_hour_returns'] = 10
    assert m.return_rule(short, empty)['reasons'] == ['INSUFFICIENT_JOINT_RETURNS']


def test_coverage_lists_every_missing_required_hour_and_counts_outside_calendar():
    expected = pd.DatetimeIndex(['2023-07-03 10:00', '2023-07-03 11:00', '2023-07-03 12:00'], tz='UTC')
    observed = pd.DatetimeIndex(['2023-07-03 10:00', '2023-07-03 12:00', '2023-07-01 12:00', '2025-02-03 10:00'], tz='UTC')
    cov, missing, outside = m.coverage(observed, expected)
    july = cov[cov.month == '2023-07'].iloc[0]
    assert july.required_hours == 3 and july.observed_hours == 2 and july.missing_hours == 1
    assert list(missing) == [pd.Timestamp('2023-07-03 11:00', tz='UTC')]
    assert list(outside) == [pd.Timestamp('2023-07-01 12:00', tz='UTC')]              # 2025 row ignored


def test_half_year_summary_denominators():
    cov = pd.DataFrame({'month': m.MONTHS, 'required_hours': 100, 'missing_hours': [1 if mo.startswith('2023-0') and int(mo[5:]) <= 6 else 0 for mo in m.MONTHS]})
    s = m.half_year_summary(cov)
    assert s['2023H1'] == dict(required_hours=600, missing_hours=6, coverage=pytest.approx(0.99))
    assert s['2023H2']['missing_hours'] == 0 and s['2024']['required_hours'] == 1200


def test_fetcher_never_retries_a_retained_partial(tmp_path):
    class Session:
        calls = 0

        def get(self, *a, **kw):
            self.calls += 1
            raise AssertionError('network must not be used')
    (tmp_path / 'X_H1.parquet.partial').write_bytes(b'prefix')
    fetch = m.make_fetcher(Session(), resume_local=False)
    entry = fetch('https://huggingface.co/pinned', tmp_path / 'X_H1.parquet')
    assert entry['state'] == 'PARTIAL_RETAINED_NO_RETRY' and Session.calls == 0


def test_reuse_pinned_core_bytes_requires_same_revision_and_digest(tmp_path):
    core = tmp_path / 'core'
    core.mkdir()
    (core / 'EURUSD_H1.parquet').write_bytes(b'bytes')
    digest = hashlib.sha256(b'bytes').hexdigest()
    report = {'revision_sha': REV, 'downloads': [{'file': 'EURUSD_H1.parquet', 'state': 'DOWNLOADED', 'sha256': digest, 'url': 'u'}]}
    (core / 'report.json').write_text(json.dumps(report))
    entry = m.reuse_pinned(core, 'EURUSD_H1.parquet', tmp_path / 'EURUSD_H1.parquet', REV)
    assert entry['transport'] == 'REUSED_PINNED_CORE_BYTES_NO_NETWORK' and entry['sha256'] == digest
    assert m.reuse_pinned(core, 'EURUSD_H1.parquet', tmp_path / 'other.parquet', 'b' * 40) is None
    (core / 'EURUSD_H1.parquet').write_bytes(b'tampered')
    assert m.reuse_pinned(core, 'EURUSD_H1.parquet', tmp_path / 'again.parquet', REV) is None


def test_pair_failure_is_recorded_not_raised(world):
    root = world['tmp'] / 'out2'

    def failing(url, path, limit=m.LIMIT):
        return dict(url=url, file=path.name, state='HTTP_FAILURE', status=404)
    status = m.run(root, failing, REV, ['usdjpy'], world['lake_root'], world['tmp'] / 'calendar.json', world['tmp'] / 'native.json')
    assert status['pairs']['usdjpy']['state'] == 'PAIR_FAILED' and status['pairs']['usdjpy']['error'] == 'H1_HTTP_FAILURE'
    assert not (root / 'usdjpy.parquet').exists()
