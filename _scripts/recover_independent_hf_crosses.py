"""Bounded independent public HF recovery of the FX crosses used by the EURUSD H1 cross-asset store.

Additive to ``recover_independent_hf_fx.py`` (its download / audit / M30-lineage / offset-comparison functions are
imported, never edited) and to ``admit_core_fx.py`` (business-calendar required hours, declared-clock rule).

Per pair (default: eurusd gbpusd usdchf usdjpy eurgbp eurjpy audusd usdcad nzdusd xauusd):
  1. one bounded GET each of ``<PAIR>/<PAIR>_H1.parquet`` and ``<PAIR>_M30.parquet`` from the PINNED dataset
     revision into ``<bulk-root>/independent-hf-crosses/`` (byte cap, sha256 of the complete original file, no
     retry: a retained partial is never re-requested; bytes already pinned in the core recovery are reused
     without the network);
  2. schema / quality audit (declared UTC labels, monotonic, positive OHLC, duplicates, alignment);
  3. H1 identity recomputed from M30 (``verify_m30``);
  4. monthly coverage 2020-01..2024-12 against the business calendar's required hours (missing hours LISTED);
  5. clock corroboration of the declared UTC bar-start label against the HistData lake 1h file re-localized from
     the lake clock (Europe/London wall - 5 h, the rule of the feature-eng plugin ``relocalize_lake_clock``):
     hourly offsets -3..+3 as negative controls, (a) the core OHLC-pip rule of ``admit_core_fx`` on identical
     common support and (b) the correlation of EXACT one-hour consecutive log returns (never across a missing
     interval) on the joint support;
  6. for EURUSD, the HF series against the admitted EURUSD core on common support (pip differences).

Derived artifacts (per-pair parquet, STATUS.json, COVERAGE.csv, MISSING_HOURS.csv, CLOCK.json) exclude every
row at or after 2025-01-01 (TEST); the raw files keep whatever the producer published. No admission to the
lake, no interpolation, no price fill, no invented bars.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from admit_core_fx import require_declared_clock, required_hours
from recover_independent_hf_fx import (BASE, DATASET, LIMIT, OFFSETS, OHLC, audit_source, compare, download, dump,
                                       read_public_parquet, sha, validate_revision, verify_m30)

PINNED_REVISION = '4e694887c7f63d7e2c15a66aeebc4f45450cb381'
PAIRS = ['eurusd', 'gbpusd', 'usdchf', 'usdjpy', 'eurgbp', 'eurjpy', 'audusd', 'usdcad', 'nzdusd', 'xauusd']
PIP = {'usdjpy': 0.01, 'eurjpy': 0.01, 'xauusd': 0.1}
SCOPE_START = pd.Timestamp('2020-01-01', tz='UTC')
TEST_START = pd.Timestamp('2025-01-01', tz='UTC')          # derived artifacts stop here (closed)
MONTHS = pd.period_range('2020-01', '2024-12', freq='M').astype(str).tolist()
HOUR = pd.Timedelta(hours=1)
LAKE_SHIFT_HOURS = 5
RETURN_RULE = dict(min_joint_returns=2000, min_corr_offset0=0.95, min_margin_over_controls=0.5,
                   monthly_min_joint_returns=100, monthly_min_margin=0.25)
BID = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']


def pip_size(pair):
    return PIP.get(pair, 0.0001)


# ----------------------------------------------------------------------------- clocks
def relocalize_lake(frame, time_col='datetime', shift_hours=LAKE_SHIFT_HOURS):
    """Mirror of feature-eng ``cross_asset_h1.relocalize_lake_clock``: the HistData lake label is Europe/London
    wall time minus ``shift_hours``; label + shift -> localize Europe/London (ambiguous / nonexistent dropped) ->
    UTC bar start. Duplicates after conversion keep the first row."""
    t = pd.DatetimeIndex(pd.to_datetime(frame[time_col]))
    wall = t.tz_convert('UTC').tz_localize(None) if t.tz is not None else t
    london = (wall + pd.Timedelta(hours=shift_hours)).tz_localize('Europe/London', ambiguous='NaT', nonexistent='NaT')
    out = frame.drop(columns=[time_col]).copy()
    out.index = london.tz_convert('UTC')
    out = out[out.index.notna()]
    out = out[~out.index.duplicated(keep='first')].sort_index()
    out.index.name = 'bar_start_utc'
    return out


def exact_hour_returns(close):
    """Log return of each bar over EXACTLY one hour of its own series: NaN unless the previous observation is
    exactly one hour earlier (a missing interval never becomes a one-hour return)."""
    c = close.sort_index()
    r = np.log(c).diff()
    gap = c.index.to_series().diff()
    return r.where(gap == HOUR)


def return_scores(candidate_close, lake_close):
    """For every offset the correlation of exact one-hour returns on the joint support, overall and per month.
    offset definition: candidate comparison UTC label = source label + offset hours."""
    lake_r = exact_hour_returns(lake_close.loc[(lake_close.index >= SCOPE_START) & (lake_close.index < TEST_START)])
    overall, monthly = [], []
    for offset in OFFSETS:
        shifted = candidate_close.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=offset)
        shifted = shifted.loc[(shifted.index >= SCOPE_START) & (shifted.index < TEST_START)]
        cand_r = exact_hour_returns(shifted)
        joint = pd.concat([cand_r.rename('c'), lake_r.rename('l')], axis=1, join='inner').dropna()
        corr = float(joint.c.corr(joint.l)) if len(joint) >= 3 else None
        overall.append(dict(offset_hours=offset, joint_exact_hour_returns=int(len(joint)), return_corr=corr,
                            mean_abs_return_diff=float((joint.c - joint.l).abs().mean()) if len(joint) else None))
        months = joint.index.strftime('%Y-%m')
        for month in MONTHS:
            sub = joint[months == month]
            monthly.append(dict(month=month, offset_hours=offset, joint_exact_hour_returns=int(len(sub)),
                                return_corr=float(sub.c.corr(sub.l)) if len(sub) >= 3 else None))
    return overall, pd.DataFrame(monthly)


def return_rule(overall, monthly, rule=RETURN_RULE):
    zero = next(r for r in overall if r['offset_hours'] == 0)
    controls = [r for r in overall if r['offset_hours'] != 0]
    reasons = []
    if zero['joint_exact_hour_returns'] < rule['min_joint_returns'] or zero['return_corr'] is None:
        reasons.append('INSUFFICIENT_JOINT_RETURNS')
    elif zero['return_corr'] < rule['min_corr_offset0']:
        reasons.append('OFFSET0_CORRELATION_BELOW_MINIMUM')
    else:
        for r in controls:
            if r['return_corr'] is not None and r['return_corr'] > zero['return_corr'] - rule['min_margin_over_controls']:
                reasons.append(f'CONTROL_{r["offset_hours"]:+d}H_WITHIN_MARGIN')
    failed_months = []
    for month, group in monthly.groupby('month'):
        z = group[group.offset_hours.eq(0)].iloc[0]
        if z.joint_exact_hour_returns < rule['monthly_min_joint_returns'] or pd.isna(z.return_corr):
            continue
        wrong = group[~group.offset_hours.eq(0)].return_corr.dropna()
        if (wrong > z.return_corr - rule['monthly_min_margin']).any():
            failed_months.append(month)
    if failed_months:
        reasons.append('MONTHLY_CONTROL_WITHIN_MARGIN')
    best = max((r for r in overall if r['return_corr'] is not None), key=lambda r: r['return_corr'], default=None)
    return dict(passed=not reasons, reasons=reasons, failed_months=failed_months, rule=rule,
                best_offset_hours=None if best is None else best['offset_hours'],
                offset0_return_corr=zero['return_corr'], offset0_joint_exact_hour_returns=zero['joint_exact_hour_returns'])


def pip_rule(comparison, monthly):
    """The core's declared-clock rule (``admit_core_fx.require_declared_clock`` plus its monthly check), on the
    pip-scaled OHLC comparison of the identical seven-shift common support."""
    reasons = []
    try:
        require_declared_clock(comparison)
    except ValueError as exc:
        reasons.append(str(exc))
    failed_months = []
    for month, group in monthly.groupby('month'):
        correct = group[group.offset_hours.eq(0)].iloc[0]
        wrong = group[~group.offset_hours.eq(0)]
        if correct.common_support_hours < 100:
            continue
        if (correct.ohlc_median_abs_diff_pips > .5 or correct.ohlc_p95_abs_diff_pips > 2
                or (wrong.ohlc_median_abs_diff_pips <= correct.ohlc_median_abs_diff_pips + .1).any()):
            failed_months.append(month)
    if failed_months:
        reasons.append('MONTHLY_CLOCK_CORROBORATION_FAILED')
    zero = next(r for r in comparison['offsets'] if r['offset_hours'] == 0)
    return dict(passed=not reasons, reasons=reasons, failed_months=failed_months,
                common_support_hours=zero['common_support_hours'],
                offset0_median_abs_diff_pips=zero['ohlc_median_abs_diff_pips'],
                offset0_p95_abs_diff_pips=zero['ohlc_p95_abs_diff_pips'],
                rule='offset 0: support>=2000, median<=0.5 pip, p95<=2 pips, every control median>=offset0 median+2 pips; '
                     'monthly (support>=100): median<=0.5, p95<=2, no control median<=offset0 median+0.1')


def clock_against_lake(pair, candidate, lake):
    """Both witnesses truncated before TEST; prices scaled so that compare()'s x10000 reports pips of this pair."""
    scale = 0.0001 / pip_size(pair)
    cand = candidate.loc[(candidate.index >= SCOPE_START) & (candidate.index < TEST_START), OHLC] * scale
    lk = lake.loc[(lake.index >= SCOPE_START) & (lake.index < TEST_START), OHLC] * scale
    comparison, monthly, _ = compare(cand, lk, pd.DatetimeIndex([], tz='UTC'))
    monthly = monthly[monthly.month.isin(MONTHS)].reset_index(drop=True)
    comparison['pip_size'] = pip_size(pair)
    overall, ret_monthly = return_scores(candidate['close'], lake['close'])
    pips = pip_rule(comparison, monthly)
    rets = return_rule(overall, ret_monthly)
    return dict(witness='histdata-lake-1h re-localized Europe/London wall - 5 h (feature-eng relocalize_lake_clock rule)',
                offset_definition=comparison['offset_definition'], selected_offset_hours=0,
                passed=bool(pips['passed'] and rets['passed']), ohlc_pip_rule=pips, exact_hour_return_rule=rets,
                ohlc_pip_offsets=comparison['offsets'], exact_hour_return_offsets=overall), monthly, ret_monthly


