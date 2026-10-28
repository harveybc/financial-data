import importlib.util
import io
from pathlib import Path

import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    'recover_histdata_ticks', Path(__file__).parents[1] / '_scripts/recover_histdata_ticks.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def parse(body, chunk_size=2):
    return m.parse_ticks(io.StringIO(body), chunk_size=chunk_size)


def test_cross_chunk_hour_and_gap_and_no_empty_hour_fill():
    bars, stats = parse(
        '20230703 100000000,1.1,1.2,0\n'
        '20230703 101000000,1.3,1.4,0\n'
        '20230703 105900000,1.2,1.3,0\n'
        '20230703 120000000,1.4,1.5,0\n')
    assert stats['source_rows'] == stats['accepted_ticks'] == 4
    assert len(bars) == 2
    assert bars.iloc[0]['tick_count'] == 3
    assert bars.iloc[0]['open'] == 1.1
    assert bars.iloc[0]['high'] == 1.3
    assert bars.iloc[0]['close'] == 1.2
    assert bars.iloc[0]['max_intertick_gap_seconds'] == 2940
    assert bars.iloc[1]['gap_from_previous_hour_last_tick_seconds'] == 3660
    assert bars.iloc[0]['source_row_last'] == 3
    assert bars.iloc[1]['source_row_first'] == 4


@pytest.mark.parametrize('quote', ['bad,1.2', '1.3,1.2', '0,1.2', '1.1,nan', 'inf,inf'])
def test_bad_or_crossed_quotes_rejected_and_counted(quote):
    bars, stats = parse('20230703 100000000,' + quote + ',0\n'
                        '20230703 100100000,1.1,1.2,0\n')
    assert stats['rejected_quotes'] == 1
    assert stats['source_rows'] == 2
    assert bars.iloc[0]['tick_count'] == 1
    assert bars.iloc[0]['rejected_quote_count'] == 1


def test_all_bad_hour_is_not_a_price_bar():
    bars, stats = parse('20230703 100000000,1.3,1.2,0\n')
    assert bars.empty and stats['accepted_ticks'] == 0


def test_monotonicity_checked_across_chunks_and_rejected_quotes():
    with pytest.raises(ValueError, match='NON_MONOTONIC'):
        parse('20230703 100100000,1.1,1.2,0\n'
              '20230703 100200000,bad,1.2,0\n'
              '20230703 100000000,1.1,1.2,0\n')


def test_duplicate_timestamps_are_real_rows_not_deduplicated():
    bars, stats = parse('20230703 100000123,1.1,1.2,0\n' * 3)
    assert stats['accepted_ticks'] == 3 and bars.iloc[0]['tick_count'] == 3


def test_bad_timestamp_fails_closed():
    with pytest.raises(ValueError, match='BAD_TIMESTAMP'):
        parse('20230703 100000,1.1,1.2,0\n')


def test_candidates_have_proper_hour_availability_and_millisecond_precision():
    bars, _ = parse('20230703 100000123,1.1,1.2,0\n')
    expected = {'fixedEST': 15, 'US_Eastern': 14, 'native_plus5_London': 14}
    for clock, hour in expected.items():
        frame = m.hourly_candidate(bars, clock)
        assert frame.iloc[0]['timestamp'].hour == hour
        assert frame.iloc[0]['available_at_utc'] == frame.iloc[0]['timestamp'] + pd.Timedelta(hours=1)
        assert frame.iloc[0]['first_tick_utc'].microsecond == 123000
        assert frame.iloc[0]['available_at_utc'] > frame.iloc[0]['last_tick_utc']
        assert not frame.iloc[0]['admitted']
    with pytest.raises(ValueError, match='UNKNOWN_CLOCK'):
        m.hourly_candidate(bars, 'unknown')


def test_no_overlap_or_equivalent_candidates_cannot_assert_clock():
    empty = pd.DataFrame(columns=['timestamp', 'BidOpen', 'BidHigh', 'BidLow', 'BidClose'])
    bars, _ = parse('20230703 100000000,1.1,1.2,0\n')
    candidates = {c: m.hourly_candidate(bars, c) for c in m.CLOCKS}
    evidence, _ = m.compare_clocks(candidates, empty)
    assert evidence['clock_state'] == 'UNRESOLVED'
    assert evidence['selected_clock'] is None
    assert evidence['common_support_hours'] == 0


