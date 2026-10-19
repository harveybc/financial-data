"""Boundary-only recovery contracts; real predictor parser via PREDICTOR_ROOT."""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / '_scripts/recover_fxcm_boundary.py'
spec = importlib.util.spec_from_file_location('recover_fxcm_boundary', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def parser():
    root = os.environ.get('PREDICTOR_ROOT')
    if not root:
        pytest.skip('Set PREDICTOR_ROOT to exercise the existing predictor parser')
    return module.load_parser(Path(root))[0]


@pytest.fixture
def fixture(tmp_path, monkeypatch, parser):
    primary, evidence, output = (tmp_path / n for n in ('primary', 'evidence', 'output'))
    public = evidence / 'public_evidence'
    public.mkdir(parents=True)
    manifest, frames, pins = {}, {}, {}
    for pair, value in [('eurusd', 1.1), ('gbpusd', 1.3)]:
        ts = pd.date_range('2020-01-02T06:00Z', periods=40, freq='h')
        frame = pd.DataFrame({c: [value] * 40 for c in module.QUOTE_COLUMNS}, index=ts)
        # Crossed endpoints are retained by BID mode, not rejected as a spread.
        for c in ('AskOpen', 'AskHigh', 'AskLow', 'AskClose'):
            frame[c] = value - .0001
        native = frame.copy()
        native.insert(0, 'DateTime', ts.strftime('%m/%d/%Y %H:%M:%S.000'))
        raw = gzip.compress(native.to_csv(index=False).encode(), mtime=0)
        name = f'{pair}-2019-53.csv.gz'
        (public / name).write_bytes(raw)
        pins[pair] = hashlib.sha256(raw).hexdigest()
        url = f'https://candledata.fxcorporate.com/H1/{pair.upper()}/2019/53.csv.gz'
        manifest[name] = dict(sha256=pins[pair], bytes=len(raw), rows=40,
                              observed_2020_rows=40, status=200, url=url, final_url=url)
        frames[pair] = parser(raw, quote_view='BID')
        for year in range(2020, 2026):
            folder = primary / str(year) / pair
            folder.mkdir(parents=True)
            baseline = frames[pair].iloc[[0]].reset_index()
            baseline['timestamp'] = pd.to_datetime([f'{year}-01-06T00:00Z'])
            baseline['available_at'] = baseline.timestamp + pd.Timedelta(hours=1)
            path = folder / f'{year}-1h.parquet'
            baseline.to_parquet(path, index=False)
    (public / 'fetch_manifest.json').write_text(json.dumps(manifest))
    monkeypatch.setattr(module, 'SOURCE_SHA256', pins)
    return primary, evidence, output, frames


def build(fixture):
    primary, evidence, output, _ = fixture
    return module.build(Path(os.environ['PREDICTOR_ROOT']), primary, evidence, output)


def test_exact_missing_rows_preserve_prices_and_hashes(fixture):
    primary, evidence, output, frames = fixture
    before = {p: sha(p) for root in (primary, evidence) for p in root.rglob('*') if p.is_file()}
    report = build(fixture)
    assert not report['admitted'] and report['interpolated_values'] == 0
    assert report['state'] == 'BOUNDARY_CANDIDATES_NOT_ADMITTED'
    assert len(list(output.iterdir())) == 3
    for pair, source in frames.items():
        item = report['pairs'][pair]
        observed = pd.read_parquet(output / item['candidate_file']).set_index('timestamp')
        pd.testing.assert_frame_equal(observed[module.QUOTE_COLUMNS], source, check_freq=False)
        assert (observed.available_at == observed.index + pd.Timedelta(hours=1)).all()
        assert item['candidate_rows'] == 40 and len(item['baselines']) == 6
        assert sha(output / item['candidate_file']) == item['candidate_sha256']
    assert all(sha(p) == value for p, value in before.items())


def test_identical_overlap_is_excluded(fixture):
    primary, _, output, frames = fixture
    path = primary / '2020/eurusd/2020-1h.parquet'
    same = frames['eurusd'].iloc[[0]].reset_index()
    same['available_at'] = same.timestamp + pd.Timedelta(hours=1)
    pd.concat([same, pd.read_parquet(path)], ignore_index=True).to_parquet(path, index=False)
    report = build(fixture)
    assert report['pairs']['eurusd']['candidate_rows'] == 39
    assert report['pairs']['eurusd']['identical_overlap_rows'] == 1
    assert len(pd.read_parquet(output / 'eurusd-2020-boundary-candidate.parquet')) == 39


@pytest.mark.parametrize('column', ['BidClose', 'AskOpen', 'available_at'])
def test_conflicting_overlap_rejected_before_output(fixture, column):
    primary, _, output, frames = fixture
    conflict = frames['eurusd'].iloc[[0]].reset_index()
    conflict['available_at'] = conflict.timestamp + pd.Timedelta(hours=1)
    conflict.loc[0, column] += pd.Timedelta(hours=1) if column == 'available_at' else .001
    conflict.to_parquet(primary / '2020/eurusd/2020-1h.parquet', index=False)
    with pytest.raises(ValueError, match='CONFLICTING_OVERLAP'):
        build(fixture)
    assert not output.exists()


@pytest.mark.parametrize('kind', ['raw_tamper', 'wrong_pair', 'forged_manifest', 'wrong_url'])
def test_authentication_rejects_bad_source(fixture, kind):
    _, evidence, output, _ = fixture
    public = evidence / 'public_evidence'
    raw = public / 'eurusd-2019-53.csv.gz'
    path = public / 'fetch_manifest.json'
    manifest = json.loads(path.read_text())
    if kind in ('raw_tamper', 'forged_manifest'):
        raw.write_bytes(raw.read_bytes() + b'x')
    elif kind == 'wrong_pair':
        raw.write_bytes((public / 'gbpusd-2019-53.csv.gz').read_bytes())
    else:
        manifest[raw.name]['url'] = manifest['gbpusd-2019-53.csv.gz']['url']
    if kind in ('wrong_pair', 'forged_manifest'):
        manifest[raw.name].update(sha256=sha(raw), bytes=raw.stat().st_size)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='SOURCE_AUTHENTICATION'):
        build(fixture)
    assert not output.exists()


