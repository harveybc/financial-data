"""One bounded public download; observed tick hours and clock evidence only."""

import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import resource
import time
from urllib.parse import urljoin
import zipfile

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import numpy as np
import pandas as pd
import requests

FORM_URL = ('https://www.histdata.com/download-free-forex-historical-data/'
            '?/ascii/tick-data-quotes/eurusd/2023/7')
SPEC_URL = 'https://www.histdata.com/f-a-q/data-files-detailed-specification/'
PUBLIC_FIELDS = dict(date='2023', datemonth='202307', platform='ASCII', timeframe='T', fxpair='EURUSD')
CLOCKS = ('fixedEST', 'US_Eastern', 'native_plus5_London')
OHLC = ['open', 'high', 'low', 'close']
FX_OHLC = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose']
MAX_ZIP = 256 * 1024**2
MAX_MEMORY = 2 * 1024**3
MAX_UNCOMPRESSED = 8 * 1024**3
SAFE_HEADERS = {'content-type', 'content-length', 'content-encoding', 'date', 'retry-after'}


class Forms(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.current = [attrs, {}]
        elif tag == 'input' and self.current is not None and attrs.get('name'):
            self.current[1][attrs['name']] = attrs.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'form' and self.current is not None:
            self.forms.append(self.current)
            self.current = None


def parse_form(html):
    parser = Forms()
    parser.feed(html)
    for attrs, fields in parser.forms:
        action = urljoin(FORM_URL, attrs.get('action', ''))
        if (action == 'https://www.histdata.com/get.php'
                and attrs.get('method', '').lower() == 'post'
                and all(fields.get(k) == v for k, v in PUBLIC_FIELDS.items())
                and fields.get('tk')):
            return action, fields
    raise ValueError('PUBLIC_FORM_NOT_FOUND')


def response_metadata(response):
    return {'status': response.status_code,
            'headers': {k.lower(): v for k, v in response.headers.items()
                        if k.lower() in SAFE_HEADERS}}


def download_once(root, session):
    """No retries/redirect following. Never persist the form or token."""
    result = {'state': 'GET_STARTED', 'form_url': FORM_URL, 'attempts': 1}
    deadline = time.monotonic() + 240
    response = None
    writer = None
    digest = None
    size = 0
    try:
        response = session.get(FORM_URL, stream=True, timeout=(15, 45), allow_redirects=False)
        result['get'] = response_metadata(response)
        body = bytearray()
        for chunk in response.iter_content(65536):
            if len(body) + len(chunk) > 2 * 1024**2 or time.monotonic() > deadline:
                raise ValueError('FORM_RESPONSE_LIMIT')
            body.extend(chunk)
        response.close()
        if result['get']['status'] != 200:
            result['state'] = 'GET_HTTP_FAILURE'
            return result
        action, fields = parse_form(body.decode('utf-8', errors='replace'))
        del body
        result['state'] = 'POST_STARTED'
        response = session.post(action, data=fields, headers={'Referer': FORM_URL},
                                stream=True, timeout=(15, 60), allow_redirects=False)
        del fields
        result['post'] = response_metadata(response)
        digest = hashlib.sha256()
        size = 0
        probe = bytearray()
        is_zip = None
        limited = False
        for chunk in response.iter_content(65536):
            if not chunk:
                continue
            if size + len(chunk) > MAX_ZIP or time.monotonic() > deadline:
                limited = True
                break
            size += len(chunk)
            digest.update(chunk)
            if is_zip is None:
                probe.extend(chunk)
                if len(probe) < 4:
                    continue
                is_zip = probe[:4] == b'PK\x03\x04'
                if is_zip:
                    writer = (root / 'EURUSD_T_202307.zip').open('xb')
                    writer.write(probe)
                probe.clear()
            elif writer is not None:
                writer.write(chunk)
        result['post'].update(bytes=size, sha256=digest.hexdigest(),
                              digest_scope='retained_prefix' if limited else 'entire_response',
                              complete=not limited)
        if limited:
            result['state'] = 'POST_LIMIT_EXCEEDED'
        elif response.status_code != 200:
            result['state'] = 'POST_HTTP_FAILURE'
        else:
            result['state'] = 'ZIP_DOWNLOADED' if is_zip else 'POST_NOT_ZIP'
        if writer is not None:
            result['raw_zip'] = 'EURUSD_T_202307.zip'
    except Exception as exc:
        # Exception strings may contain request details; retain only a type/code.
        result['failure_phase'] = result['state']
        result['state'] = 'DOWNLOAD_FAILED'
        result['error_type'] = type(exc).__name__
        if isinstance(exc, ValueError) and str(exc) in {'PUBLIC_FORM_NOT_FOUND', 'FORM_RESPONSE_LIMIT'}:
            result['error_code'] = str(exc)
    finally:
        if digest is not None and 'sha256' not in result['post']:
            result['post'].update(bytes=size, sha256=digest.hexdigest(),
                                  digest_scope='received_prefix', complete=False)
        if writer is not None:
            writer.close()
        if response is not None:
            response.close()
    return result


def parse_ticks(stream, chunk_size=50000, expected_month=None):
    """Retain only per-hour state and one CSV chunk; never sort or fill ticks."""
    if not 1 <= chunk_size <= 100000:
        raise ValueError('CHUNK_SIZE_LIMIT')
    stats = dict(source_rows=0, accepted_ticks=0, rejected_quotes=0)
    bars, source_counts, reject_counts = {}, {}, {}
    previous_source = previous_valid = None
    reader = pd.read_csv(stream, header=None, names=['native', 'bid', 'ask', 'volume'],
                         dtype=str, keep_default_na=False, chunksize=chunk_size,
                         skip_blank_lines=False, on_bad_lines='error')
    for chunk in reader:
        native = chunk['native']
        valid_stamp = native.str.fullmatch(r'[0-9]{8} [0-9]{9}').fillna(False)
        times = pd.to_datetime(native, format='%Y%m%d %H%M%S%f', errors='coerce')
        if not valid_stamp.all() or times.isna().any():
            raise ValueError('BAD_TIMESTAMP')
        if expected_month is not None and not native.str.startswith(expected_month).all():
            raise ValueError('UNEXPECTED_MONTH')
        if not times.is_monotonic_increasing or (previous_source is not None and times.iloc[0] < previous_source):
            raise ValueError('NON_MONOTONIC_SOURCE_TIMES')
        previous_source = times.iloc[-1]
        hour = times.dt.floor('h')
        if len(set(source_counts).union(hour.unique())) > 800:
            raise ValueError('MONTH_HOUR_LIMIT')
        for key, count in hour.value_counts().items():
            source_counts[key] = source_counts.get(key, 0) + int(count)
        bid = pd.to_numeric(chunk['bid'], errors='coerce')
        ask = pd.to_numeric(chunk['ask'], errors='coerce')
        volume = pd.to_numeric(chunk['volume'], errors='coerce')
        good = (np.isfinite(bid) & np.isfinite(ask) & np.isfinite(volume)
                & (bid > 0) & (ask >= bid) & (volume >= 0))
        for key, count in hour[~good].value_counts().items():
            reject_counts[key] = reject_counts.get(key, 0) + int(count)
        offset = stats['source_rows']
        stats['source_rows'] += len(chunk)
        stats['rejected_quotes'] += int((~good).sum())
        stats['accepted_ticks'] += int(good.sum())
        valid = pd.DataFrame({'native': times[good], 'bid': bid[good], 'hour': hour[good],
                              'row': np.arange(offset + 1, offset + len(chunk) + 1)[good]})
        if valid.empty:
            continue
        prior = valid['native'].shift()
        prior.iloc[0] = previous_valid if previous_valid is not None else pd.NaT
        gaps = (valid['native'] - prior).dt.total_seconds()
        same_hour = prior.dt.floor('h') == valid['hour']
        valid['internal_gap'] = gaps.where(same_hour)
        valid['incoming_gap'] = gaps.where(~same_hour)
        previous_valid = valid['native'].iloc[-1]
        groups = valid.groupby('hour', sort=False).agg(
            open=('bid', 'first'), high=('bid', 'max'), low=('bid', 'min'), close=('bid', 'last'),
            tick_count=('bid', 'size'), first_tick_native=('native', 'first'), last_tick_native=('native', 'last'),
            source_row_first=('row', 'first'), source_row_last=('row', 'last'),
            max_intertick_gap_seconds=('internal_gap', 'max'),
            gap_from_previous_hour_last_tick_seconds=('incoming_gap', 'max'))
        for key, row in groups.iterrows():
            value = row.to_dict()
            if key not in bars:
                bars[key] = value
                continue
            old = bars[key]
            old['high'] = max(old['high'], value['high'])
            old['low'] = min(old['low'], value['low'])
            old['close'] = value['close']
            old['last_tick_native'] = value['last_tick_native']
            old['source_row_last'] = value['source_row_last']
            old['tick_count'] += value['tick_count']
            old['max_intertick_gap_seconds'] = np.nanmax(
                [old['max_intertick_gap_seconds'], value['max_intertick_gap_seconds']])
    rows = []
    for hour, bar in bars.items():
        rows.append(dict(native_hour=hour, **bar, source_rows_in_hour=source_counts[hour],
                         rejected_quote_count=reject_counts.get(hour, 0)))
    stats.update(observed_price_hours=len(rows), source_hours=len(source_counts),
                 rejected_only_hours=len(set(source_counts) - set(bars)), interpolated_values=0)
    return pd.DataFrame(rows), stats


def clock_to_utc(values, clock):
    if clock == 'fixedEST':
        return values.dt.tz_localize('Etc/GMT+5').dt.tz_convert('UTC')
    if clock == 'US_Eastern':
        return values.dt.tz_localize('America/New_York', ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC')
    if clock == 'native_plus5_London':
        return (values + pd.Timedelta(hours=5)).dt.tz_localize(
            'Europe/London', ambiguous='raise', nonexistent='raise').dt.tz_convert('UTC')
    raise ValueError('UNKNOWN_CLOCK')


def hourly_candidate(bars, clock):
    if clock not in CLOCKS:
        raise ValueError('UNKNOWN_CLOCK')
    frame = bars.copy()
    frame['timestamp'] = clock_to_utc(frame['native_hour'], clock)
    frame['first_tick_utc'] = clock_to_utc(frame['first_tick_native'], clock)
    frame['last_tick_utc'] = clock_to_utc(frame['last_tick_native'], clock)
    frame['available_at_utc'] = frame['timestamp'] + pd.Timedelta(hours=1)
    frame['clock_candidate'] = clock
    frame['admitted'] = False
    frame['coverage_state'] = 'OBSERVED_TICKS_ONLY_COMPLETENESS_UNKNOWN'
    frame['publication_available_at_utc'] = pd.NaT
    return frame


def compare_clocks(candidates, fxcm):
    fxcm = fxcm.copy()
    fxcm['timestamp'] = pd.to_datetime(fxcm['timestamp'], utc=True)
    if fxcm['timestamp'].duplicated().any():
        raise ValueError('DUPLICATE_FXCM_HOURS')
    fxcm = fxcm.set_index('timestamp')[FX_OHLC].astype(float)
    fxcm = fxcm.loc[np.isfinite(fxcm).all(axis=1) & (fxcm > 0).all(axis=1)]
    frames = {k: v.set_index('timestamp') for k, v in candidates.items()}
    support = fxcm.index
    for frame in frames.values():
        support = support.intersection(frame.index)
    support = support.sort_values()
    evidence = dict(clock_state='UNRESOLVED', selected_clock=None, common_support_hours=len(support),
                    scores={}, admitted=False, specification_claim='fixedEST', specification_url=SPEC_URL)
    details = []
    for clock, frame in frames.items():
        delta = (frame.loc[support, OHLC].to_numpy() - fxcm.loc[support, FX_OHLC].to_numpy()) * 10000
        score = dict(hours=len(support), overlap_hours=len(frame.index.intersection(fxcm.index)),
                     ohlc_mae_pips=float(np.abs(delta).mean()) if len(support) else None,
                     ohlc_median_absolute_error_pips=float(np.median(np.abs(delta))) if len(support) else None)
        evidence['scores'][clock] = score
        for i, stamp in enumerate(support):
            details.append(dict(timestamp=stamp, clock_candidate=clock,
                                **{f'{c}_error_pips': float(delta[i, j]) for j, c in enumerate(OHLC)}))
    # Equivalent July clocks cannot be distinguished by this month's witness.
    if len(support) >= 48:
        ranked = sorted(CLOCKS, key=lambda c: evidence['scores'][c]['ohlc_mae_pips'])
        best, second = (evidence['scores'][c]['ohlc_mae_pips'] for c in ranked[:2])
        if best <= 5 and second >= max(best * 2, best + 1):
            evidence.update(clock_state='CORROBORATED_CANDIDATE_NOT_ADMITTED', selected_clock=ranked[0])
    evidence['selection_gate'] = '>=48 common hours; best <=5 pips; runner-up >=2x and >=1 pip worse'
    evidence['equivalent_july_candidates'] = ['US_Eastern', 'native_plus5_London']
    return evidence, pd.DataFrame(details)


def write_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--fxcm-h1', type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY, MAX_MEMORY))
    root = args.output_root
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        parser.error('Output root must be empty; refusing another network attempt or overwrite')
    # Persist intent before network I/O, so interruption cannot enable a silent retry.
    write_json(root / 'attempt.json', dict(pair='EURUSD', month='202307', max_zip_bytes=MAX_ZIP,
                                         max_address_space_bytes=MAX_MEMORY, admitted=False))
    with requests.Session() as session:
        download = download_once(root, session)
    write_json(root / 'download.json', download)
    report = dict(state=download['state'], admitted=False, source_rows=0, accepted_ticks=0, hourly_candidates=0)
    try:
        if download['state'] == 'ZIP_DOWNLOADED':
            with zipfile.ZipFile(root / download['raw_zip']) as archive:
                members = archive.infolist()
                csvs = [entry for entry in members if entry.filename.lower().endswith('.csv')]
                if (len(csvs) != 1 or sum(e.file_size for e in members) > MAX_UNCOMPRESSED
                        or csvs[0].flag_bits & 1):
                    raise ValueError('ZIP_MEMBER_CONTRACT')
                with archive.open(csvs[0]) as stream:
                    bars, stats = parse_ticks(stream, expected_month='202307')
                report.update(stats, csv_member=csvs[0].filename,
                              uncompressed_csv_bytes=csvs[0].file_size)
            if bars.empty:
                raise ValueError('NO_ACCEPTED_TICKS')
            bars.to_parquet(root / 'observed_native_hours.parquet', index=False)
            candidates = {clock: hourly_candidate(bars, clock) for clock in CLOCKS}
            for clock, frame in candidates.items():
                frame.to_parquet(root / f'hourly_{clock}.parquet', index=False)
            report['hourly_candidates'] = sum(len(f) for f in candidates.values())
            import pyarrow.parquet as pq
            fxcm = pq.read_table(args.fxcm_h1, columns=['timestamp'] + FX_OHLC,
                                 use_threads=False).to_pandas(use_threads=False)
            evidence, details = compare_clocks(candidates, fxcm)
            write_json(root / 'clock_comparison.json', evidence)
            details.to_csv(root / 'clock_comparison_common_support.csv', index=False)
            report.update(state='CANDIDATES_AND_EVIDENCE_ONLY', clock_state=evidence['clock_state'],
                          selected_clock=evidence['selected_clock'], common_support_hours=evidence['common_support_hours'])
    except Exception as exc:
        report.update(state='VALIDATION_FAILED_RAW_RETAINED', error_type=type(exc).__name__)
        if isinstance(exc, ValueError):
            report['error_code'] = str(exc)[:120]
    report['peak_rss_bytes'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    write_json(root / 'report.json', report)
    print(json.dumps(report, allow_nan=False))
    return 0 if report['state'] == 'CANDIDATES_AND_EVIDENCE_ONLY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
