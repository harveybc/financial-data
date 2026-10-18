import importlib.util
from pathlib import Path

import pandas as pd
import pytest


spec = importlib.util.spec_from_file_location(
    'native_comparison', Path(__file__).parents[1] / '_scripts/compare_native_fx_sources.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def minutes(start='2023-07-03 12:01', n=60):
    return pd.DataFrame({'timestamp_native': pd.date_range(start, periods=n, freq='min'),
                         'TICKER': 'EURUSD', 'CLOSE': 1.1})


def primary():
    return pd.DataFrame({'available_at': pd.to_datetime(['2023-07-03 11:00'], utc=True),
                         'BidClose': [1.10002]})


def test_endpoints_convert_without_losing_last_minute_or_looking_ahead():
    bars, diagnostics = module.complete_hour_closes(minutes(), 'FIXED_UTC_PLUS_120')
    assert len(bars) == 1
    assert bars.available_at.iloc[0] == pd.Timestamp('2023-07-03 11:00Z')
    assert bars.CLOSE.iloc[0] == 1.1
    assert diagnostics['complete_hours'] == 1


def test_missing_minute_does_not_become_a_completed_hour():
    bars, diagnostics = module.complete_hour_closes(minutes().drop(index=28), 'FIXED_UTC_PLUS_120')
    assert bars.empty and diagnostics['incomplete_hours'] == 1


def test_duplicate_or_conflicting_minutes_rejected():
    frame = minutes()
    with pytest.raises(ValueError, match='DUPLICATE_MINUTES'):
        module.complete_hour_closes(pd.concat([frame, frame.iloc[:1]]), 'FIXED_UTC_PLUS_120')


def test_unknown_clock_and_aware_native_values_rejected():
    with pytest.raises(ValueError, match='UNKNOWN_CLOCK'):
        module.complete_hour_closes(minutes(), 'GUESS')
    frame = minutes()
    frame['timestamp_native'] = frame.timestamp_native.dt.tz_localize('UTC')
    with pytest.raises(ValueError, match='NATIVE_CLOCK_ALREADY_AWARE'):
        module.complete_hour_closes(frame, 'FIXED_UTC_PLUS_120')


def test_dst_ambiguous_hour_is_counted_not_guessed():
    _, diagnostics = module.complete_hour_closes(minutes('2023-10-29 02:01'), 'EUROPE_BERLIN')
    assert diagnostics['unresolved_dst_minutes'] == 59


def test_price_comparison_uses_matching_availability_and_original_values():
    bars, _ = module.complete_hour_closes(minutes(), 'FIXED_UTC_PLUS_120')
    result = module.compare(primary(), bars)
    assert result['paired_hours'] == 1
    assert result['median_absolute_quote_difference'] == pytest.approx(.00002)
    assert result['rounded_4dp_agreement'] == 1
    assert module.compare(primary(), bars.assign(available_at=bars.available_at + pd.Timedelta(hours=1)))['paired_hours'] == 0


def test_nonfinite_invalid_and_subminute_values_rejected():
    for value in [float('nan'), float('inf'), 0, -1]:
        frame = minutes()
        frame.loc[0, 'CLOSE'] = value
        with pytest.raises(ValueError, match='INVALID_PRICE'):
            module.complete_hour_closes(frame, 'FIXED_UTC_PLUS_120')
    frame = minutes('2023-07-03 12:01:30')
    with pytest.raises(ValueError, match='NOT_MINUTE_ENDPOINTS'):
        module.complete_hour_closes(frame, 'FIXED_UTC_PLUS_120')


def test_empty_overlap_not_fictitious_zero_error():
    result = module.compare(primary(), pd.DataFrame({'available_at': pd.to_datetime([], utc=True), 'CLOSE': []}))
    assert result['paired_hours'] == 0
    assert result['median_absolute_quote_difference'] is None


def fixtures(tmp_path):
    raw, reference = tmp_path/'raw', tmp_path/'reference'
    raw.mkdir()
    pd.concat([minutes(), minutes().assign(TICKER='GBPUSD')]).to_parquet(raw/'030723.parquet', index=False)
    for pair in ('eurusd', 'gbpusd'):
        folder=reference/'2023'/pair
        folder.mkdir(parents=True)
        primary().to_parquet(folder/'2023-1h.parquet', index=False)
    return raw, reference


def test_real_parquet_path_records_identities_without_mutation_or_admission(tmp_path):
    raw, reference = fixtures(tmp_path)
    source = raw/'030723.parquet'
    before = source.read_bytes()
    result = module.run(reference, raw)
    assert source.read_bytes() == before
    assert result['admitted'] is False and result['automatic_clock_selection'] is False
    assert len(result['files']) == 3 and len(result['code_sha256']) == 64
    assert all('/tmp/' not in row['relative_path'] for row in result['files'])


def test_source_changed_during_read_is_rejected(tmp_path, monkeypatch):
    raw, reference = fixtures(tmp_path)
    original = module.pd.read_parquet
    def changed(path, *args, **kwargs):
        frame = original(path, *args, **kwargs)
        if Path(path).parent == raw:
            Path(path).write_bytes(b'changed during read')
        return frame
    monkeypatch.setattr(module.pd, 'read_parquet', changed)
    with pytest.raises(ValueError, match='SOURCE_CHANGED_DURING_DIAGNOSTIC'):
        module.run(reference, raw)

