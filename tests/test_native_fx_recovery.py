import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

spec=importlib.util.spec_from_file_location('native_fx_recovery',Path(__file__).parents[1]/'_scripts/native_fx_recovery.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def quotes(times,close=None):
    index=pd.to_datetime(times,utc=True)
    close=close if close is not None else [1.1]*len(index)
    return pd.DataFrame({'timestamp':index,'BidOpen':close,'BidHigh':close,
        'BidLow':close,'BidClose':close,'AskOpen':[v+.0001 for v in close],
        'AskHigh':[v+.0001 for v in close],'AskLow':[v+.0001 for v in close],
        'AskClose':[v+.0001 for v in close],'available_at':index+pd.Timedelta(hours=1)})


def config():
    value=json.loads((Path(__file__).parents[1]/'configs/native_fx_recovery.v1.json').read_text())
    value.update(required_start='2023-01-01T00:00:00Z',required_end_exclusive='2024-01-01T00:00:00Z')
    return value


def test_contract_forbids_fill_admission_and_incomplete_week_inventory():
    assert module.validate(config())['pairs']==['eurusd','gbpusd']
    for key in ('interpolation','price_fill','admit_to_lake'):
        c=config();c[key]=True
        with pytest.raises(ValueError):module.validate(c)
    c=config();c['weeks']=list(range(1,53))
    with pytest.raises(ValueError,match='WEEK_INVENTORY'):module.validate(c)


def test_monthly_denominator_exposes_wholly_missing_month_and_never_admits():
    frame=quotes(['2023-01-03T12:00Z','2023-03-01T12:00Z'])
    r=module.audit(frame,config())
    feb=next(m for m in r['months'] if m['month']=='2023-02')
    assert feb['observed_rows']==0 and feb['missing_expected_open_hours']>400
    assert not r['admitted'] and r['interpolated_values']==0
    assert r['outlier_reference']=='TRAIN_ONLY'
    assert r['return_outliers']['state']=='NOT_ESTIMABLE'


def test_weekend_closure_is_not_counted_as_missing_and_current_bar_stays():
    c=config();c.update(required_start='2023-01-06T21:00:00Z',required_end_exclusive='2023-01-09T00:00:00Z')
    r=module.audit(quotes(['2023-01-06T21:00Z','2023-01-08T22:00Z','2023-01-08T23:00Z']),c)
    assert r['months'][0]['missing_expected_open_hours']==0
    assert r['months'][0]['expected_open_hours']==3
    assert r['months'][0]['observed_rows']==3


def test_conflicting_duplicates_and_false_availability_are_rejected():
    frame=quotes(['2023-01-03T12:00Z','2023-01-03T12:00Z'],[1.1,1.2])
    with pytest.raises(ValueError,match='CONFLICTING_DUPLICATE'):module.audit(frame,config())
    frame=quotes(['2023-01-03T12:00Z']);frame.loc[0,'available_at']=frame.loc[0,'timestamp']
    with pytest.raises(ValueError,match='AVAILABILITY'):module.audit(frame,config())


def test_identical_boundary_rows_count_once_and_outlier_fit_ignores_later_data():
    c=config();c.update(required_end_exclusive='2025-01-01T00:00:00Z')
    train=quotes(pd.date_range('2023-01-03T00:00Z',periods=10,freq='h'),
        [1.1,1.1001,1.1003,1.1004,1.1008,1.1006,1.1007,1.1009,1.101,1.1012])
    later=quotes(['2024-01-03T00:00Z','2024-01-03T01:00Z'],[1.1,1.9])
    a=module.audit(pd.concat([train,train.iloc[[0]],later]),c)
    later=quotes(['2024-01-03T00:00Z','2024-01-03T01:00Z'],[1.1,9.9])
    b=module.audit(pd.concat([train,later]),c)
    assert a['identical_duplicates_removed']==1
    assert a['return_outliers']['reference']==b['return_outliers']['reference']


def test_read_only_status_never_creates_directories(tmp_path):
    missing=tmp_path/'absent'
    with pytest.raises(FileNotFoundError):module.status(missing)
    assert not missing.exists()


def test_stopped_controller_never_reports_running_eta(tmp_path):
    body={'state':'RUNNING','controller_pid':999999999,'controller_process_token':'absent','eta_seconds':10}
    path=tmp_path/'STATUS.json';path.write_text(json.dumps(body));before=path.read_bytes()
    assert module.status(tmp_path)['state']=='INTERRUPTED'
    assert module.status(tmp_path)['eta_seconds'] is None
    assert path.read_bytes()==before


def test_missing_mount_cannot_fall_back_to_local_filesystem(tmp_path,monkeypatch):
    class Result:
        stdout=json.dumps({'filesystems':[{'fstype':'ext4','options':'rw'}]})
    monkeypatch.setattr(module.subprocess,'run',lambda *a,**k:Result())
    c=config();c['minimum_memory_available_bytes']=0
    with pytest.raises(RuntimeError,match='STORAGE_FILESYSTEM_MISMATCH'):
        module.resource_check(tmp_path,c)


def test_batch_retries_partial_download_then_advances_all_years(tmp_path):
    c=config();c['required_end_exclusive']='2025-01-01T00:00:00Z';c['retry_wait_seconds']=0
    root=tmp_path/'state';out=tmp_path/'bulk';calls=[]
    def executor(year,attempt):
        calls.append((year,attempt))
        return 2 if attempt==1 else 0
    result=module.run_jobs(root,out,c,executor,sleep=lambda _:None)
    assert calls==[(2023,1),(2023,2),(2024,1),(2024,2)]
    assert result['completed_years']==2 and result['admitted'] is False
    assert result['state']=='ACQUISITION_FINISHED_REQUIRES_DATA_VALIDATION'
    module.run_jobs(root,out,c,lambda *_:pytest.fail('completed year reran'),sleep=lambda _:None)


def test_batch_resume_rejects_changed_configuration_and_persists_failure(tmp_path):
    c=config();c['retry_wait_seconds']=0
    root=tmp_path/'state';out=tmp_path/'bulk'
    r=module.run_jobs(root,out,c,lambda *_:2,sleep=lambda _:None)
    assert r['state']=='INCOMPLETE_SOURCE_RECOVERY' and r['failed_years']==1
    c['pairs']=['eurusd']
    with pytest.raises(ValueError,match='RECOVERY_IDENTITY_CHANGED'):
        module.run_jobs(root,out,c,lambda *_:0,sleep=lambda _:None)