# ----------------------------------------------------------------------------- coverage
def coverage(index, expected):
    """Required business hours per month (2020-01..2024-12), observed among them, missing (listed), and observed
    hours outside the calendar. No hour is inferred."""
    index = pd.DatetimeIndex(index)
    expected = pd.DatetimeIndex(expected)
    expected = expected[(expected >= SCOPE_START) & (expected < TEST_START)]
    present = expected.isin(index)
    missing = expected[~present]
    exp_months, miss_months = expected.strftime('%Y-%m'), missing.strftime('%Y-%m')
    scoped = index[(index >= SCOPE_START) & (index < TEST_START)]
    outside = scoped[~scoped.isin(expected)]
    out_months = outside.strftime('%Y-%m')
    rows = []
    for month in MONTHS:
        req = int((exp_months == month).sum())
        miss = int((miss_months == month).sum())
        rows.append(dict(month=month, required_hours=req, observed_hours=req - miss, missing_hours=miss,
                         coverage=(req - miss) / req if req else None,
                         observed_outside_calendar=int((out_months == month).sum())))
    return pd.DataFrame(rows), missing, outside


def half_year_summary(cov):
    out = {}
    for label, months in (('2023H1', [m for m in MONTHS if m.startswith('2023') and int(m[5:]) <= 6]),
                          ('2023H2', [m for m in MONTHS if m.startswith('2023') and int(m[5:]) > 6]),
                          ('2024', [m for m in MONTHS if m.startswith('2024')])):
        sub = cov[cov.month.isin(months)]
        req, miss = int(sub.required_hours.sum()), int(sub.missing_hours.sum())
        out[label] = dict(required_hours=req, missing_hours=miss, coverage=(req - miss) / req if req else None)
    return out


