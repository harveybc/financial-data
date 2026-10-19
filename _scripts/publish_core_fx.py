"""Publish scoped core admission evidence using the existing metrics outbox."""
import argparse
import json
from pathlib import Path
import sys

from publish_native_fx_quality import copy_closed, file_sha, mirror_closed, snapshot, write_json
from publish_consolidated_fx import verify_pinned


def build_report(receipt, admission_sha, code_commit):
    if (receipt.get('status') != 'ADMITTED' or receipt.get('admitted') is not True
            or receipt.get('scope') != 'CORE_PRICES_ONLY' or set(receipt['pairs']) != {'eurusd'}):
        raise ValueError('SCOPED_CORE_ADMISSION_REQUIRED')
    item = receipt['pairs']['eurusd']
    metrics = [dict(metric=k, value=item[k], unit='hour_bar_count', split='quality', horizon=None)
               for k in ('rows', 'missing_required_operating_hours', 'coherent_source_rows', 'fallback_rows')]
    metrics += [dict(metric=f'coverage.{month}.observed_rows', value=n,
                    unit='hour_bar_count', split='quality', horizon=None)
                for month, n in sorted(item['monthly_rows'].items())]
    return dict(experiment_key='core-fx-admission:eurusd:'+admission_sha,
        experiment_set_key='canonical-native-fx-recovery', actor='canonical-data-curation',
        lake='curated-core-prices', lineage='VERIFIED', project='financial-data',
        phase='CORE_PRICE_ADMISSION', config_sha256=receipt['binding']['calendar_sha256'],
        code_commit=code_commit, tags=dict(kind='core_price_admission', pair='eurusd',
            scope='CORE_PRICES_ONLY', feature_selection_complete='false',
            global_venue_calendar_certified='false', model_training='false',
            admission_sha256=admission_sha, calendar_scope='DECLARED_CONSERVATIVE_BUSINESS_OPERATING_CALENDAR'),
        datasets=[dict(lake='curated-core-prices', resource=item['file'], sha256=item['sha256'],
                       role='core_price_reference', lineage='VERIFIED', reason='Scoped owner admission')],
        metrics=metrics)


def main():
    p = argparse.ArgumentParser(__doc__)
    for name in ('admission-root', 'root', 'predictor-root', 'local-copy'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('code-commit', 'warehouse-url', 'mirror-host', 'mirror-relative-path'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--token-env', default='DATA_GOV_LAKE_TOKEN')
    a = p.parse_args()
    source, root = a.admission_root.resolve(), a.root.resolve()
    repo = Path(__file__).resolve().parents[1]
    verify_pinned(repo, a.code_commit, ('_scripts/admit_core_fx.py', '_scripts/publish_core_fx.py'))
    if root.is_relative_to(source) or root.is_relative_to(repo):
        raise ValueError('SEPARATE_OPERATIONAL_ROOT_REQUIRED')
    receipt_path = source/'ADMISSION.json'
    admission_sha = file_sha(receipt_path)
    receipt = json.loads(receipt_path.read_text())
    if json.loads((source/'STATUS.json').read_text()) != receipt:
        raise ValueError('ADMISSION_STATUS_MISMATCH')
    if (file_sha(repo/'_scripts/admit_core_fx.py') != receipt['binding']['code_sha256']
            or file_sha(source/'CALENDAR.json') != receipt['binding']['calendar_sha256']
            or file_sha(source/receipt['closure_intervals_file']) != receipt['closure_intervals_sha256']):
        raise ValueError('ADMISSION_EVIDENCE_DRIFT')
    for item in receipt['pairs'].values():
        for field, pin in [('file', 'sha256'), ('quality_file', 'quality_sha256')]:
            path = source/item[field]
            if path.resolve().parent != source or file_sha(path) != item[pin]:
                raise ValueError('ADMITTED_SOURCE_DRIFT')
    sys.path.insert(0, str(a.predictor_root.resolve()))
    from tools.i6dmo.outbox import HttpWarehouse, Outbox
    root.mkdir(parents=True, exist_ok=True)
    box = Outbox(root/'core-admission-outbox.sqlite')
    try:
        box.enqueue(build_report(receipt, admission_sha, a.code_commit), source_unit='core-eurusd-admission')
        delivery = box.pump(HttpWarehouse(a.warehouse_url, a.token_env))
        reports = [json.loads(row['body']) for row in box.items()]
        physical = root/'core-admission.duckdb'
        sha = snapshot(physical, reports)
        if copy_closed(physical, a.local_copy) != sha:
            raise ValueError('LOCAL_MIRROR_MISMATCH')
        mirror = mirror_closed(physical, a.mirror_host, a.mirror_relative_path)
        if file_sha(receipt_path) != admission_sha:
            raise ValueError('ADMISSION_CHANGED_DURING_PUBLICATION')
        ok = delivery['delivered'] == 1 and delivery['pending'] == delivery['mismatch'] == 0
        write_json(root/'PUBLICATION_STATUS.json', dict(state='CORE_ADMISSION_PUBLISHED' if ok else 'PUBLICATION_PENDING',
            scope='CORE_PRICES_ONLY', feature_selection_complete=False, warehouse=delivery,
            physical_sha256=sha, second_machine=mirror))
        print(json.dumps(dict(state='CORE_ADMISSION_PUBLISHED' if ok else 'PUBLICATION_PENDING', warehouse=delivery)))
        return 0 if ok else 2
    finally:
        box.close()


if __name__ == '__main__':
    raise SystemExit(main())
