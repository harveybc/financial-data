import importlib.util
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

SCRIPTS = Path(__file__).parents[1] / '_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('clock_publication', SCRIPTS / 'publish_forexite_clock.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def evidence(tmp_path):
    source = tmp_path / 'source.html'
    source.write_text('synthetic provider clock evidence')
    contract = tmp_path / 'contract.json'
    contract.write_text(json.dumps({
        'schema': 'financial_data.forexite_metastock_clock.v1',
        'status': 'CLOCK_VERIFIED_QUOTE_SIDE_AND_BAR_LABEL_UNRESOLVED',
        'timezone': 'Europe/Berlin', 'source_sha256': module.sha(source)}))
    native, output = tmp_path / 'native', tmp_path / 'normalized'
    native.mkdir()
    pd.DataFrame({'timestamp_native': ['2023-07-03 12:00'], 'CLOSE': [1.1]}).to_parquet(native / 'day.parquet')
    module.normalize_run(native, output, contract, source)
    return native, output, contract, source


def test_report_preserves_narrow_scope_and_verifies_real_files(evidence):
    report = module.build_verified_report(*evidence, 'abc123')
    values = {m['metric']: m['value'] for m in report['metrics']}
    assert values['rows'] == 1
    assert values['clock_verified'] == 1
    assert values['admitted'] == values['quote_side_verified'] == values['bar_label_verified'] == 0
    assert len(report['datasets']) == 4


@pytest.mark.parametrize('field,value', [('rows', 9), ('completed_files', 2),
                                        ('admitted', True), ('clock_verified', False),
                                        ('code_sha256', '0' * 64)])
def test_forged_summary_cannot_be_published(evidence, field, value):
    path = evidence[1] / 'STATUS.json'
    body = json.loads(path.read_text())
    body[field] = value
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError):
        module.build_verified_report(*evidence, 'abc123')


@pytest.mark.parametrize('which', [0, 1])
def test_changed_candidate_or_output_cannot_be_published(evidence, which):
    (evidence[which] / 'day.parquet').write_bytes(b'changed')
    with pytest.raises(ValueError, match='DIGEST'):
        module.build_verified_report(*evidence, 'abc123')


def test_unsafe_manifest_path_is_rejected(evidence):
    path = evidence[1] / 'STATUS.json'
    body = json.loads(path.read_text())
    body['files'][0]['name'] = '../day.parquet'
    path.write_text(json.dumps(body))
    with pytest.raises(ValueError, match='FILE_NAME'):
        module.build_verified_report(*evidence, 'abc123')
