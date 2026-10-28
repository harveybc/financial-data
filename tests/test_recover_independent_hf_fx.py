"""Isolated recovery gates: byte identity, explicit label hypotheses, no admission."""
import hashlib
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location(
    'recover_independent_hf_fx', Path(__file__).parents[1] / '_scripts/recover_independent_hf_fx.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def source(times, values=None):
    n = len(times)
    values = values if values is not None else [1.1] * n
    return pd.DataFrame({'Time': pd.to_datetime(times), 'Open': values, 'High': values,
                         'Low': values, 'Close': values, 'Volume': [10] * n})


def test_naive_labels_remain_hypotheses_not_timezone_assertions():
    audit, frame = m.audit_source(source(['2023-07-03 10:00', '2023-07-03 11:00']))
    assert audit['timestamp_timezone'] is None
    assert audit['comparison_time_basis'] == 'NAIVE_LABEL_AS_UTC_HYPOTHESIS_ONLY'
    assert audit['timezone_verified'] is False and audit['admitted'] is False
    assert frame.index.tz is not None


def test_actual_audit_missing_invalid_ohlc_duplicates_and_monotonicity():
    raw = source(['2023-07-03T11:00Z', '2023-07-03T10:00Z', '2023-07-03T10:00Z'])
    raw.loc[1, 'Open'] = None
    raw.loc[2, 'High'] = 0.5
    audit, frame = m.audit_source(raw)
    assert audit['monotonic_increasing'] is False
    assert audit['duplicate_timestamp_rows'] == 2
    assert audit['ohlc_missing_cells'] == 1
    assert audit['invalid_ohlc_rows'] == 2
    assert len(frame) == 1


def test_no_string_timestamp_or_implicit_epoch_guess():
    raw = source(['2023-07-03T10:00Z'])
    raw['Time'] = ['20230703 100000']
    with pytest.raises(ValueError, match='TIME_DTYPE'):
        m.audit_source(raw)


def test_all_shifts_use_common_support_and_exact_missing_targets():
    times = pd.date_range('2023-07-03', periods=24, freq='h', tz='UTC')
    _, candidate = m.audit_source(source(times, [1.1 + i * .001 for i in range(24)]))
    fxcm = candidate[m.OHLC].copy()
    # Explicitly moving candidate labels +1h exactly matches this witness.
    fxcm.index = fxcm.index + pd.Timedelta(hours=1)
    target = pd.DatetimeIndex([pd.Timestamp('2023-07-04T00:00Z'), pd.Timestamp('2023-07-05T00:00Z')])
    report, monthly, gaps = m.compare(candidate, fxcm, target)
    assert {r['common_support_hours'] for r in report['offsets']} == {18}
    assert report['timezone_verified'] is False and report['selected_offset_hours'] is None
    best = next(r for r in report['offsets'] if r['offset_hours'] == 1)
    assert best['ohlc_median_abs_diff_pips'] == pytest.approx(0)
    assert best['missing_v2_hours_covered'] == 1
    assert len(gaps) == 7 * 2
    assert len(monthly) == 7 * 72
    assert not gaps['admitted'].any()
    assert report['admitted'] is False


def test_missing_denominator_requires_explicit_lists_and_consistent_count():
    q = {'missing_expected_open_hours': 1, 'months': [{'missing_expected_open_hours': 1,
         'missing_timestamps': ['2023-07-03T00:00:00+00:00']}]}
    assert len(m.missing_targets(q)) == 1
    q['missing_expected_open_hours'] = 2
    with pytest.raises(ValueError, match='MISSING_DENOMINATOR'):
        m.missing_targets(q)


def test_revision_must_be_full_sha():
    assert m.validate_revision('4e694887c7f63d7e2c15a66aeebc4f45450cb381')
    for value in ['main', '', '../main', 'a' * 39]:
        with pytest.raises(ValueError, match='REVISION'):
            m.validate_revision(value)


class Response:
    status_code = 200
    headers = {'Set-Cookie': 'secret', 'Content-Type': 'application/octet-stream'}
    history = []

    def __init__(self, chunks):
        self.chunks = chunks

    def iter_content(self, size):
        yield from self.chunks

    def close(self):
        pass


def test_bounded_download_original_bytes_digest_and_no_redirect_secret(tmp_path):
    class Session:
        def get(self, url, **kw):
            assert kw['allow_redirects'] is True
            return Response([b'PAR1', b'original bytes'])

    entry = m.download(Session(), 'https://huggingface.co/pinned', tmp_path / 'raw.parquet', 32)
    assert entry['state'] == 'DOWNLOADED'
    assert (tmp_path / 'raw.parquet').read_bytes() == b'PAR1original bytes'
    assert entry['sha256'] == hashlib.sha256(b'PAR1original bytes').hexdigest()
    assert 'secret' not in str(entry)


def test_download_hard_byte_cap_no_retry(tmp_path):
    class Session:
        calls = 0

        def get(self, *a, **kw):
            self.calls += 1
            return Response([b'12345678', b'abcdefgh'])

    session = Session()
    entry = m.download(session, 'https://huggingface.co/pinned', tmp_path / 'raw.parquet', 10)
    assert entry['state'] == 'BYTE_LIMIT_EXCEEDED'
    assert entry['bytes'] == 8 and session.calls == 1
    assert not (tmp_path / 'raw.parquet').exists()
    assert (tmp_path / 'raw.parquet.partial').stat().st_size <= 10


def test_no_overlap_remains_unresolved():
    _, candidate = m.audit_source(source(['2023-07-03T00:00Z']))
    witness = candidate[m.OHLC].copy()
    witness.index += pd.Timedelta(days=10)
    report, _, _ = m.compare(candidate, witness, pd.DatetimeIndex([], tz='UTC'))
    assert all(r['common_support_hours'] == 0 for r in report['offsets'])
    assert report['selected_offset_hours'] is None


def test_m30_lineage_exact_two_rows_and_all_ohlc_aggregation():
    raw = source(['2023-07-03T10:00Z', '2023-07-03T10:30Z'], [1.1, 1.2])
    h1 = source(['2023-07-03T10:00Z'])
    h1.loc[0, ['High', 'Close']] = [1.2, 1.2]
    _, h1frame = m.audit_source(h1)
    summary, detail = m.verify_m30(h1frame, raw)
    assert summary['h1_rows_exactly_verified'] == 1
    assert detail.iloc[0]['exact_two_aligned_native_rows']
    raw.loc[1, 'Close'] += 1e-7
    raw.loc[1, 'High'] += 1e-7
    summary, _ = m.verify_m30(h1frame, raw)
    assert summary['ohlc_mismatch_hours'] == 1


def test_m30_missing_duplicate_or_misaligned_row_never_certifies_hour():
    _, h1frame = m.audit_source(source(['2023-07-03T10:00Z']))
    variants = [source(['2023-07-03T10:00Z']),
                source(['2023-07-03T10:00Z', '2023-07-03T10:00Z']),
                source(['2023-07-03T10:00Z', '2023-07-03T10:15Z'])]
    for raw in variants:
        summary, _ = m.verify_m30(h1frame, raw)
        assert summary['h1_rows_exactly_verified'] == 0
        assert summary['incomplete_or_misaligned_hours'] == 1


def test_m30_tolerance_and_zero_volume_audit():
    raw = source(['2023-07-03T10:00Z', '2023-07-03T10:30Z'])
    raw['Volume'] = 0
    _, h1frame = m.audit_source(source(['2023-07-03T10:00Z']))
    raw.loc[1, ['High', 'Close']] += 1e-13
    summary, _ = m.verify_m30(h1frame, raw)
    assert summary['h1_rows_exactly_verified'] == 1
    assert summary['m30_audit']['zero_volume_rows'] == 2