def admitted_comparison(candidate, admitted):
    """HF H1 vs the admitted EURUSD core on common support (both before TEST); pips of 0.0001."""
    adm = admitted.set_index('timestamp')[BID].rename(columns=dict(zip(BID, OHLC)))
    adm = adm.loc[adm.index < TEST_START]
    cand = candidate.loc[(candidate.index >= SCOPE_START) & (candidate.index < TEST_START), OHLC]
    support = adm.index.intersection(cand.index)
    delta = np.abs(cand.loc[support].to_numpy() - adm.loc[support].to_numpy()) / 0.0001
    row_max = delta.max(axis=1) if delta.size else np.array([])
    return dict(common_support_hours=int(len(support)), admitted_hours_before_test=int(len(adm)),
                admitted_hours_absent_from_candidate=int(len(adm.index.difference(cand.index))),
                identical_rows=int((row_max == 0).sum()) if delta.size else 0,
                rows_within_half_pip=int((row_max <= .5).sum()) if delta.size else 0,
                ohlc_median_abs_diff_pips=float(np.median(delta)) if delta.size else None,
                ohlc_p95_abs_diff_pips=float(np.quantile(delta, .95)) if delta.size else None,
                ohlc_max_abs_diff_pips=float(delta.max()) if delta.size else None)


