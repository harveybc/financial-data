"""Build missing observed Jan 2020 FXCM H1 candidates. Never merge or admit.

The pair is not encoded in the CSV. Authenticate it with the retained provider
URL AND the pair-specific compressed-response digest established by the sidecar.
An output directory is new-only; MANIFEST.json is the completion marker.
Use --status --output-root to verify a retained receipt without writes/network.
"""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import resource
import sys


SOURCE_SHA256 = {
    'eurusd': 'f8fc2ef1c558eb4b73759886222df9c0ef9b60803a94b36442d67d3446c961e7',
    'gbpusd': 'fc0875b0e27323b59a8dc4dd2043457588521d09d99aea73af4258398e3ccfc0',
}
QUOTE_COLUMNS = [side + field for side in ('Bid', 'Ask') for field in ('Open', 'High', 'Low', 'Close')]


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(output, result):
    target = output / 'MANIFEST.json'
    if target.exists():
        raise FileExistsError('MANIFEST_EXISTS_NO_OVERWRITE')
    temporary = output / '.MANIFEST.json.partial'
    with temporary.open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
    directory = os.open(output, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def status(output_root):
    output = Path(output_root).resolve(strict=True)
    manifest = output / 'MANIFEST.json'
    if manifest.stat().st_size > 1024**2:
        raise ValueError('MANIFEST_SIZE_LIMIT')
    raw = manifest.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        receipt = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ValueError('MANIFEST_INVALID_JSON') from exc
    if (not isinstance(receipt, dict)
            or receipt.get('schema') != 'financial_data.fxcm_boundary_candidates.v1'
            or receipt.get('state') != 'BOUNDARY_CANDIDATES_NOT_ADMITTED'
            or receipt.get('admitted') is not False or receipt.get('quote_view') != 'BID'
            or not isinstance(receipt.get('pairs'), dict)
            or set(receipt['pairs']) != set(SOURCE_SHA256)):
        raise ValueError('MANIFEST_CONTRACT_INVALID')
    import pyarrow.parquet as pq

    counts = {}
    for pair, item in receipt['pairs'].items():
        name = f'{pair}-2020-boundary-candidate.parquet'
        if not isinstance(item, dict) or item.get('candidate_file') != name:
            raise ValueError('MANIFEST_CANDIDATE_PATH_INVALID')
        expected_count = item.get('candidate_rows')
        if type(expected_count) is not int or not 0 <= expected_count <= 40:
            raise ValueError('MANIFEST_CANDIDATE_COUNT_INVALID')
        path = output / name
        if path.is_symlink() or path.resolve().parent != output:
            raise ValueError('MANIFEST_CANDIDATE_PATH_INVALID')
        if path.stat().st_size > 32 * 1024**2 or sha(path) != item.get('candidate_sha256'):
            raise ValueError(f'CANDIDATE_HASH_MISMATCH:{pair}')
        with pq.ParquetFile(path) as parquet:
            if parquet.metadata.num_rows != expected_count:
                raise ValueError(f'CANDIDATE_ROW_COUNT_MISMATCH:{pair}')
            if parquet.metadata.num_columns != 10:
                raise ValueError(f'CANDIDATE_SCHEMA_MISMATCH:{pair}')
            count = parquet.read(columns=['timestamp']).num_rows
        if count != expected_count or sha(path) != item['candidate_sha256']:
            raise ValueError(f'CANDIDATE_CHANGED_DURING_STATUS:{pair}')
        counts[pair] = count
    if sha(manifest) != digest:
        raise ValueError('MANIFEST_CHANGED_DURING_STATUS')
    return dict(state='NOT_ADMITTED', admitted=False, candidate_rows=counts,
                hashes_verified=True, manifest_sha256=digest,
                builder_sha256=receipt.get('builder_sha256'), receipt_state=receipt['state'])


def load_parser(predictor_root):
    root = Path(predictor_root).resolve(strict=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    module = importlib.import_module('tools.i6dmo.recover_fxcm_quotes')
    helper = importlib.import_module('tools.i6dmo.recover_fx_quotes')
    identities = {}
    for loaded, name in ((module, 'recover_fxcm_quotes'), (helper, 'recover_fx_quotes')):
        expected = root / 'tools/i6dmo' / f'{name}.py'
        if Path(loaded.__file__).resolve() != expected.resolve():
            raise ValueError('PREDICTOR_IMPORT_ROOT_MISMATCH')
        identities[str(expected.relative_to(root))] = sha(expected)
    return module.parse, identities


def validate_source(frame):
    import pandas as pd

    index = frame.index
    if not isinstance(index, pd.DatetimeIndex) or str(index.tz) != 'UTC' or index.hasnans:
        raise ValueError('BOUNDARY_SUPPORT_REQUIRES_UTC')
    if not index.equals(index.floor('h')):
        raise ValueError('NONHOURLY_SOURCE')
    expected = pd.date_range('2020-01-02T06:00Z', periods=40, freq='h', name='timestamp')
    if not index.equals(expected) or list(frame.columns) != QUOTE_COLUMNS:
        raise ValueError('BOUNDARY_SUPPORT_MUST_BE_EXACT_OBSERVED_40_HOURS')


def authenticate(public, pair, manifest):
    name = f'{pair}-2019-53.csv.gz'
    record = manifest.get(name, {})
    url = f'https://candledata.fxcorporate.com/H1/{pair.upper()}/2019/53.csv.gz'
    path = public / name
    if path.stat().st_size > 8 * 1024**2:
        raise ValueError('SOURCE_AUTHENTICATION_SIZE')
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if (digest != SOURCE_SHA256[pair] or digest != record.get('sha256')
            or record.get('url') != url or record.get('final_url') != url
            or record.get('status') != 200 or record.get('bytes') != len(raw)
            or record.get('rows') != 40 or record.get('observed_2020_rows') != 40):
        raise ValueError('SOURCE_AUTHENTICATION_FAILED')
    return raw, path, digest, url


def build(predictor_root, primary_root, evidence_root, output_root):
    predictor, primary, evidence = [Path(p).resolve(strict=True)
                                    for p in (predictor_root, primary_root, evidence_root)]
    output = Path(output_root).resolve()
    code_root = Path(__file__).resolve().parents[1]
    if any(output.is_relative_to(p) or p.is_relative_to(output)
           for p in (predictor, primary, evidence, code_root)):
        raise ValueError('OUTPUT_OVERLAPS_INPUT')
    if output.exists():
        raise FileExistsError('OUTPUT_EXISTS_NO_OVERWRITE')
    public = evidence / 'public_evidence'
    manifest_path = public / 'fetch_manifest.json'
    manifest_hash = sha(manifest_path)
    retained = json.loads(manifest_path.read_text())
    parse, parser_hashes = load_parser(predictor)
    import numpy as np
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    inputs = [(manifest_path, manifest_hash), (Path(__file__), sha(__file__))]
    inputs.extend((predictor / name, digest) for name, digest in parser_hashes.items())
    candidates, pairs = {}, {}
    for pair in SOURCE_SHA256:
        raw, source_path, digest, url = authenticate(public, pair, retained)
        inputs.append((source_path, digest))
        frame = parse(raw, quote_view='BID')
        validate_source(frame)
        frame['available_at'] = frame.index + pd.Timedelta(hours=1)
        overlap, baselines = set(), []
        for year in range(2020, 2026):
            path = primary / str(year) / pair / f'{year}-1h.parquet'
            baseline_hash = sha(path)
            if path.stat().st_size > 32 * 1024**2:
                raise ValueError('BASELINE_SIZE_LIMIT')
            with pq.ParquetFile(path) as parquet:
                if parquet.metadata.num_rows > 100000 or parquet.metadata.num_columns != 10:
                    raise ValueError('BASELINE_SHAPE_LIMIT')
            baseline = pd.read_parquet(path)
            if set(baseline.columns) != {'timestamp', 'available_at', *QUOTE_COLUMNS}:
                raise ValueError('BASELINE_SCHEMA')
            if str(getattr(baseline.timestamp.dtype, 'tz', None)) != 'UTC':
                raise ValueError('BASELINE_CLOCK_REQUIRES_UTC')
            baseline = baseline.set_index('timestamp')
            if baseline.index.has_duplicates or baseline.index.hasnans:
                raise ValueError('BASELINE_DUPLICATE_OR_NULL_TIMESTAMPS')
            common = frame.index.intersection(baseline.index)
            if len(common):
                try:
                    pd.testing.assert_frame_equal(
                        frame.loc[common], baseline.loc[common, frame.columns],
                        check_exact=True, check_dtype=False, check_freq=False)
                except AssertionError as exc:
                    raise ValueError(f'CONFLICTING_OVERLAP:{pair}:{year}') from exc
                overlap.update(common)
            if sha(path) != baseline_hash:
                raise ValueError('BASELINE_CHANGED_DURING_READ')
            inputs.append((path, baseline_hash))
            baselines.append(dict(file=str(path.relative_to(primary)), sha256=baseline_hash,
                                  rows=len(baseline), overlap_rows=len(common)))
            del baseline
        candidate = frame.loc[~frame.index.isin(overlap)].reset_index()
        candidates[pair] = candidate
        pairs[pair] = dict(source_file=str(source_path.relative_to(evidence)), source_url=url,
                           source_sha256=digest, source_rows=len(frame),
                           identical_overlap_rows=len(overlap), candidate_rows=len(candidate),
                           first_timestamp=candidate.timestamp.min().isoformat() if len(candidate) else None,
                           last_timestamp=candidate.timestamp.max().isoformat() if len(candidate) else None,
                           candidate_file=f'{pair}-2020-boundary-candidate.parquet', baselines=baselines,
                           crossed_side_bar_endpoints=int(((frame.AskClose < frame.BidClose)
                                                          | (frame.AskOpen < frame.BidOpen)).sum()))
        del raw, frame
    # Seal against inputs changing after an earlier year's read, before any write.
    if any(sha(path) != digest for path, digest in inputs):
        raise ValueError('INPUT_CHANGED_BEFORE_WRITE')
    output.mkdir(parents=True, exist_ok=False)
    for pair, frame in candidates.items():
        path = output / pairs[pair]['candidate_file']
        frame.to_parquet(path, index=False)
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
        pd.testing.assert_frame_equal(pd.read_parquet(path), frame, check_exact=True)
        pairs[pair]['candidate_sha256'] = sha(path)
    if any(sha(path) != digest for path, digest in inputs):
        raise ValueError('INPUT_CHANGED_NO_COMPLETION_MANIFEST')
    result = dict(schema='financial_data.fxcm_boundary_candidates.v1',
                  state='BOUNDARY_CANDIDATES_NOT_ADMITTED', admitted=False,
                  quote_view='BID', executable_spread_eligible=False,
                  interpolated_values=0, source_edits=0, merged_rows=0,
                  clock='UTC native H1 bar start; available_at = start + 1 hour',
                  scope='Observed 2020-01-02 06:00 through 2020-01-03 21:00 UTC only',
                  calendar_closure_claim=False, fetch_manifest_sha256=manifest_hash,
                  builder_sha256=sha(__file__), parser_sha256=parser_hashes,
                  versions=dict(python=sys.version.split()[0], pandas=pd.__version__,
                                numpy=np.__version__, pyarrow=pa.__version__),
                  reproduction='python _scripts/recover_fxcm_boundary.py '
                  '--predictor-root "$PREDICTOR_ROOT" --primary-root "$PRIMARY_ROOT" '
                  '--evidence-root "$EVIDENCE_ROOT" --output-root "$NEW_OUTPUT_ROOT"',
                  max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, pairs=pairs)
    write_manifest(output, result)
    return result


def main():
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--output-root', type=Path, required=True)
    for name in ('predictor-root', 'primary-root', 'evidence-root'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    if not args.status and any(getattr(args, name) is None
                               for name in ('predictor_root', 'primary_root', 'evidence_root')):
        parser.error('build requires --predictor-root, --primary-root and --evidence-root')
    for name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[name] = '1'
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    for kind, limit in ((resource.RLIMIT_AS, 2 * 1024**3), (resource.RLIMIT_CPU, 120)):
        soft, hard = resource.getrlimit(kind)
        cap = min(limit, hard) if hard != resource.RLIM_INFINITY else limit
        if soft != resource.RLIM_INFINITY:
            cap = min(cap, soft)
        resource.setrlimit(kind, (cap, cap))
    if args.status:
        print(json.dumps(status(args.output_root)))
        return
    report = build(args.predictor_root, args.primary_root, args.evidence_root, args.output_root)
    print(json.dumps({'state': report['state'], 'admitted': False,
                      'candidate_rows': {p: v['candidate_rows'] for p, v in report['pairs'].items()}}))


if __name__ == '__main__':
    main()
