"""Bounded independent public HF recovery, audits and explicit label hypotheses.

Test gates: pinned identity/byte cap; actual schema/quality; identical-support
offset comparison; exact missing-hour denominator; optional native M30 lineage.
No financial fitting, price fill, timezone assignment, source merge or admission.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import time

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import requests

DATASET = 'Yllvar/fx-historical-data'
API = f'https://huggingface.co/api/datasets/{DATASET}'
BASE = f'https://huggingface.co/datasets/{DATASET}/resolve'
LIMIT = 32 * 1024**2
OHLC = ['open', 'high', 'low', 'close']
FX = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']
OFFSETS = list(range(-3, 4))
START, END = pd.Timestamp('2020-01-01', tz='UTC'), pd.Timestamp('2026-01-01', tz='UTC')
MONTHS = pd.period_range('2020-01', '2025-12', freq='M').astype(str).tolist()


def dump(path, value):
    with path.open('w') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def validate_revision(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{40}', value):
        raise ValueError('INVALID_REVISION_SHA')
    return value


def download(session, url, path, limit=LIMIT):
    entry = dict(url=url, file=path.name, bytes=0, state='REQUEST_STARTED')
    digest = hashlib.sha256()
    response = None
    partial = path.with_name(path.name + '.partial')
    deadline = time.monotonic() + 120
    try:
        response = session.get(url, stream=True, timeout=(15, 45), allow_redirects=True)
        entry.update(status=response.status_code, redirect_statuses=[r.status_code for r in response.history],
                     headers={k.lower(): v for k, v in response.headers.items()
                              if k.lower() in {'content-type', 'content-length', 'x-repo-commit'}})
        # Signed CDN redirect URLs/cookies/authorization are never logged.
        if response.status_code != 200:
            entry['state'] = 'HTTP_FAILURE'
            return entry
        if int(response.headers.get('Content-Length', 0)) > limit:
            entry['state'] = 'BYTE_LIMIT_EXCEEDED'
            return entry
        with partial.open('xb') as handle:
            for chunk in response.iter_content(65536):
                if entry['bytes'] + len(chunk) > limit:
                    entry['state'] = 'BYTE_LIMIT_EXCEEDED'
                    break
                if time.monotonic() > deadline:
                    entry['state'] = 'TIME_LIMIT_EXCEEDED'
                    break
                handle.write(chunk)
                digest.update(chunk)
                entry['bytes'] += len(chunk)
            else:
                entry['state'] = 'DOWNLOADED'
        if entry['state'] == 'DOWNLOADED':
            partial.rename(path)
    except Exception as exc:
        entry.update(state='REQUEST_FAILED', error_type=type(exc).__name__)
    finally:
        entry['sha256'] = digest.hexdigest()
        entry['digest_scope'] = 'complete_original_file' if entry['state'] == 'DOWNLOADED' else 'retained_prefix'
        if response is not None:
            response.close()
    return entry


def label_index(series):
    if not pd.api.types.is_datetime64_any_dtype(series.dtype):
        raise ValueError('UNSUPPORTED_TIME_DTYPE_NO_GUESS')
    labels = pd.DatetimeIndex(series)
    if labels.tz is None:
        return labels.tz_localize('UTC'), 'NAIVE_LABEL_AS_UTC_HYPOTHESIS_ONLY'
    return labels.tz_convert('UTC'), 'DECLARED_AWARE_TIMESTAMP_PLUS_EXPLICIT_OFFSET'


def audit_source(raw, cadence_minutes=60):
    required = ['Time', 'Open', 'High', 'Low', 'Close']
    if not set(required).issubset(raw.columns):
        raise ValueError('UNSUPPORTED_SOURCE_COLUMNS')
    labels, basis = label_index(raw['Time'])
    prices = raw[['Open', 'High', 'Low', 'Close']].apply(pd.to_numeric, errors='coerce')
    prices.columns = OHLC
    finite_positive = np.isfinite(prices).all(axis=1) & (prices > 0).all(axis=1)
    shape = ((prices.high >= prices[['open', 'low', 'close']].max(axis=1))
             & (prices.low <= prices[['open', 'high', 'close']].min(axis=1)))
    valid_ohlc = finite_positive & shape
    duplicates = labels.duplicated(keep=False)
    aligned = labels == labels.floor(f'{cadence_minutes}min')
    good = valid_ohlc.to_numpy() & ~labels.isna() & ~duplicates & aligned
    normalized = prices.copy()
    normalized.index = labels
    if 'Volume' in raw:
        normalized['volume'] = pd.to_numeric(raw['Volume'], errors='coerce').to_numpy()
    report = dict(rows=len(raw), columns=[str(c) for c in raw.columns],
                  dtypes={str(c): str(raw[c].dtype) for c in raw.columns},
                  first_timestamp=str(raw['Time'].iloc[0]) if len(raw) else None,
                  last_timestamp=str(raw['Time'].iloc[-1]) if len(raw) else None,
                  min_timestamp=str(raw['Time'].min()), max_timestamp=str(raw['Time'].max()),
                  timestamp_timezone=str(raw['Time'].dt.tz) if raw['Time'].dt.tz is not None else None,
                  comparison_time_basis=basis, monotonic_increasing=bool(labels.is_monotonic_increasing),
                  duplicate_timestamp_rows=int(duplicates.sum()), missing_timestamps=int(labels.isna().sum()),
                  nonaligned_timestamp_rows=int((~aligned).sum()),
                  ohlc_missing_cells=int(prices.isna().sum().sum()), invalid_ohlc_rows=int((~valid_ohlc).sum()),
                  usable_comparison_rows=int(good.sum()), timezone_verified=False, admitted=False)
    if 'volume' in normalized:
        report['zero_volume_rows'] = int(normalized.volume.eq(0).sum())
    if 'timestamp_ms' in raw:
        epoch = pd.to_numeric(raw['timestamp_ms'], errors='coerce').to_numpy()
        report['timestamp_ms_disagreements'] = int((epoch != labels.asi8 // 1000000).sum())
    scope = (labels >= START) & (labels < END)
    report['in_scope_2020_2025_rows'] = int(scope.sum())
    report['in_scope_invalid_or_ambiguous_rows'] = int((scope & ~good).sum())
    return report, normalized.loc[good]


def missing_targets(quality):
    values = []
    for month in quality['months']:
        missing = month['missing_timestamps']
        if len(missing) != month['missing_expected_open_hours']:
            raise ValueError('MISSING_DENOMINATOR_MONTH')
        values.extend(missing)
    index = pd.to_datetime(values, utc=True)
    if len(index) != quality['missing_expected_open_hours'] or index.has_duplicates:
        raise ValueError('MISSING_DENOMINATOR_TOTAL')
    return index


def diff_stats(delta):
    if not delta.size:
        return dict(ohlc_median_abs_diff_pips=None, ohlc_p95_abs_diff_pips=None)
    return dict(ohlc_median_abs_diff_pips=float(np.median(delta)),
                ohlc_p95_abs_diff_pips=float(np.quantile(delta, .95)),
                **{f'{name}_{stat}_abs_diff_pips': float(fn(delta[:, i]))
                   for i, name in enumerate(OHLC)
                   for stat, fn in [('median', np.median), ('p95', lambda x: np.quantile(x, .95))]})


def compare(candidate, fxcm, targets):
    frames = {}
    for offset in OFFSETS:
        shifted = candidate.copy()
        shifted.index = shifted.index + pd.Timedelta(hours=offset)
        frames[offset] = shifted.loc[(shifted.index >= START) & (shifted.index < END)]
    fxcm = fxcm.loc[(fxcm.index >= START) & (fxcm.index < END)]
    support = fxcm.index
    for frame in frames.values():
        support = support.intersection(frame.index)
    support = support.sort_values()
    support_months = support.strftime('%Y-%m')
    target_months = targets.strftime('%Y-%m')
    report = dict(offsets=[], timezone_verified=False, selected_offset_hours=None, admitted=False,
                  offset_definition='candidate comparison UTC label = source label + offset hours',
                  common_support_policy='identical intersection of all seven shifts and native FXCM',
                  missing_v2_hours=len(targets), calendar_status='v2 assumed-open denominator, not certified closures')
    monthly, gaps = [], []
    for offset, frame in frames.items():
        frame_months = frame.index.strftime('%Y-%m')
        delta = np.abs(frame.loc[support, OHLC].to_numpy() - fxcm.loc[support, OHLC].to_numpy()) * 10000
        covered = targets.intersection(frame.index)
        report['offsets'].append(dict(offset_hours=offset, common_support_hours=len(support),
                                      pairwise_overlap_hours=len(frame.index.intersection(fxcm.index)),
                                      in_scope_source_hours=len(frame), missing_v2_hours_covered=len(covered),
                                      **diff_stats(delta)))
        for month in MONTHS:
            mask = support_months == month
            target_mask = target_months == month
            monthly.append(dict(month=month, offset_hours=offset, common_support_hours=int(mask.sum()),
                                source_hours=int((frame_months == month).sum()),
                                missing_v2_hours=int(target_mask.sum()),
                                missing_v2_hours_covered=int(targets[target_mask].isin(frame.index).sum()),
                                **diff_stats(delta[mask])))
        for stamp in targets:
            found = stamp in frame.index
            row = dict(missing_timestamp_utc=stamp, offset_hours=offset, candidate_present=found,
                       original_source_comparison_label=stamp - pd.Timedelta(hours=offset), admitted=False)
            if found:
                row.update({col: float(frame.loc[stamp, col]) for col in OHLC})
                if 'volume' in frame:
                    row['volume'] = float(frame.loc[stamp, 'volume'])
            gaps.append(row)
    return report, pd.DataFrame(monthly), pd.DataFrame(gaps)


def verify_m30(h1, raw_m30):
    audit, m30 = audit_source(raw_m30, cadence_minutes=30)
    raw_labels, _ = label_index(raw_m30['Time'])
    raw_counts = pd.Series(1, index=raw_labels).groupby(raw_labels.floor('h')).sum()
    group = m30.groupby(m30.index.floor('h'))
    aggregated = group.agg(open=('open', 'first'), high=('high', 'max'),
                           low=('low', 'min'), close=('close', 'last'))
    # Sorting only the derived read-only view makes first/last aggregation explicit.
    if not m30.index.is_monotonic_increasing:
        group = m30.sort_index().groupby(m30.index.sort_values().floor('h'))
        aggregated = group.agg(open=('open', 'first'), high=('high', 'max'),
                               low=('low', 'min'), close=('close', 'last'))
    valid_counts = group.size()
    scope = h1.loc[(h1.index >= START) & (h1.index < END)]
    out = pd.DataFrame(index=scope.index)
    out['raw_m30_rows'] = raw_counts.reindex(scope.index).fillna(0).astype(int)
    out['valid_aligned_m30_rows'] = valid_counts.reindex(scope.index).fillna(0).astype(int)
    out['exact_two_aligned_native_rows'] = out.raw_m30_rows.eq(2) & out.valid_aligned_m30_rows.eq(2)
    errors = np.abs(scope[OHLC] - aggregated.reindex(scope.index)[OHLC])
    for column in OHLC:
        out[f'{column}_abs_error'] = errors[column]
    out['ohlc_within_1e_12'] = errors.le(1e-12).all(axis=1)
    out['exactly_verified'] = out.exact_two_aligned_native_rows & out.ohlc_within_1e_12
    summary = dict(in_scope_usable_h1_rows=len(scope), h1_rows_exactly_verified=int(out.exactly_verified.sum()),
                   incomplete_or_misaligned_hours=int((~out.exact_two_aligned_native_rows).sum()),
                   ohlc_mismatch_hours=int((out.exact_two_aligned_native_rows & ~out.ohlc_within_1e_12).sum()),
                   tolerance=1e-12, bar_label_basis='same original source labels floored to hour, no measured shift applied',
                   m30_audit=audit, admitted=False)
    summary['incomplete_or_misaligned_timestamps'] = [t.isoformat() for t in out.index[~out.exact_two_aligned_native_rows]]
    summary['ohlc_mismatch_timestamps'] = [t.isoformat() for t in out.index[
        out.exact_two_aligned_native_rows & ~out.ohlc_within_1e_12]]
    return summary, out.reset_index(names='source_h1_comparison_label')


def read_public_parquet(path):
    parquet = pq.ParquetFile(path)
    if parquet.metadata.num_rows > 250000 or len(parquet.schema.names) > 16:
        raise ValueError('PARQUET_EXPANSION_LIMIT')
    return parquet.read(use_threads=False).to_pandas(use_threads=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bulk-root', type=Path, required=True)
    parser.add_argument('--resume-local', action='store_true',
                        help='Reuse completed original files; never retry a retained partial download')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    root = args.bulk_root / 'independent-hf-h1'
    root.mkdir(exist_ok=True)
    if any(root.iterdir()) and not args.resume_local:
        parser.error('Refusing overwrite or repeated acquisition in nonempty output root')
    if not (root / 'attempt.json').exists():
        dump(root / 'attempt.json', dict(dataset=DATASET, max_bytes_per_file=LIMIT,
                                        offsets=OFFSETS, admitted=False, retries=0))

    def fetch(session, url, path, limit=LIMIT):
        if args.resume_local and path.exists():
            if path.stat().st_size > limit:
                raise ValueError('CACHED_FILE_BYTE_LIMIT')
            return dict(url=url, file=path.name, state='DOWNLOADED', bytes=path.stat().st_size,
                        sha256=sha(path), digest_scope='complete_original_file',
                        transport='REUSED_COMPLETED_LOCAL_BYTES_NO_NETWORK')
        if path.with_name(path.name + '.partial').exists():
            return dict(url=url, file=path.name, state='PARTIAL_RETAINED_NO_RETRY')
        return download(session, url, path, limit)
    report = dict(dataset=DATASET, admitted=False, timezone_verified=False, pairs={}, downloads=[],
                  method=dict(stage='BOUNDED_ALPHA', review_owner='user',
                              requirements=['byte_identity_and_revision', 'source_quality', 'common_support_offsets',
                                            'exact_v2_missing_targets', 'conditional_native_m30_lineage'],
                              next_action='review evidence only; admission and any source replacement excluded'))
    try:
        with requests.Session() as session:
            session.max_redirects = 5
            meta = fetch(session, API, root / 'dataset_api.json', 2 * 1024**2)
            report['downloads'].append(meta)
            if meta['state'] != 'DOWNLOADED':
                raise ValueError('DATASET_API_DOWNLOAD_FAILED')
            dataset = json.loads((root / 'dataset_api.json').read_text())
            revision = validate_revision(dataset['sha'])
            report['revision_sha'] = revision
            card = fetch(session, f'{BASE}/{revision}/README.md', root / 'README.producer.md', 1024**2)
            report['downloads'].append(card)
            if card['state'] != 'DOWNLOADED':
                raise ValueError('PINNED_CARD_DOWNLOAD_FAILED')
            report['producer_declared_metadata'] = dict(
                license=(dataset.get('cardData') or {}).get('license'),
                tags=dataset.get('tags', []), timezone='UTC', time_label='bar open',
                h1_derivation='M30', upstream='DukasCopy via forexsb.com',
                status='producer card claims, not measured verification')
            for pair in ['EURUSD', 'GBPUSD']:
                result = report['pairs'][pair] = dict(state='STARTED', admitted=False)
                entry = fetch(session, f'{BASE}/{revision}/{pair}/{pair}_H1.parquet', root / f'{pair}_H1.parquet')
                report['downloads'].append(entry)
                if entry['state'] != 'DOWNLOADED':
                    result['state'] = entry['state']
                    continue
                try:
                    raw = read_public_parquet(root / f'{pair}_H1.parquet')
                    audit, candidate = audit_source(raw)
                    result['audit'] = audit
                    dump(root / f'{pair}.audit.json', audit)
                    inputs, witnesses = [], []
                    for year in range(2020, 2026):
                        path = args.bulk_root / 'fxcm-native-hourly-bid' / str(year) / pair.lower() / f'{year}-1h.parquet'
                        frame = pq.read_table(path, columns=['timestamp'] + FX, use_threads=False).to_pandas(use_threads=False)
                        frame = frame.rename(columns=dict(zip(FX, OHLC))).set_index('timestamp')
                        witnesses.append(frame)
                        inputs.append(dict(file=str(path.relative_to(args.bulk_root)), sha256=sha(path)))
                    fxcm = pd.concat(witnesses)
                    if fxcm.index.has_duplicates or fxcm.index.tz is None:
                        raise ValueError('FXCM_TIME_CONTRACT')
                    good = np.isfinite(fxcm[OHLC]).all(axis=1) & (fxcm[OHLC] > 0).all(axis=1)
                    fxcm = fxcm.loc[good]
                    quality_path = args.bulk_root / 'fx-consolidated-v2' / f'QUALITY.{pair.lower()}.json'
                    targets = missing_targets(json.loads(quality_path.read_text()))
                    measured, monthly, gaps = compare(candidate, fxcm, targets)
                    v2_path = args.bulk_root / 'fx-consolidated-v2' / f'{pair.lower()}.parquet'
                    v2_labels = pd.DatetimeIndex(pq.read_table(v2_path, columns=['timestamp'],
                                                             use_threads=False).column('timestamp').to_pandas())
                    absent_rows = []
                    for score in measured['offsets']:
                        shifted_labels = candidate.index + pd.Timedelta(hours=score['offset_hours'])
                        absent = v2_labels.difference(shifted_labels)
                        score['existing_v2_hours_absent_from_candidate'] = len(absent)
                        absent_rows.extend(dict(existing_v2_timestamp_utc=t, offset_hours=score['offset_hours']) for t in absent)
                    pd.DataFrame(absent_rows).to_csv(root / f'{pair}.existing_v2_hours_absent.csv', index=False)
                    result.update(comparison=measured, reference_inputs=inputs,
                                  v2_quality_sha256=sha(quality_path), v2_parquet_sha256=sha(v2_path),
                                  state='H1_AUDITED_AND_COMPARED')
                    dump(root / f'{pair}.comparison.json', measured)
                    monthly.to_csv(root / f'{pair}.monthly_offsets.csv', index=False)
                    gaps.to_csv(root / f'{pair}.v2_missing_candidates.csv', index=False)
                    strong = [s for s in measured['offsets'] if s['common_support_hours'] >= 25000
                              and s['ohlc_median_abs_diff_pips'] <= 1 and s['ohlc_p95_abs_diff_pips'] <= 3]
                    native_months = candidate.loc[(candidate.index >= START) & (candidate.index < END)].index.strftime('%Y-%m')
                    full_month_span = set(MONTHS).issubset(set(native_months))
                    gate = bool(strong and full_month_span and audit['in_scope_2020_2025_rows'] >= 30000
                                and audit['in_scope_invalid_or_ambiguous_rows'] == 0)
                    result['m30_download_gate'] = dict(passed=gate, covers_all_72_months=full_month_span,
                        rule='>=30000 scope rows, all72 months, no invalid scope rows, >=25000 common hours, median<=1 pip/p95<=3 pips')
                    if gate:
                        entry = fetch(session, f'{BASE}/{revision}/{pair}/{pair}_M30.parquet', root / f'{pair}_M30.parquet')
                        report['downloads'].append(entry)
                        if entry['state'] == 'DOWNLOADED':
                            summary, lineage = verify_m30(candidate, read_public_parquet(root / f'{pair}_M30.parquet'))
                            result['m30_lineage'] = summary
                            verified = lineage.set_index('source_h1_comparison_label')['exactly_verified']
                            gaps['native_m30_exactly_verified'] = gaps.original_source_comparison_label.map(verified).eq(True)
                            for score in measured['offsets']:
                                score['missing_v2_hours_with_exact_m30_lineage'] = int((
                                    gaps.offset_hours.eq(score['offset_hours']) & gaps.candidate_present
                                    & gaps.native_m30_exactly_verified).sum())
                            gaps.to_csv(root / f'{pair}.v2_missing_candidates.csv', index=False)
                            dump(root / f'{pair}.comparison.json', measured)
                            dump(root / f'{pair}.m30_lineage.json', summary)
                            lineage.to_parquet(root / f'{pair}.m30_lineage.parquet', index=False)
                            result['state'] = 'H1_AND_NATIVE_M30_EVIDENCE_COMPLETE'
                        else:
                            result['m30_download_state'] = entry['state']
                except Exception as exc:
                    result.update(state='PAIR_AUDIT_FAILED', error_type=type(exc).__name__)
                    if isinstance(exc, ValueError) and re.fullmatch('[A-Z_]+', str(exc)):
                        result['error_code'] = str(exc)
        report['state'] = 'BOUNDED_ATTEMPT_COMPLETE'
    except Exception as exc:
        report.update(state='ATTEMPT_FAILED', error_type=type(exc).__name__)
    report['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    dump(root / 'report.json', report)
    print(json.dumps(dict(state=report['state'], revision_sha=report.get('revision_sha'),
                          pairs={k: v['state'] for k, v in report['pairs'].items()}, admitted=False)))


if __name__ == '__main__':
    main()
