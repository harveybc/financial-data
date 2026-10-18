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
