import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    'clock_normalization', Path(__file__).parents[1] / '_scripts/normalize_forexite_clock.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_provider_clock_uses_seasonal_offset_without_assuming_minute_availability():
    frame = pd.DataFrame({'timestamp_native': pd.to_datetime([
        '2023-01-03 12:00', '2023-07-03 12:00', '2023-10-27 12:00', '2023-10-30 12:00']),
        'CLOSE': [1.1, 1.2, 1.3, 1.4]})
    before = frame.copy(deep=True)
    result = module.normalize(frame)
    assert list(result.timestamp_utc_label.dt.hour) == [11, 10, 10, 11]
    assert 'available_at' not in result
    pd.testing.assert_frame_equal(frame, before)
    assert result.CLOSE.tolist() == frame.CLOSE.tolist()


@pytest.mark.parametrize('stamp', ['2023-03-26 02:30', '2023-10-29 02:30', None])
def test_invalid_or_ambiguous_local_clock_is_never_dropped_or_guessed(stamp):
    with pytest.raises(ValueError):
        module.normalize(pd.DataFrame({'timestamp_native': [stamp], 'CLOSE': [1.1]}))


def test_aware_input_cannot_be_shifted_twice():
    with pytest.raises(ValueError, match='NATIVE_CLOCK_ALREADY_AWARE'):
        module.normalize(pd.DataFrame({'timestamp_native': pd.to_datetime(['2023-01-03T12:00Z'])}))


def test_wrong_source_bytes_cannot_authorize_clock(tmp_path):
    contract = {'schema': 'financial_data.forexite_metastock_clock.v1',
                'timezone': 'Europe/Berlin', 'source_sha256': '0' * 64}
    source = tmp_path / 'source.html'
    source.write_text('unrelated source')
    with pytest.raises(ValueError, match='SOURCE_EVIDENCE_MISMATCH'):
        module.verify_contract(contract, source)
