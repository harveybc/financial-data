"""Normalize the reviewed provider clock, without claiming quote-side or bar-label admission."""
import argparse
import hashlib
import json
import os
from pathlib import Path

import pandas as pd


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_contract(contract, source):
    if contract.get('schema') != 'financial_data.forexite_metastock_clock.v1':
        raise ValueError('UNKNOWN_CLOCK_CONTRACT')
    if contract.get('timezone') != 'Europe/Berlin':
        raise ValueError('UNREVIEWED_CLOCK')
    if sha(source) != contract.get('source_sha256'):
        raise ValueError('SOURCE_EVIDENCE_MISMATCH')
    if contract.get('status') != 'CLOCK_VERIFIED_QUOTE_SIDE_AND_BAR_LABEL_UNRESOLVED':
        raise ValueError('UNREVIEWED_CLOCK_STATUS')


def normalize(frame):
    native = pd.DatetimeIndex(pd.to_datetime(frame.timestamp_native, errors='raise'))
    if native.tz is not None:
        raise ValueError('NATIVE_CLOCK_ALREADY_AWARE')
    if native.isna().any() or (native != native.floor('min')).any():
        raise ValueError('INVALID_NATIVE_MINUTE_LABEL')
    try:
        utc = native.tz_localize('Europe/Berlin', ambiguous='raise', nonexistent='raise').tz_convert('UTC')
    except Exception as exc:
        raise ValueError('AMBIGUOUS_OR_NONEXISTENT_LOCAL_TIME') from exc
    result = frame.copy()
    result['timestamp_utc_label'] = utc
    # A label is not an availability instant until minute-start/end semantics
    # are established. Prices and native labels remain byte-equivalent values.
    return result


def write_status(path, report):
    temporary = path.with_suffix('.partial')
    try:
        with temporary.open('w') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def run(candidate, output, contract_path, source):
    candidate, output = Path(candidate).resolve(), Path(output).resolve()
    contract = json.loads(Path(contract_path).read_text())
    verify_contract(contract, source)
    files = sorted(candidate.glob('*.parquet'))
    if not files or output == candidate or output.is_relative_to(candidate):
        raise ValueError('CANDIDATES_REQUIRED_AND_OUTPUT_MUST_BE_SEPARATE')
    output.mkdir(parents=True, exist_ok=False)
    report = {'schema': 'financial_data.forexite_clock_normalization.v1',
              'state': 'RUNNING', 'clock_verified': True, 'admitted': False,
              'quote_side': 'UNRESOLVED', 'minute_bar_label': 'UNRESOLVED_START_OR_END',
              'contract_sha256': sha(contract_path), 'source_sha256': sha(source),
              'code_sha256': sha(Path(__file__)), 'expected_files': len(files),
              'completed_files': 0, 'rows': 0, 'files': []}
    status = output / 'STATUS.json'
    write_status(status, report)
    try:
        for path in files:
            digest = sha(path)
            frame = normalize(pd.read_parquet(path))
            if sha(path) != digest:
                raise ValueError('SOURCE_CHANGED_DURING_READ')
            target = output / path.name
            temporary = target.with_suffix('.partial')
            try:
                frame.to_parquet(temporary, index=False)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            report['files'].append({'name': path.name, 'source_sha256': digest,
                                    'output_sha256': sha(target), 'rows': len(frame)})
            report['completed_files'] += 1
            report['rows'] += len(frame)
            write_status(status, report)
        report['state'] = 'CLOCK_NORMALIZED_NOT_ADMITTED'
    except Exception as exc:
        report.update(state='FAILED', error_type=type(exc).__name__, reason=str(exc))
        write_status(status, report)
        raise
    write_status(status, report)
    return {key: value for key, value in report.items() if key != 'files'}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--candidate-root')
    parser.add_argument('--output-root', required=True)
    parser.add_argument('--contract')
    parser.add_argument('--source-evidence')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    if args.status:
        report = json.loads((Path(args.output_root) / 'STATUS.json').read_text())
        print(json.dumps({k: v for k, v in report.items() if k != 'files'}, indent=2))
        return
    if not all((args.candidate_root, args.contract, args.source_evidence)):
        parser.error('candidate-root, contract and source-evidence required')
    print(json.dumps(run(args.candidate_root, args.output_root, args.contract,
                         args.source_evidence), indent=2))


if __name__ == '__main__':
    main()