@pytest.mark.parametrize('change', ['out_of_range', 'nonhourly', 'missing_hour'])
def test_date_support_rejected_without_filling(parser, fixture, change):
    source = fixture[3]['eurusd'].copy()
    if change == 'missing_hour':
        source = source.iloc[:-1]
    else:
        index = list(source.index)
        index[0] = pd.Timestamp('2019-12-31T06:00Z') if change == 'out_of_range' else index[0] + pd.Timedelta(minutes=1)
        source.index = pd.DatetimeIndex(index, name='timestamp')
    with pytest.raises(ValueError, match='BOUNDARY_SUPPORT|NONHOURLY'):
        module.validate_source(source)


def test_existing_output_is_never_changed(fixture):
    output = fixture[2]
    output.mkdir()
    marker = output / 'user-file'
    marker.write_text('unchanged')
    with pytest.raises(FileExistsError):
        build(fixture)
    assert marker.read_text() == 'unchanged' and len(list(output.iterdir())) == 1


def test_missing_baseline_is_not_treated_as_missing_quotes(fixture):
    (fixture[0] / '2024/eurusd/2024-1h.parquet').unlink()
    with pytest.raises(FileNotFoundError):
        build(fixture)
    assert not fixture[2].exists()


def test_input_output_roots_cannot_overlap(fixture):
    primary, evidence, _, _ = fixture
    with pytest.raises(ValueError, match='OUTPUT_OVERLAPS_INPUT'):
        module.build(Path(os.environ['PREDICTOR_ROOT']), primary, evidence, primary / 'patch')


