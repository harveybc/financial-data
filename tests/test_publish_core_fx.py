import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).parents[1]/'_scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('core_publish', SCRIPTS/'publish_core_fx.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_core_report_preserves_partial_scope_and_monthly_counts():
    receipt = dict(status='ADMITTED', admitted=True, scope='CORE_PRICES_ONLY',
        binding=dict(calendar_sha256='a'*64), pairs=dict(eurusd=dict(rows=3,
            missing_required_operating_hours=0, coherent_source_rows=2, fallback_rows=1,
            file='eurusd.parquet', sha256='b'*64, monthly_rows={'2024-01': 3})))
    report = module.build_report(receipt, 'c'*64, 'd'*40)
    assert report['tags']['feature_selection_complete'] == 'false'
    assert report['tags']['global_venue_calendar_certified'] == 'false'
    assert report['tags']['model_training'] == 'false'
    assert {m['metric']: m['value'] for m in report['metrics']}['coverage.2024-01.observed_rows'] == 3


def test_non_admission_cannot_publish_as_admitted():
    with pytest.raises(ValueError, match='CORE_ADMISSION'):
        module.build_report(dict(status='PREPARING'), 'c'*64, 'd'*40)
