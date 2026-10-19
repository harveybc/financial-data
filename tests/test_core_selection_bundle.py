import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _scripts.core_selection_bundle import business_targets, candidate_frame, trim_warmup


def bars(n=200):
    t = pd.date_range('2020-01-01', periods=n, freq='h', tz='UTC')
    c = 1.1 + .001 * np.sin(np.arange(n) / 5)
    return pd.DataFrame(dict(DATE_TIME=t, OPEN=c, HIGH=c+.002, LOW=c-.002, CLOSE=c+.0001))


def generator(x):
    x['indicator'] = x.CLOSE.rolling(4).mean()
    return x


def test_current_bar_and_prefix_invariance():
    x = bars()
    a = candidate_frame(x, generator, ['indicator'])
    b = candidate_frame(x.iloc[:100], generator, ['indicator'])
    pd.testing.assert_frame_equal(a.iloc[:100], b)
    x.loc[100:, 'CLOSE'] *= 2
    pd.testing.assert_frame_equal(a.iloc[:100], candidate_frame(x, generator, ['indicator']).iloc[:100])
    assert a.RAW_BAR_LOG_RETURN.iloc[20] == pytest.approx(np.log(x.CLOSE.iloc[20]/x.OPEN.iloc[20]))


def test_only_leading_warmup_may_be_removed():
    f = candidate_frame(bars(), generator, ['indicator'])
    clean, removed = trim_warmup(f)
    assert removed == 3 and len(clean) == 197
    assert clean.DATE_TIME.iloc[0] == f.DATE_TIME.iloc[3]
    f.loc[20, 'indicator'] = np.nan
    with pytest.raises(ValueError, match='INTERIOR_NONFINITE'):
        trim_warmup(f)


def test_elapsed_lookup_not_observed_row_shift():
    x = bars(200)
    x = x.drop(index=range(40, 50)).reset_index(drop=True)
    y = business_targets(x, [], end='2021-01-01T00:00:00Z', cutoffs=[])
    assert np.isnan(y.RETURN_4H.iloc[38])
    assert y.RETURN_4H.iloc[10] == pytest.approx(np.log(x.CLOSE.iloc[14]/x.CLOSE.iloc[10]))


def test_business_buffers_and_target_crossing_fail_closed():
    x = bars(200)
    closure = [[str(x.DATE_TIME.iloc[80]), str(x.DATE_TIME.iloc[100])]]
    y = business_targets(x, closure, end='2021-01-01T00:00:00Z', cutoffs=[])
    assert np.isnan(y.RETURN_4H.iloc[64])  # t+h == forced flat
    assert np.isnan(y.RETURN_4H.iloc[105])  # reopen buffer
    assert np.isfinite(y.RETURN_4H.iloc[112])
    assert np.isnan(y.RETURN_12H.iloc[60])


def test_fold_and_train_boundaries_purged_without_touching_inputs():
    x = bars(200)
    y = business_targets(x, [], end=str(x.DATE_TIME.iloc[180]), cutoffs=[x.DATE_TIME.iloc[100]])
    assert y.RETURN_4H.iloc[96:100].isna().all()
    assert np.isfinite(y.RETURN_4H.iloc[100])
    assert y.RETURN_4H.iloc[176:].isna().all()
    assert len(x) == len(y) == 200


def test_no_nonfinite_candidate_and_no_future_keys():
    x = bars()
    x.loc[20, 'HIGH'] = np.inf
    with pytest.raises(ValueError, match='NONFINITE'):
        trim_warmup(candidate_frame(x, generator, ['indicator']))