# ----------------------------------------------------------------------------- acquisition
def make_fetcher(session, resume_local):
    def fetch(url, path, limit=LIMIT):
        if resume_local and path.exists():
            if path.stat().st_size > limit:
                raise ValueError('CACHED_FILE_BYTE_LIMIT')
            return dict(url=url, file=path.name, state='DOWNLOADED', bytes=path.stat().st_size, sha256=sha(path),
                        digest_scope='complete_original_file', transport='REUSED_COMPLETED_LOCAL_BYTES_NO_NETWORK')
        if path.with_name(path.name + '.partial').exists():
            return dict(url=url, file=path.name, state='PARTIAL_RETAINED_NO_RETRY')
        return download(session, url, path, limit)
    return fetch


def reuse_pinned(core_root, name, path, revision):
    """Reuse bytes already acquired and receipted by the core recovery at the same revision; no network."""
    if core_root is None or not (core_root / 'report.json').exists() or not (core_root / name).exists():
        return None
    report = json.loads((core_root / 'report.json').read_text())
    if report.get('revision_sha') != revision:
        return None
    receipt = next((d for d in report.get('downloads', []) if d.get('file') == name and d.get('state') == 'DOWNLOADED'), None)
    if receipt is None or sha(core_root / name) != receipt['sha256']:
        return None
    if not path.exists():
        shutil.copyfile(core_root / name, path)
    if sha(path) != receipt['sha256']:
        raise ValueError('REUSED_BYTES_DIGEST_MISMATCH')
    return dict(url=receipt.get('url'), file=name, state='DOWNLOADED', bytes=path.stat().st_size, sha256=receipt['sha256'],
                digest_scope='complete_original_file', transport='REUSED_PINNED_CORE_BYTES_NO_NETWORK')


def load_lake(path):
    raw = pq.read_table(path, columns=['datetime', 'open', 'high', 'low', 'close'], use_threads=False).to_pandas(use_threads=False)
    lake = relocalize_lake(raw, 'datetime')
    good = np.isfinite(lake[OHLC]).all(axis=1) & (lake[OHLC] > 0).all(axis=1)
    return lake.loc[good]