def test_form_token_never_in_metadata_and_action_restricted():
    html = '<form method="POST" action="/get.php">' + ''.join(
        '<input name="%s" value="%s">' % (k, v) for k, v in {
            **m.PUBLIC_FIELDS, 'tk': 'test-secret'}.items()) + '</form>'
    action, fields = m.parse_form(html)
    assert action == 'https://www.histdata.com/get.php'
    assert fields['tk'] == 'test-secret'
    with pytest.raises(ValueError, match='FORM'):
        m.parse_form(html.replace('/get.php', 'https://other.invalid/get.php'))


def test_nonzip_single_post_status_digest_and_no_secret_body(tmp_path):
    html = '<form method="POST" action="/get.php">' + ''.join(
        '<input name="%s" value="%s">' % (k, v) for k, v in {
            **m.PUBLIC_FIELDS, 'tk': 'test-secret'}.items()) + '</form>'

    class Response:
        def __init__(self, body, headers=None):
            self.body = body
            self.headers = headers or {}
            self.status_code = 200

        def iter_content(self, size):
            yield self.body

        def close(self):
            pass

    class Session:
        posts = 0

        def get(self, *a, **kw):
            return Response(html.encode())

        def post(self, *a, **kw):
            self.posts += 1
            return Response(b'not zip test-secret', {'Set-Cookie': 'secret', 'Content-Type': 'text/html'})

    session = Session()
    result = m.download_once(tmp_path, session)
    assert session.posts == 1
    assert result['state'] == 'POST_NOT_ZIP'
    assert result['post']['bytes'] == 19
    assert len(result['post']['sha256']) == 64
    assert 'test-secret' not in str(result) and 'Set-Cookie' not in str(result)
    assert not list(tmp_path.iterdir())


def test_clock_comparison_uses_identical_common_support():
    bars, _ = parse(''.join('20230703 %02d0000000,1.1,1.2,0\n' % h for h in range(10, 14)))
    candidates = {c: m.hourly_candidate(bars, c) for c in m.CLOCKS}
    fx = candidates['fixedEST'][['timestamp', 'open', 'high', 'low', 'close']].rename(
        columns=dict(zip(m.OHLC, m.FX_OHLC)))
    evidence, detail = m.compare_clocks(candidates, fx)
    assert evidence['common_support_hours'] == 3
    assert len(detail) == 9
    assert {v['hours'] for v in evidence['scores'].values()} == {3}
    assert evidence['clock_state'] == 'UNRESOLVED'


def test_sufficient_support_still_does_not_disambiguate_equivalent_clocks():
    times = pd.date_range('2023-07-03', periods=72, freq='h')
    bars, _ = parse(''.join(t.strftime('%Y%m%d %H%M%S') + '000,1.1,1.2,0\n' for t in times))
    candidates = {c: m.hourly_candidate(bars, c) for c in m.CLOCKS}
    fx = candidates['US_Eastern'][['timestamp'] + m.OHLC].rename(columns=dict(zip(m.OHLC, m.FX_OHLC)))
    evidence, _ = m.compare_clocks(candidates, fx)
    assert evidence['common_support_hours'] >= 48
    assert evidence['scores']['US_Eastern']['ohlc_mae_pips'] == 0
    assert evidence['selected_clock'] is None


def test_post_limit_retains_bounded_prefix_without_retry(tmp_path, monkeypatch):
    html = '<form method="POST" action="/get.php">' + ''.join(
        '<input name="%s" value="%s">' % (k, v) for k, v in {
            **m.PUBLIC_FIELDS, 'tk': 'test-secret'}.items()) + '</form>'

    class Response:
        status_code = 200
        headers = {}

        def __init__(self, chunks):
            self.chunks = chunks

        def iter_content(self, size):
            yield from self.chunks

        def close(self):
            pass

    class Session:
        def get(self, *a, **kw):
            return Response([html.encode()])

        def post(self, *a, **kw):
            return Response([b'PK\x03\x04abcd', b'12345678'])

    monkeypatch.setattr(m, 'MAX_ZIP', 10)
    evidence = m.download_once(tmp_path, Session())
    assert evidence['state'] == 'POST_LIMIT_EXCEEDED'
    assert evidence['post']['bytes'] == 8
    assert not evidence['post']['complete']
    assert (tmp_path / 'EURUSD_T_202307.zip').stat().st_size == 8