def test_production_pair_hashes_are_distinct():
    assert module.SOURCE_SHA256 == {
        'eurusd': 'f8fc2ef1c558eb4b73759886222df9c0ef9b60803a94b36442d67d3446c961e7',
        'gbpusd': 'fc0875b0e27323b59a8dc4dd2043457588521d09d99aea73af4258398e3ccfc0',
    }


def test_manifest_fsync_precedes_atomic_rename(tmp_path, monkeypatch):
    events = []
    real_sync, real_replace = module.os.fsync, module.os.replace

    def sync(fd):
        events.append('fsync')
        real_sync(fd)

    def replace(source, target):
        assert events == ['fsync']
        assert not target.exists()
        assert json.loads(source.read_text()) == {'admitted': False}
        events.append('rename')
        real_replace(source, target)

    monkeypatch.setattr(module.os, 'fsync', sync)
    monkeypatch.setattr(module.os, 'replace', replace)
    module.write_manifest(tmp_path, {'admitted': False})
    assert events == ['fsync', 'rename', 'fsync']
    assert len(list(tmp_path.iterdir())) == 1


def test_interrupted_manifest_never_becomes_completion_marker(tmp_path, monkeypatch):
    def fail(*args):
        raise OSError('simulated rename failure')

    monkeypatch.setattr(module.os, 'replace', fail)
    with pytest.raises(OSError, match='simulated'):
        module.write_manifest(tmp_path, {'admitted': False})
    assert not (tmp_path / 'MANIFEST.json').exists()
    with pytest.raises(FileNotFoundError):
        module.status(tmp_path)


def test_status_read_only_and_uses_receipt_identity(fixture, monkeypatch):
    build(fixture)
    output = fixture[2]
    manifest = output / 'MANIFEST.json'
    receipt = json.loads(manifest.read_text())
    receipt['builder_sha256'] = 'old-code-identity'
    manifest.write_text(json.dumps(receipt))
    before = {p: (sha(p), p.stat().st_mtime_ns) for p in output.iterdir()}

    def forbidden(*args, **kwargs):
        pytest.fail('status must not load predictor, write, or access network')

    monkeypatch.setattr(module, 'load_parser', forbidden)
    monkeypatch.setattr(module, 'write_manifest', forbidden)
    import socket
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    report = module.status(output)
    assert report['state'] == 'NOT_ADMITTED' and not report['admitted']
    assert report['builder_sha256'] == 'old-code-identity'
    assert report['candidate_rows'] == {'eurusd': 40, 'gbpusd': 40}
    assert {p: (sha(p), p.stat().st_mtime_ns) for p in output.iterdir()} == before


@pytest.mark.parametrize('damage', ['truncated_manifest', 'tampered_output', 'wrong_count', 'unsafe_path'])
def test_status_rejects_damaged_receipt_or_candidate(fixture, damage):
    build(fixture)
    output = fixture[2]
    manifest = output / 'MANIFEST.json'
    if damage == 'truncated_manifest':
        manifest.write_text('{"admitted": false,')
    elif damage == 'tampered_output':
        path = output / 'eurusd-2020-boundary-candidate.parquet'
        path.write_bytes(path.read_bytes() + b'tampered')
    else:
        body = json.loads(manifest.read_text())
        field = 'candidate_rows' if damage == 'wrong_count' else 'candidate_file'
        body['pairs']['eurusd'][field] = 39 if damage == 'wrong_count' else '../outside.parquet'
        manifest.write_text(json.dumps(body))
    with pytest.raises(ValueError, match='MANIFEST|CANDIDATE'):
        module.status(output)


def test_status_cli_requires_only_output_root(fixture):
    build(fixture)
    completed = subprocess.run([sys.executable, str(SCRIPT), '--status', '--output-root', str(fixture[2])],
                               capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)['state'] == 'NOT_ADMITTED'


def test_status_missing_root_does_not_create_it(tmp_path):
    missing = tmp_path / 'absent'
    with pytest.raises(FileNotFoundError):
        module.status(missing)
    assert not missing.exists()
