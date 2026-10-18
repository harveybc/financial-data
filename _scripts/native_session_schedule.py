"""Observed session schedule of the native FXCM H1 feed and typed classification of missing runs.

Separates SOURCE_FILE_ABSENT (the weekly source file failed), CALENDAR_RESOLUTION_CANDIDATE
(in-file absence on a date commonly associated with a holiday; NOT a verified closure) and
MISSING_QUOTE_OPEN_SESSION (in-file absence inside an ordinary open session). Nothing is
auto-closed, filled or admitted."""
import argparse
import json
import os
from pathlib import Path

import pandas as pd

NY = 'America/New_York'
#: Dates commonly associated with reduced FX liquidity/closures. Candidates for calendar
#: resolution only; the provider's holiday schedule for 2020-2025 is UNSTATED (see return).
HOLIDAY_CANDIDATE_MMDD = {'12-24', '12-25', '12-26', '12-31', '01-01', '01-02', '07-04', '07-03', '11-11'}


def weekly_schedule(timestamps):
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True)).sort_values()
    local = ts.tz_convert(NY)
    # a trading week starts at the first bar after the Friday 17:00 NY close
    week_key = (local - pd.Timedelta(hours=17)).to_period('W-FRI')
    out = []
    for key, idx in pd.Series(range(len(ts)), index=week_key).groupby(level=0):
        first, last = ts[idx.iloc[0]], ts[idx.iloc[-1]]
        out.append({'week': str(key), 'bars': int(len(idx)),
                    'first_bar_utc': first.isoformat(), 'last_bar_utc': last.isoformat(),
                    'first_bar_ny_local': first.tz_convert(NY).isoformat(),
                    'last_bar_ny_local': last.tz_convert(NY).isoformat(),
                    'first_bar_ny_weekday_hour': f'{first.tz_convert(NY).day_name()} {first.tz_convert(NY).hour:02d}',
                    'last_bar_ny_weekday_hour': f'{last.tz_convert(NY).day_name()} {last.tz_convert(NY).hour:02d}'})
    return out


def classify_runs(pair, runs, failed_weeks):
    out = []
    for run in runs:
        start = pd.Timestamp(run['start'])
        end = pd.Timestamp(run['end'])
        iso = start.isocalendar()
        covered_failed = {w for (p, y, w) in failed_weeks if p == pair and y == start.year}
        dates = {d.strftime('%m-%d') for d in pd.date_range(start.floor('D'), end.floor('D'), freq='D')}
        if run['hours'] >= 100 or iso.week in covered_failed or (start.year, iso.week) in {(y, w) for (p, y, w) in failed_weeks if p == pair}:
            klass = 'SOURCE_FILE_ABSENT' if (iso.week in covered_failed or run['hours'] >= 100) else 'MISSING_QUOTE_OPEN_SESSION'
        elif dates & HOLIDAY_CANDIDATE_MMDD:
            klass = 'CALENDAR_RESOLUTION_CANDIDATE'
        else:
            klass = 'MISSING_QUOTE_OPEN_SESSION'
        out.append({**run, 'pair': pair, 'iso_week': int(iso.week), 'class': klass, 'closure_verified': False})
    return out


def run(primary_root, quality_dir):
    primary_root, quality_dir = Path(primary_root), Path(quality_dir)
    report = {'schema': 'financial_data.native_session_schedule.v1', 'state': 'OBSERVED_NOT_CERTIFIED',
              'calendar_certified': False, 'pairs': {}}
    for pair in ('eurusd', 'gbpusd'):
        paths = sorted(primary_root.glob(f'*/{pair}/*-1h.parquet'))
        frame = pd.concat([pd.read_parquet(p, columns=['timestamp']) for p in paths], ignore_index=True)
        weeks = weekly_schedule(frame.timestamp)
        failed = set()
        for status in primary_root.glob('*/STATUS.json'):
            for f in json.loads(status.read_text()).get('failures', []):
                p, y, w = f['job'].split('-')
                failed.add((p, int(y), int(w)))
        quality = json.loads((quality_dir / f'QUALITY.{pair}.json').read_text())
        missing = pd.to_datetime([t for m in quality['months'] for t in m['missing_timestamps']], utc=True)
        runs, s = [], None
        for i, t in enumerate(missing):
            if s is None:
                s = prev = t
                continue
            if t - prev != pd.Timedelta(hours=1):
                runs.append({'start': s.isoformat(), 'end': prev.isoformat(), 'hours': int((prev - s) / pd.Timedelta(hours=1)) + 1})
                s = t
            prev = t
        if s is not None:
            runs.append({'start': s.isoformat(), 'end': prev.isoformat(), 'hours': int((prev - s) / pd.Timedelta(hours=1)) + 1})
        classified = classify_runs(pair, runs, failed)
        opens = pd.Series([w['first_bar_ny_weekday_hour'] for w in weeks]).value_counts().to_dict()
        closes = pd.Series([w['last_bar_ny_weekday_hour'] for w in weeks]).value_counts().to_dict()
        report['pairs'][pair] = {'weeks_observed': len(weeks), 'first_bar_ny_weekday_hour_counts': opens,
                                 'last_bar_ny_weekday_hour_counts': closes,
                                 'source_week_failures': sorted(f"{y}-W{w:02d}:{f}" for (p, y, w) in failed if p == pair for f in ['FAILED']),
                                 'missing_runs': classified,
                                 'class_hours': pd.DataFrame(classified).groupby('class').hours.sum().astype(int).to_dict() if classified else {},
                                 'weeks': weeks}
    return report


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--primary-root', required=True)
    parser.add_argument('--quality-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.primary_root, args.quality_dir)
    output = Path(args.output)
    temp = output.with_suffix('.partial')
    temp.write_text(json.dumps(result, sort_keys=True, indent=1) + '\n')
    os.replace(temp, output)
    print(json.dumps({'state': result['state'], 'pairs': {p: v['class_hours'] for p, v in result['pairs'].items()}}))


if __name__ == '__main__':
    main()