# ----------------------------------------------------------------------------- pipeline
def run(root, fetch, revision, pairs, lake_root, calendar_path, native_config, core_root=None, admitted_path=None):
    revision = validate_revision(revision)
    root.mkdir(parents=True, exist_ok=True)
    calendar = json.loads(calendar_path.read_text())
    config = json.loads(native_config.read_text())
    if calendar.get('schema') != 'financial_data.fx_business_calendar.v1':
        raise ValueError('BUSINESS_CALENDAR_CONTRACT_REQUIRED')
    config['closed_intervals'] = calendar['closed_intervals']
    config['required_start'] = SCOPE_START.isoformat()
    config['required_end_exclusive'] = TEST_START.isoformat()
    expected = required_hours(config)
    status = dict(schema='financial_data.independent_hf_crosses.v1', dataset=DATASET, revision_sha=revision,
                  source_id=f'independent-hf:{revision}', admitted=False, admitted_to_lake=False,
                  interpolation=False, price_fill=False, invented_bars=False, test_rows_excluded_from=TEST_START.isoformat(),
                  calendar_id=calendar.get('calendar_id'), calendar_sha256=sha(calendar_path),
                  native_config_sha256=sha(native_config), code_sha256=sha(Path(__file__)),
                  required_business_hours_2020_2024=int(len(expected)), max_bytes_per_file=LIMIT, retries=0,
                  lake_clock_rule=f'label + {LAKE_SHIFT_HOURS} h localized Europe/London -> UTC (feature-eng relocalize_lake_clock)',
                  downloads=[], pairs={})
    coverage_rows, missing_rows, clock = [], [], dict(revision_sha=revision, offsets=OFFSETS, pairs={})
    monthly_frames = []
    for pair in pairs:
        up = pair.upper()
        result = status['pairs'][pair] = dict(state='STARTED', admitted=False)
        try:
            entries = {}
            for cadence in ('H1', 'M30'):
                name = f'{up}_{cadence}.parquet'
                entry = reuse_pinned(core_root, name, root / name, revision)
                if entry is None:
                    entry = fetch(f'{BASE}/{revision}/{up}/{name}', root / name)
                    header_commit = (entry.get('headers') or {}).get('x-repo-commit')
                    entry['revision_header_match'] = None if header_commit is None else header_commit == revision
                status['downloads'].append(entry)
                entries[cadence] = entry
                if entry['state'] != 'DOWNLOADED':
                    raise ValueError(f'{cadence}_{entry["state"]}')
            result['raw_sha256'] = {c: e['sha256'] for c, e in entries.items()}
            raw = read_public_parquet(root / f'{up}_H1.parquet')
            audit, candidate = audit_source(raw)
            dump(root / f'{pair}.audit.json', audit)
            result['audit'] = dict(rows=audit['rows'], timestamp_timezone=audit['timestamp_timezone'],
                                   monotonic_increasing=audit['monotonic_increasing'],
                                   duplicate_timestamp_rows=audit['duplicate_timestamp_rows'],
                                   invalid_ohlc_rows=audit['invalid_ohlc_rows'],
                                   nonaligned_timestamp_rows=audit['nonaligned_timestamp_rows'],
                                   timestamp_ms_disagreements=audit.get('timestamp_ms_disagreements'),
                                   in_scope_invalid_or_ambiguous_rows=audit['in_scope_invalid_or_ambiguous_rows'],
                                   first_timestamp=audit['first_timestamp'], last_timestamp=audit['last_timestamp'])
            if (audit['timestamp_timezone'] != 'UTC' or not audit['monotonic_increasing']
                    or audit.get('timestamp_ms_disagreements', 0)):
                raise ValueError('INDEPENDENT_SOURCE_QUALITY_FAILED')
            derived = candidate.loc[candidate.index < TEST_START, OHLC].copy()
            lineage, verified = verify_m30(derived, read_public_parquet(root / f'{up}_M30.parquet'))
            lineage.pop('incomplete_or_misaligned_timestamps', None)
            lineage.pop('ohlc_mismatch_timestamps', None)
            dump(root / f'{pair}.m30_lineage.json', lineage)
            result['m30_lineage'] = dict(in_scope_usable_h1_rows=lineage['in_scope_usable_h1_rows'],
                                         h1_rows_exactly_verified=lineage['h1_rows_exactly_verified'],
                                         incomplete_or_misaligned_hours=lineage['incomplete_or_misaligned_hours'],
                                         ohlc_mismatch_hours=lineage['ohlc_mismatch_hours'])
            exact = verified.set_index('source_h1_comparison_label')['exactly_verified']
            derived['m30_exact'] = exact.reindex(derived.index).eq(True).to_numpy()
            derived['source'] = f'independent-hf:{revision}'
            derived.index.name = 'timestamp'
            out = derived.reset_index()
            if (out.timestamp >= TEST_START).any() or out.timestamp.duplicated().any():
                raise ValueError('DERIVED_CONTRACT')
            out.to_parquet(root / f'{pair}.parquet', index=False)
            cov, missing, outside = coverage(derived.index, expected)
            cov.insert(0, 'pair', pair)
            coverage_rows.append(cov)
            missing_rows.extend(dict(pair=pair, missing_timestamp_utc=t.isoformat()) for t in missing)
            result.update(file=f'{pair}.parquet', sha256=sha(root / f'{pair}.parquet'), rows=int(len(out)),
                          rows_2020_2024=int(((derived.index >= SCOPE_START)).sum()),
                          first_timestamp=derived.index[0].isoformat(), last_timestamp=derived.index[-1].isoformat(),
                          missing_required_hours_2020_2024=int(len(missing)),
                          observed_outside_calendar_2020_2024=int(len(outside)),
                          coverage=half_year_summary(cov))
            lake_path = lake_root / 'market_data' / 'forex' / 'g10' / pair / '1h.parquet'
            if lake_path.exists():
                lake = load_lake(lake_path)
                verdict, pip_monthly, ret_monthly = clock_against_lake(pair, candidate, lake)
                verdict['lake_file'] = str(lake_path.relative_to(lake_root))
                verdict['lake_sha256'] = sha(lake_path)
                pip_monthly.insert(0, 'pair', pair)
                ret_monthly.insert(0, 'pair', pair)
                monthly_frames.append(pip_monthly.merge(ret_monthly, on=['pair', 'month', 'offset_hours']))
            else:
                verdict = dict(passed=False, selected_offset_hours=None, witness=None,
                               reason='NO_HOURLY_LAKE_WITNESS_FOR_PAIR',
                               note='declared UTC bar-start label is the producer convention shared with the corroborated pairs; '
                                    'not independently corroborated for this symbol')
            clock['pairs'][pair] = verdict
            result['clock'] = dict(passed=verdict['passed'], selected_offset_hours=verdict.get('selected_offset_hours'),
                                   reason=verdict.get('reason'))
            if pair == 'eurusd' and admitted_path is not None:
                admitted = pd.read_parquet(admitted_path, columns=['timestamp'] + BID)
                result['admitted_core'] = dict(file=admitted_path.name, sha256=sha(admitted_path),
                                               **admitted_comparison(candidate, admitted))
            result['state'] = 'RECOVERED_NOT_ADMITTED'
        except Exception as exc:
            result.update(state='PAIR_FAILED', error_type=type(exc).__name__, error=str(exc)[:200])
    if coverage_rows:
        pd.concat(coverage_rows).to_csv(root / 'COVERAGE.csv', index=False)
    pd.DataFrame(missing_rows, columns=['pair', 'missing_timestamp_utc']).to_csv(root / 'MISSING_HOURS.csv', index=False)
    if monthly_frames:
        pd.concat(monthly_frames).to_csv(root / 'CLOCK_MONTHLY.csv', index=False)
    clock['all_corroborated_pairs_selected_offset_0'] = all(
        v.get('selected_offset_hours') == 0 and v['passed'] for v in clock['pairs'].values() if v.get('witness'))
    dump(root / 'CLOCK.json', clock)
    status['state'] = 'BOUNDED_ATTEMPT_COMPLETE'
    status['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    dump(root / 'STATUS.json', status)
    return status


def main():
    import requests
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bulk-root', type=Path, required=True)
    parser.add_argument('--lake-root', type=Path, required=True, help='financial-data checkout holding market_data/')
    parser.add_argument('--admitted', type=Path, default=None, help='admitted EURUSD core parquet (optional)')
    parser.add_argument('--revision', default=PINNED_REVISION)
    parser.add_argument('--pairs', nargs='+', default=PAIRS, choices=PAIRS)
    parser.add_argument('--resume-local', action='store_true',
                        help='Reuse completed original files; never retry a retained partial download')
    parser.add_argument('--calendar', type=Path, default=Path(__file__).parents[1] / 'configs/fx_business_calendar.v1.json')
    parser.add_argument('--native-config', type=Path, default=Path(__file__).parents[1] / 'configs/native_fx_recovery.v1.json')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    root = args.bulk_root / 'independent-hf-crosses'
    root.mkdir(exist_ok=True)
    if any(root.iterdir()) and not args.resume_local:
        parser.error('Refusing overwrite or repeated acquisition in nonempty output root')
    with requests.Session() as session:
        session.max_redirects = 5
        status = run(root, make_fetcher(session, args.resume_local), args.revision, args.pairs, args.lake_root,
                     args.calendar, args.native_config, core_root=args.bulk_root / 'independent-hf-h1',
                     admitted_path=args.admitted)
    print(json.dumps(dict(state=status['state'], revision_sha=status['revision_sha'],
                          pairs={k: v['state'] for k, v in status['pairs'].items()}, admitted=False)))


if __name__ == '__main__':
    main()
