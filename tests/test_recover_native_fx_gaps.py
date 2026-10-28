import importlib.util
import json
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location('recover_native_fx_gaps',Path(__file__).parents[1]/'_scripts/recover_native_fx_gaps.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def inputs(root):
    for pair in ('eurusd','gbpusd'):
        (root/f'QUALITY.{pair}.json').write_text(json.dumps({'admitted':False,'months':[
            {'missing_timestamps':['2023-07-03T12:00:00+00:00','2023-07-03T13:00:00+00:00']}]}))


def test_waits_without_making_network_calls(tmp_path):
    r=module.run_pass(tmp_path,lambda *_:pytest.fail('not ready'))
    assert r['state']=='WAIT_SOURCE_QUALITY'


def test_dates_are_deduplicated_with_adjacent_overlap_and_no_time_guess():
    dates=module.dates_from_quality([{'months':[{'missing_timestamps':['2023-07-03T23:00Z','2023-07-03T12:00Z']}]}])
    assert dates==['2023-07-02','2023-07-03','2023-07-04']


def test_batches_advance_without_supervision_and_resume_does_not_redownload(tmp_path):
    inputs(tmp_path);calls=[]
    def executor(dates):
        calls.append(dates)
        return {'state':'ACQUIRED','complete':len(dates),'failures':[]}
    r=module.run_pass(tmp_path,executor)
    assert len(calls)==1 and r['state']=='CANDIDATES_ACQUIRED_CLOCK_NOT_ADMITTED'
    assert r['admitted'] is False
    module.run_pass(tmp_path,lambda *_:pytest.fail('completed batch reran'))


def test_provider_cooldown_blocks_all_later_calls(tmp_path):
    inputs(tmp_path)
    r=module.run_pass(tmp_path,lambda *_:{'state':'RATE_LIMITED','retry_not_before_epoch':2000},now=lambda:1000)
    assert r['state']=='WAIT_PROVIDER'
    r=module.run_pass(tmp_path,lambda *_:pytest.fail('cooldown ignored'),now=lambda:1100)
    assert r['state']=='WAIT_PROVIDER'


def test_changed_quality_cannot_reuse_old_recovery_identity(tmp_path):
    inputs(tmp_path);module.run_pass(tmp_path,lambda *_:{'state':'ACQUIRED','complete':3,'failures':[]})
    p=tmp_path/'QUALITY.eurusd.json';q=json.loads(p.read_text());q['months'][0]['missing_timestamps']=['2023-07-04T12:00Z'];p.write_text(json.dumps(q))
    with pytest.raises(ValueError,match='GAP_SOURCE_IDENTITY_CHANGED'):
        module.run_pass(tmp_path,lambda *_:pytest.fail('wrong identity'))
