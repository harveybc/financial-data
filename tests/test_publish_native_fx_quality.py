import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('publish_native_fx_quality',Path(__file__).parents[1]/'_scripts/publish_native_fx_quality.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def quality():
    return dict(schema='financial_data.native_fx_quality.v1',admitted=False,
        quote_view='BID',interpolated_values=0,source_sha256={'2023/eurusd/2023-1h.parquet':'a'*64},
        calendar_basis='ASSUMED_NY',observed_rows=100,missing_expected_open_hours=2,
        identical_duplicates_removed=0,outside_assumed_open_schedule_rows=1,crossed_side_bar_endpoints=3,
        months=[dict(month='2023-01',observed_rows=100,expected_open_hours=102,missing_expected_open_hours=2)],
        return_outliers={'state':'NOT_ESTIMABLE','count':None,'reference':{'n':0,'median':None,'mad':None}})


def test_report_is_quality_not_forecasting_and_preserves_undefined_outliers():
    r=module.build_report('eurusd',quality(),'b'*64,'code-revision')
    assert r['project']=='financial-data' and r['phase']=='NATIVE_SOURCE_QUALITY'
    assert r['lineage']=='UNVERIFIED' and r['tags']['admission']=='NOT_ADMITTED'
    assert r['tags']['outlier_state']=='NOT_ESTIMABLE'
    rows={x['metric']:x for x in r['metrics']}
    assert rows['coverage.2023-01.observed_rows']['split']=='train'
    assert rows['return_outlier_count']['value'] is None
    assert all('MAE' not in m['metric'] for m in r['metrics'])
    assert '://' not in json.dumps(r) and '/home/' not in json.dumps(r)


@pytest.mark.parametrize('change',[{'admitted':True},{'interpolated_values':1},{'quote_view':'PAIRED'}, {'schema':'old-experiment'}])
def test_no_relabeling_of_admitted_interpolated_or_old_experiment_data(change):
    q=quality();q.update(change)
    with pytest.raises(ValueError):module.build_report('eurusd',q,'b'*64,'code')


def test_actual_source_digest_checked_and_path_escape_rejected(tmp_path):
    p=tmp_path/'2023/eurusd/2023-1h.parquet';p.parent.mkdir(parents=True);p.write_bytes(b'observed')
    q=quality();q['source_sha256']={str(p.relative_to(tmp_path)):module.file_sha(p)}
    module.verify_sources(q,tmp_path)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError,match='SOURCE_DIGEST'):module.verify_sources(q,tmp_path)
    q['source_sha256']={'../outside.parquet':'a'*64}
    with pytest.raises(ValueError,match='SOURCE_PATH'):module.verify_sources(q,tmp_path)


def test_new_quality_identity_changes_when_source_or_metrics_change():
    a=module.build_report('eurusd',quality(),'b'*64,'code')
    q=quality();q['observed_rows']=101
    b=module.build_report('eurusd',q,'b'*64,'code')
    assert a['experiment_key']!=b['experiment_key']
    assert module.build_report('eurusd',quality(),'b'*64,'code')==a


def test_real_governed_schema_physical_readback_and_closed_copy(tmp_path):
    import os
    import sys
    pytest.importorskip('duckdb')
    runtime=os.environ.get('PREDICTOR_CURATION_RUNTIME')
    if not runtime:pytest.skip('requires the declared predictor runtime')
    sys.path.insert(0,runtime)
    from tools.i6dmo.outbox import seal_report,expected_rows
    report=seal_report(module.build_report('eurusd',quality(),'b'*64,'code'))
    assert len(expected_rows(report))==12
    source=tmp_path/'native.duckdb'
    sha=module.snapshot(source,[report])
    assert module.snapshot(source,[report])==sha
    assert module.copy_closed(source,tmp_path/'copy.duckdb')==sha
