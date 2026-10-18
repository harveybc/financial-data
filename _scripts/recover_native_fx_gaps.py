"""Fetch actual alternative quotes for missing dates, without merging or filling."""
import argparse
from datetime import datetime,timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,body):
    temp=path.with_suffix('.partial')
    with temp.open('w') as f:
        json.dump(body,f,sort_keys=True,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def dates_from_quality(reports):
    days=set()
    for q in reports:
        for month in q['months']:
            for value in month['missing_timestamps']:
                day=datetime.fromisoformat(value.replace('Z','+00:00')).date()
                days.update((day+timedelta(days=n)).isoformat() for n in (-1,0,1))
    return sorted(days)


def run_pass(root,executor,now=time.time,source_code_sha=None):
    root=Path(root);paths=[root/f'QUALITY.{p}.json' for p in ('eurusd','gbpusd')]
    state_file=root/'GAP_RECOVERY_STATUS.json'
    if not all(p.is_file() for p in paths):
        result=dict(state='WAIT_SOURCE_QUALITY',admitted=False)
        if root.is_dir():write(state_file,result)
        return result
    reports=[json.loads(p.read_text()) for p in paths]
    if any(q.get('admitted') is not False for q in reports):raise ValueError('UNADMITTED_SOURCE_QUALITY_REQUIRED')
    dates=dates_from_quality(reports)
    identity=hashlib.sha256(json.dumps({'quality':[sha(p) for p in paths],
        'controller':sha(__file__),'fetcher':source_code_sha,'dates':dates},sort_keys=True).encode()).hexdigest()
    plan_file=root/'GAP_RECOVERY_PLAN.json'
    if plan_file.exists():
        plan=json.loads(plan_file.read_text())
        if plan['identity']!=identity:raise ValueError('GAP_SOURCE_IDENTITY_CHANGED')
    else:
        plan=dict(identity=identity,admitted=False,native_clock_preserved=True,requested_dates=dates,
            batches=[dict(dates=dates[i:i+14],attempts=[],state='PENDING') for i in range(0,len(dates),14)])
        write(plan_file,plan)
    if state_file.exists():
        old=json.loads(state_file.read_text())
        if old.get('state')=='WAIT_PROVIDER' and old['retry_not_before_epoch']>now():return old
    for batch in plan['batches']:
        if batch['state'] in ('COMPLETE','UNAVAILABLE_AFTER_ATTEMPTS'):continue
        while len(batch['attempts'])<2:
            attempt=dict(state='RUNNING',started_at=now());batch['attempts'].append(attempt)
            write(plan_file,plan)
            write(state_file,dict(state='RUNNING',admitted=False,controller_pid=os.getpid(),
                current_dates=batch['dates'],requested_dates=len(dates),
                completed_batches=sum(b['state']=='COMPLETE' for b in plan['batches'])))
            result=executor(batch['dates']);attempt.update(result=result,finished_at=now(),state=result['state'])
            if result['state']=='RATE_LIMITED':
                write(plan_file,plan)
                state=dict(state='WAIT_PROVIDER',admitted=False,retry_not_before_epoch=result['retry_not_before_epoch'])
                write(state_file,state);return state
            if result['state']=='ACQUIRED':batch['state']='COMPLETE';break
        if batch['state']!='COMPLETE':batch['state']='UNAVAILABLE_AFTER_ATTEMPTS'
        write(plan_file,plan)
    complete=sum(b['state']=='COMPLETE' for b in plan['batches'])
    state=dict(state='CANDIDATES_ACQUIRED_CLOCK_NOT_ADMITTED' if complete==len(plan['batches']) else 'PARTIAL_CANDIDATES_CLOCK_NOT_ADMITTED',
        admitted=False,identity=identity,requested_dates=len(dates),batches=len(plan['batches']),
        completed_batches=complete,unavailable_batches=len(plan['batches'])-complete)
    write(state_file,state)
    return state


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('command',choices=['run','status'])
    p.add_argument('--root',required=True);p.add_argument('--output');p.add_argument('--config')
    a=p.parse_args();root=Path(a.root)
    if a.command=='status':
        value=json.loads((root/'GAP_RECOVERY_STATUS.json').read_text())
        if value.get('state')=='RUNNING' and not Path(f"/proc/{value['controller_pid']}").exists():value['state']='INTERRUPTED'
        print(json.dumps(value,sort_keys=True));return
    if not root.is_dir():return
    if not a.output or not a.config:p.error('run requires --output and --config')
    script=Path(__file__).with_name('recover_forexite_observations.py')
    c=json.loads(Path(a.config).read_text())
    with (root/'gap-recovery.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def execute(dates):
            from native_fx_recovery import resource_check
            resource_check(a.output,c)
            command=[sys.executable,'-B',str(script),'--output',a.output,'--dates',*dates]
            try:
                rc=subprocess.run(command,timeout=900,env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')).returncode
            except subprocess.TimeoutExpired:rc=124
            path=Path(a.output)/'STATUS.json'
            if not path.is_file():return dict(state='INCOMPLETE',returncode=rc,reason='ABSENT_SOURCE_STATUS')
            body=json.loads(path.read_text())
            if body.get('requested_dates')!=dates:raise ValueError('ALTERNATIVE_SOURCE_STATUS_IDENTITY')
            if body['state']=='RATE_LIMITED':return body
            if rc!=0 or {r['date'] for r in body['results']}!=set(dates):body['state']='INCOMPLETE'
            return body
        identity=hashlib.sha256((sha(script)+sha(Path(a.config))).encode()).hexdigest()
        print(json.dumps(run_pass(root,execute,source_code_sha=identity),sort_keys=True))


if __name__=='__main__':main()
