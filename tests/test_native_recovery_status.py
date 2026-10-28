import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('native_recovery_status',Path(__file__).parents[1]/'_scripts/native_recovery_status.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def put(path,body):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(body))


def test_absent_state_is_read_only_and_never_calls_it_complete(tmp_path):
    root=tmp_path/'missing';r=module.snapshot(root)
    assert r['state']=='NOT_INITIALIZED' and not root.exists()
    assert r['data_admission_complete'] is False


def test_failed_year_is_not_reported_as_zero_available_source_files(tmp_path):
    put(tmp_path/'STATUS.json',{'state':'RECOVERY_AWAITING_CLOCK_CALENDAR_AND_GAP_ACCEPTANCE',
        'output':str(tmp_path/'bulk'),'jobs':[{'year':2023,'state':'FAILED'}]})
    put(tmp_path/'bulk/2023/STATUS.json',{'total':3,'complete':2,'failures':[{}]})
    r=module.snapshot(tmp_path)
    assert r['native']['years_processed']==1
    assert r['native']['available_week_files']==2
    assert r['native']['unavailable_week_files']==1
    assert r['native']['requested_week_files']==3


def test_candidate_days_count_once_across_retries_and_are_not_repaired_hours(tmp_path):
    put(tmp_path/'STATUS.json',{'state':'DONE','output':str(tmp_path/'bulk'),'jobs':[]})
    day={'date':'2023-07-03','observations':{'EURUSD':10,'GBPUSD':11}}
    put(tmp_path/'GAP_RECOVERY_PLAN.json',{'requested_dates':['2023-07-03','2023-07-04'],
        'batches':[{'state':'UNAVAILABLE_AFTER_ATTEMPTS','attempts':[
            {'result':{'results':[day]}},{'result':{'results':[day]}}]}]})
    r=module.snapshot(tmp_path)
    assert r['alternative']['available_native_dates']==1
    assert r['alternative']['candidate_minute_observations']=={'EURUSD':10,'GBPUSD':11}
    assert r['alternative']['hours_verified_as_repaired'] is None


def test_quality_and_publication_never_confer_lake_admission(tmp_path):
    put(tmp_path/'STATUS.json',{'state':'DONE','output':str(tmp_path/'bulk'),'jobs':[]})
    put(tmp_path/'QUALITY.eurusd.json',{'observed_rows':100,'missing_expected_open_hours':2,'admitted':False})
    put(tmp_path/'PUBLICATION_STATUS.json',{'state':'QUALITY_PUBLISHED_NOT_ADMITTED',
        'warehouse':{'expected':2,'delivered':2,'pending':0,'mismatch':0},'physical_sha256':'a'*64,
        'second_machine':{'sha256':'a'*64}})
    r=module.snapshot(tmp_path)
    assert r['publication']['warehouse']['delivered']==2
    assert r['data_admission_complete'] is False and r['feature_selection_complete'] is False
    assert r['native_quality']['eurusd']['missing_expected_open_hours']==2


def test_unavailable_dates_show_weekdays_without_certifying_closures(tmp_path):
    put(tmp_path/'GAP_RECOVERY_PLAN.json',{'requested_dates':['2020-01-04','2020-12-25'],
        'batches':[{'attempts':[{'result':{'failures':[
            {'date':'2020-01-04','reason':'NO_REQUIRED_PAIRS'},
            {'date':'2020-12-25','reason':'NO_REQUIRED_PAIRS'}]}}]}]})
    r=module.snapshot(tmp_path)
    details=r['alternative']['unavailable_date_diagnostics']
    assert details[0]['weekday']=='Saturday'
    assert details[1]['weekday']=='Friday'
    assert all(d['calendar_disposition']=='UNVERIFIED' for d in details)


def test_supplementary_correction_and_consolidation_are_visible_without_admission(tmp_path, monkeypatch):
    import sys
    import types
    put(tmp_path/'SUPPLEMENTARY_ROOTS.json', dict(schema='financial_data.supplementary_roots.v1',
        histdata_corrected=str(tmp_path/'corrected'), observations_consolidated=str(tmp_path/'consolidated')))
    monkeypatch.setitem(sys.modules, 'normalize_histdata_observed_clock', types.SimpleNamespace(
        status=lambda p: dict(state='CLOCK_CORRECTED_COMPLETE_HOUR_CANDIDATES', clock_verified=True,
                              files=[dict(rows=60), dict(rows=120)])))
    monkeypatch.setitem(sys.modules, 'consolidate_fx_observations', types.SimpleNamespace(
        status=lambda p: dict(state='OBSERVATIONS_CONSOLIDATED_REQUIRES_CALENDAR_AND_COVERAGE',
            pairs={'eurusd': dict(rows=100, missing_expected_open_hours=2,
                                  observations_excluded_by_closed_weekly_schedule=1)})))
    before = sorted(str(p) for p in tmp_path.rglob('*'))
    result = module.snapshot(tmp_path)
    assert result['histdata_corrected']['clock_verified'] is True
    assert result['histdata_corrected']['complete_hours'] == 180
    assert result['observations_consolidated']['pairs']['eurusd']['missing_expected_open_hours'] == 2
    assert result['state'] == 'RECOVERING_REMAINING_OBSERVATIONS_AND_CALENDAR'
    assert result['data_admission_complete'] is False
    assert sorted(str(p) for p in tmp_path.rglob('*')) == before


def test_changed_supplementary_outputs_report_unavailable_not_complete(tmp_path, monkeypatch):
    import sys
    import types
    put(tmp_path/'SUPPLEMENTARY_ROOTS.json', dict(schema='financial_data.supplementary_roots.v1',
        histdata_corrected=str(tmp_path/'corrected')))
    def changed(path):
        raise ValueError('NORMALIZED_OUTPUT_CHANGED')
    monkeypatch.setitem(sys.modules, 'normalize_histdata_observed_clock', types.SimpleNamespace(status=changed))
    result = module.snapshot(tmp_path)
    assert result['histdata_corrected']['state'] == 'UNAVAILABLE'
    assert result['histdata_corrected']['error_type'] == 'ValueError'
    assert 'clock_verified' not in result['histdata_corrected']
