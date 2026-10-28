import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location('prepare_raw_rl_input',
    Path(__file__).parents[1] / '_scripts/prepare_raw_rl_input.py')
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


def bars(times, closes=None):
    ts = pd.to_datetime(times, utc=True)
    closes = closes if closes is not None else [1.1] * len(ts)
    return pd.DataFrame(dict(timestamp=ts, available_at=ts + pd.Timedelta(hours=1),
        BidOpen=1.1, BidHigh=1.3, BidLow=1., BidClose=closes))


def test_completed_availability_drives_splits_and_excludes_2025():
    raw = bars(['2023-12-31T21:00Z', '2023-12-31T22:00Z', '2023-12-31T23:00Z',
                '2024-12-31T22:00Z', '2024-12-31T23:00Z'])
    frame = m.derive(raw)
    split = m.split_frames(frame)
    assert split['train'].DATE_TIME.tolist() == [pd.Timestamp('2023-12-31T23:00Z')]
    assert split['validation'].DATE_TIME.tolist() == [pd.Timestamp('2024-01-01T00:00Z'),
                                                     pd.Timestamp('2024-12-31T23:00Z')]
    assert all(f.DATE_TIME.max() < pd.Timestamp('2025-01-01T00:00Z') for f in split.values())


def test_weekend_return_is_not_claimed_one_hour_and_warmup_not_filled():
    frame = m.derive(bars(['2023-07-07T20:00Z', '2023-07-09T21:00Z'], [1.1, 1.2]))
    assert len(frame) == 1
    assert frame.iloc[0].RAW_ELAPSED_HOURS == 49
    assert frame.iloc[0].RAW_CLOSE_LOG_RETURN == pytest.approx(np.log(1.2 / 1.1))
    assert frame.iloc[0].RAW_BAR_LOG_RETURN == pytest.approx(np.log(1.2 / 1.1))
    assert frame.iloc[0].RAW_LOG_RANGE == pytest.approx(np.log(1.3))


def test_future_perturbation_cannot_change_prior_features_or_train():
    raw = bars(['2023-12-31T21:00Z', '2023-12-31T22:00Z', '2024-01-02T06:00Z'], [1.1, 1.15, 1.2])
    before = m.derive(raw)
    raw.loc[2, 'BidClose'] = 1.25
    after = m.derive(raw)
    pd.testing.assert_frame_equal(before.iloc[:1], after.iloc[:1])
    pd.testing.assert_frame_equal(m.split_frames(before)['train'], m.split_frames(after)['train'])


@pytest.mark.parametrize('mutation', ['backward', 'duplicate', 'availability', 'price'])
def test_bad_input_refuses_instead_of_sorting_filling_or_retiming(mutation):
    raw = bars(['2023-07-03T10:00Z', '2023-07-03T11:00Z'])
    if mutation == 'backward':
        raw = raw.iloc[::-1]
    elif mutation == 'duplicate':
        raw.iloc[1] = raw.iloc[0]
    elif mutation == 'availability':
        raw.loc[1, 'available_at'] = raw.loc[1, 'timestamp']
    else:
        raw.loc[1, 'BidClose'] = float('nan')
    with pytest.raises(ValueError):
        m.derive(raw)


def test_csv_exact_float_roundtrip_timestamp_hash_and_real_validator(tmp_path):
    validator = Path('/var/tmp/agent-multi-rl-static-20261018/app/curated_rl_input.py')
    if not validator.exists():
        pytest.skip('external validator checkout absent')
    frame = m.derive(bars(['2023-07-03T10:00Z', '2023-07-03T11:00Z'], [1.1, 1.1234567890123457]))
    pins = dict(selection_sha256='a' * 64, calendar_sha256='b' * 64, inventory_sha256='c' * 64)
    manifest, config = m.write_split(tmp_path, 'train', frame, pins, {'schema': 'test_fixture_only'})
    with (tmp_path / 'train.csv').open(newline='') as stream:
        row = next(csv.DictReader(stream))
    assert float(row['CLOSE']) == frame.iloc[0].CLOSE
    result = m.load_validator(validator).validate_curated_rl_input(config)
    assert result['row_count'] == 1
    assert len(manifest['expected_timestamps_sha256']) == 64
    assert manifest['feature_selection_complete'] is False
    assert manifest['selection_semantics'] == 'RAW_BASELINE_INPUT_POLICY_NOT_FINAL_SELECTION'
    assert float(row['ASSUMED_SPREAD']) == 0.00010
    assert 'ASSUMED_SPREAD' not in manifest['feature_columns']
    assert manifest['assumed_spread_policy']['observed'] is False
    assert manifest['assumed_spread_policy']['validation_tuned'] is False
    assert manifest['assumed_spread_policy']['provenance'] == 'ASSUMED_FIXED_SPREAD_1_PIP_NOT_BROKER_VERIFIED'
    assert config['session_spread_column'] == 'ASSUMED_SPREAD'
    assert not any('ASK' in column for column in row)
    (tmp_path / 'train.csv').write_text((tmp_path / 'train.csv').read_text().replace('1.3', '1.4'))
    with pytest.raises(ValueError, match='INPUT_DIGEST'):
        m.load_validator(validator).validate_curated_rl_input(config)


def test_calendar_includes_only_declared_exclusions_and_ny_weekly_hours():
    calendar = dict(coverage_start='2023-07-07T19:00Z', coverage_end_exclusive='2023-07-10T01:00Z',
                    timezone='America/New_York', weekly_open_day=6, weekly_open_hour=17,
                    weekly_close_day=4, weekly_close_hour=17,
                    closed_intervals=[dict(start='2023-07-09T21:00Z', end='2023-07-09T23:00Z')])
    expected = m.calendar_hours(calendar)
    assert pd.Timestamp('2023-07-07T20:00Z') in expected
    assert pd.Timestamp('2023-07-07T21:00Z') not in expected
    assert pd.Timestamp('2023-07-09T21:00Z') not in expected
    assert pd.Timestamp('2023-07-09T23:00Z') in expected


def test_frozen_policy_is_raw_baseline_not_final_selection():
    assert m.POLICY['scope'] == 'RAW_BASELINE'
    assert m.POLICY['feature_selection_complete'] is False
    assert m.POLICY['price_fill'] is False and m.POLICY['interpolation'] is False
    assert set(m.PERIODS) == {'train', 'validation'}
    spread = m.POLICY['nonfeature_columns']['ASSUMED_SPREAD']
    assert spread['constant'] == .00010 and not spread['feature']
    assert spread['usage'] == 'SESSION_STABILITY_COST_MODEL_ONLY'


def test_renderer_refuses_modified_cost_assumption(tmp_path):
    frame = m.derive(bars(['2023-07-03T10:00Z', '2023-07-03T11:00Z']))
    frame['ASSUMED_SPREAD'] = .0002
    with pytest.raises(ValueError, match='FIXED_NONFEATURE_COST_ASSUMPTION'):
        m.write_split(tmp_path, 'train', frame, {}, {})


def test_owner_admission_required_before_rendering(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'ADMISSION.json').write_text(json.dumps(dict(schema='financial_data.core_price_inventory.v1', status='PREPARING')))
    with pytest.raises(ValueError, match='OWNER_CORE_PRICE_ADMISSION_REQUIRED'):
        m.prepare(source, tmp_path / 'output', Path('/not-used'), data_commit='HEAD')
    assert not (tmp_path / 'output').exists()
