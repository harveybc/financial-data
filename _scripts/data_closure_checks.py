"""Pure data-closure checks (order 2026-10-18 D.6). No provider access, no admission, no deletion.

Every function reports; none repairs. A flag is evidence for a human/calendar decision."""
import numpy as np
import pandas as pd

HOUR = pd.Timedelta(hours=1)


def finite_fraction(values):
    values = np.asarray(values, float)
    return float(np.isfinite(values).mean()) if values.size else 0.0


def monthly_coverage(timestamps, start, end_exclusive, expected=None):
    """Every month of [start, end) is listed, including months with zero rows."""
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True))
    months = pd.period_range(pd.Timestamp(start, tz='UTC'), pd.Timestamp(end_exclusive, tz='UTC') - pd.Timedelta(seconds=1), freq='M')
    observed = ts.to_period('M').value_counts() if len(ts) else pd.Series(dtype=int)
    exp = pd.DatetimeIndex(expected).to_period('M').value_counts() if expected is not None else None
    out = []
    for month in months:
        rows = int(observed.get(month, 0))
        record = {'month': str(month), 'observed_rows': rows,
                  'status': 'MONTH_ABSENT' if rows == 0 else 'ROWS_PRESENT_NOT_VERIFIED'}
        if exp is not None:
            record['expected_rows'] = int(exp.get(month, 0))
        out.append(record)
    return out


def required_files_status(relative_paths, root):
    root = pd.io.common.os.fspath(root)
    import os
    missing = [p for p in relative_paths if not os.path.isfile(os.path.join(root, p))]
    return {'denominator': len(relative_paths), 'present': len(relative_paths) - len(missing), 'missing': missing}


def duplicate_report(frame, key='timestamp', strict=False):
    dup = frame[frame[key].duplicated(keep=False)]
    conflicting = 0
    if not dup.empty:
        conflicting = int((dup.groupby(key).nunique(dropna=False) > 1).any(axis=1).sum())
    if strict and conflicting:
        raise ValueError('CONFLICTING_DUPLICATE')
    return {'identical': int(frame[key].duplicated().sum()) - conflicting, 'conflicting': conflicting}


def ohlc_report(frame, side):
    o, h, l, c = (frame[side + k].to_numpy(float) for k in ('Open', 'High', 'Low', 'Close'))
    values = np.stack([o, h, l, c], axis=1)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError('INVALID_PRICE')
    bad = (h < np.maximum.reduce([o, l, c])) | (l > np.minimum.reduce([o, h, c]))
    if bad.any():
        raise ValueError(f'INVALID_OHLC:{int(bad.sum())}')
    return {'invalid_rows': 0}


def return_flags(frame, train_end, side='Bid', threshold=3.5):
    """Modified z-score of one-hour log returns, TRAIN-only reference; flags only, never removal."""
    data = frame.sort_values('timestamp').reset_index(drop=True)
    ts = pd.to_datetime(data.timestamp, utc=True)
    r = np.log(data[side + 'Close']).diff().where(ts.diff().eq(HOUR))
    train = r[ts < pd.Timestamp(train_end, tz='UTC')].dropna()
    median = float(train.median()) if len(train) else None
    mad = float((train - median).abs().median()) if len(train) else None
    out = {'reference': {'n': int(len(train)), 'median': median, 'mad': mad}, 'retained_rows': data.index.tolist(), 'count': None}
    if not mad:
        out['state'] = 'NOT_ESTIMABLE'
        return out
    flagged = (.6744897501960817 * (r - median).abs() / mad) > threshold
    out.update(state='FLAGGED_NOT_REMOVED', count=int(flagged.sum()), flagged_timestamps=[t.isoformat() for t in ts[flagged.fillna(False)]])
    return out


def consumable(event_time, available_at, t):
    if available_at < event_time:
        raise ValueError('AVAILABILITY_BEFORE_EVENT')
    return bool(available_at <= t)


def elapsed_steps(timestamps):
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True)).sort_values()
    delta = pd.Series(ts).diff().dropna()
    hours = delta / HOUR
    return {'rows': int(len(ts)), 'max_elapsed_hours': float(hours.max()) if len(hours) else None,
            'steps_over_one_hour': int((hours > 1).sum()),
            'one_hour_returns_defined': int((hours == 1).sum())}
