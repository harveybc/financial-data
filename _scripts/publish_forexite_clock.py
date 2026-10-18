"""Publish verified clock-only evidence through the existing governed outbox."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from normalize_forexite_clock import run as normalize_run, sha, verify_contract
from publish_native_fx_quality import copy_closed, mirror_closed, snapshot, write_json


def build_verified_report(native, normalized, contract_path, source, code_commit):
    native, normalized = Path(native).resolve(), Path(normalized).resolve()
    contract = json.loads(Path(contract_path).read_text())
    verify_contract(contract, source)
    receipt = json.loads((normalized / 'STATUS.json').read_text())
    if (receipt.get('schema') != 'financial_data.forexite_clock_normalization.v1'
            or receipt.get('state') != 'CLOCK_NORMALIZED_NOT_ADMITTED'
            or receipt.get('admitted') is not False or receipt.get('clock_verified') is not True
            or receipt.get('quote_side') != 'UNRESOLVED'
            or receipt.get('minute_bar_label') != 'UNRESOLVED_START_OR_END'):
        raise ValueError('CLOCK_ONLY_COMPLETED_RECEIPT_REQUIRED')
    if (receipt['contract_sha256'] != sha(contract_path)
            or receipt['source_sha256'] != sha(source)
            or receipt['code_sha256'] != sha(Path(__file__).with_name('normalize_forexite_clock.py'))):
        raise ValueError('EVIDENCE_OR_CODE_DIGEST_MISMATCH')
    datasets = []
    def add(name, digest, role):
        datasets.append(dict(lake='acquisition-not-admitted', resource=name, sha256=digest,
                             role=role, lineage='UNVERIFIED', reason='Clock-only evidence; no admission'))
    add('provider-clock-page', sha(source), 'primary_provider_documentation')
    add('provider-clock-contract', sha(contract_path), 'reviewed_clock_contract')
    names, rows = set(), 0
    for item in receipt['files']:
        name = item['name']
        if not name or Path(name).name != name or name in names:
            raise ValueError('INVALID_OR_DUPLICATE_FILE_NAME')
        names.add(name)
        for base, field, role in ((native, 'source_sha256', 'native_candidate'),
                                  (normalized, 'output_sha256', 'clock_normalized_candidate')):
            path = (base / name).resolve()
            if not path.is_relative_to(base) or sha(path) != item[field]:
                raise ValueError('FILE_DIGEST_MISMATCH')
            if len(pd.read_parquet(path, columns=['timestamp_native'])) != item['rows']:
                raise ValueError('FILE_ROW_COUNT_MISMATCH')
            add(role + '/' + name, item[field], role)
        rows += item['rows']
    if (not names or receipt['expected_files'] != len(names)
            or receipt['completed_files'] != len(names) or receipt['rows'] != rows):
        raise ValueError('RECEIPT_COUNTS_MISMATCH')
    identity = sha(normalized / 'STATUS.json')
    values = dict(files=len(names), rows=rows, clock_verified=1, quote_side_verified=0,
                  bar_label_verified=0, admitted=0)
    return dict(experiment_key='forexite-clock-normalization:' + identity,
        experiment_set_key='canonical-native-fx-recovery', actor='canonical-data-curation',
        lake='acquisition-not-admitted', lineage='UNVERIFIED', project='financial-data',
        phase='PROVIDER_CLOCK_NORMALIZATION', config_sha256=sha(contract_path), code_commit=code_commit,
        tags=dict(kind='clock_only_evidence', admission='NOT_ADMITTED', model_training='false',
                  receipt_sha256=identity, timezone='Europe/Berlin'), datasets=datasets,
        metrics=[dict(metric=k, value=v, unit='count', split='quality', horizon=None)
                 for k, v in values.items()])


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--status', action='store_true')
    for name in ('native-root', 'normalized-root', 'contract', 'source-evidence', 'predictor-root',
                 'warehouse-url', 'code-commit', 'local-copy', 'mirror-host', 'mirror-relative-path'):
        parser.add_argument('--' + name)
    parser.add_argument('--token-env', default='DATA_GOV_LAKE_TOKEN')
    args = parser.parse_args()
    status = args.root / 'PUBLICATION_STATUS.json'
    if args.status:
        state = json.loads(status.read_text())
        print(json.dumps(state, indent=2))
        return 0 if state['state'] == 'CLOCK_EVIDENCE_PUBLISHED_NOT_ADMITTED' else 2
    if any(getattr(args, name) is None for name in ('native_root', 'normalized_root', 'contract',
            'source_evidence', 'predictor_root', 'warehouse_url', 'code_commit', 'local_copy',
            'mirror_host', 'mirror_relative_path')):
        parser.error('all publication arguments are required')
    # Keep queue/WAL on the coordinator filesystem, never the bulk NTFS volume.
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root / 'publication.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        box = None
        try:
            repo = Path(__file__).resolve().parents[1]
            for name in ('publish_forexite_clock.py', 'normalize_forexite_clock.py',
                         'publish_native_fx_quality.py'):
                pinned = subprocess.run(['git', '-C', str(repo), 'show',
                    args.code_commit + ':_scripts/' + name], capture_output=True, check=True).stdout
                if hashlib.sha256(pinned).hexdigest() != sha(repo / '_scripts' / name):
                    raise ValueError('PUBLICATION_CODE_NOT_PINNED')
            report = build_verified_report(args.native_root, args.normalized_root, args.contract,
                                           args.source_evidence, args.code_commit)
            sys.path.insert(0, str(Path(args.predictor_root).resolve()))
            from tools.i6dmo.outbox import HttpWarehouse, Outbox
            box = Outbox(args.root / 'clock-outbox.sqlite')
            box.enqueue(report, source_unit='forexite-clock-normalization')
            delivery = box.pump(HttpWarehouse(args.warehouse_url, args.token_env))
            reports = [json.loads(item['body']) for item in box.items()]
            physical = args.root / 'forexite_clock_quality.duckdb'
            digest = snapshot(physical, reports)
            if copy_closed(physical, args.local_copy) != digest:
                raise ValueError('LOCAL_MIRROR_MISMATCH')
            mirror = mirror_closed(physical, args.mirror_host, args.mirror_relative_path)
            complete = delivery['pending'] == delivery['mismatch'] == 0 and delivery['delivered'] == len(reports)
            state = dict(state='CLOCK_EVIDENCE_PUBLISHED_NOT_ADMITTED' if complete else 'PUBLICATION_PENDING',
                         admitted=False, warehouse=delivery, physical_sha256=digest, second_machine=mirror)
            write_json(status, state)
            return 0 if complete else 2
        except Exception as exc:
            write_json(status, dict(state='PUBLICATION_RETRY_PENDING', admitted=False,
                                    error_type=type(exc).__name__))
            raise
        finally:
            if box is not None:
                box.close()


if __name__ == '__main__':
    raise SystemExit(main())
