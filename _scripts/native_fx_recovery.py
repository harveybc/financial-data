"""Bounded, resumable native-hourly acquisition; never grants lake admission."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np
import pandas as pd


def digest(body):
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def write_json(path,body):
    path=Path(path);temp=path.with_suffix('.partial')
    with temp.open('w') as stream:
        json.dump(body,stream,sort_keys=True,indent=2,allow_nan=False)
        stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def validate(c):
    if (c.get('schema')!='financial_data.native_fx_recovery.v1'
            or c.get('provider')!='FXCM' or c.get('periodicity')!='H1'):
        raise ValueError('NATIVE_HOURLY_CONTRACT_REQUIRED')
    if any(c.get(k) is not False for k in ('interpolation','price_fill','admit_to_lake')):
        raise ValueError('NO_FILL_AND_NO_ADMISSION_REQUIRED')
    if c.get('weeks')!=list(range(1,54)):raise ValueError('FULL_WEEK_INVENTORY_REQUIRED')
    if not c.get('pairs') or len(set(c['pairs']))!=len(c['pairs']) or set(c['pairs'])-{'eurusd','gbpusd'}:
        raise ValueError('PAIR_CONTRACT')
    start=pd.Timestamp(c['required_start']);end=pd.Timestamp(c['required_end_exclusive'])
    for t in (start,end):
        if t.tzinfo is None or t.utcoffset().total_seconds()!=0 or t!=pd.Timestamp(year=t.year,month=1,day=1,tz='UTC'):
            raise ValueError('WHOLE_UTC_YEARS_REQUIRED')
    if not 1<=(end.year-start.year)<=10:raise ValueError('INVALID_REQUIRED_RANGE')
    if not 0<=c['retry_limit']<=2 or c['retry_wait_seconds']<0:raise ValueError('BOUNDED_RETRIES_REQUIRED')
    if not 1<=c['year_timeout_seconds']<=7200:raise ValueError('BOUNDED_WALL_REQUIRED')
    return c


def years(c):
    return range(pd.Timestamp(c['required_start']).year,pd.Timestamp(c['required_end_exclusive']).year)


def audit(frame,c):
    data=frame.copy()
    columns=[side+k for side in ('Bid','Ask') for k in ('Open','High','Low','Close')]
    if not set(columns+['timestamp','available_at']).issubset(data.columns):raise ValueError('QUOTE_SCHEMA')
    ts=pd.to_datetime(data.timestamp,utc=True,errors='raise')
    available=pd.to_datetime(data.available_at,utc=True,errors='raise')
    if ts.isna().any() or not (available-ts).eq(pd.Timedelta(hours=1)).all():
        raise ValueError('BAR_AVAILABILITY_MISMATCH')
    if (ts.dt.minute.ne(0)|ts.dt.second.ne(0)|ts.dt.microsecond.ne(0)).any():
        raise ValueError('HOURLY_CLOCK_ALIGNMENT')
    values=data[columns].to_numpy(float)
    if not np.isfinite(values).all() or (values<=0).any():raise ValueError('INVALID_QUOTES')
    for side in ('Bid','Ask'):
        if (data[side+'High']<data[[side+'Open',side+'Low',side+'Close']].max(axis=1)).any() or (data[side+'Low']>data[[side+'Open',side+'High',side+'Close']].min(axis=1)).any():
            raise ValueError('INVALID_OHLC')
    if (data.AskClose<data.BidClose).any() or (data.AskOpen<data.BidOpen).any():raise ValueError('CROSSED_QUOTES')
    data['timestamp']=ts;data['available_at']=available
    duplicates=data[data.timestamp.duplicated(keep=False)]
    if not duplicates.empty and (duplicates.groupby('timestamp')[columns+['available_at']].nunique()>1).any().any():
        raise ValueError('CONFLICTING_DUPLICATE_QUOTES')
    identical=int(data.timestamp.duplicated().sum())
    data=data.drop_duplicates('timestamp').set_index('timestamp').sort_index()
    start=pd.Timestamp(c['required_start']);end=pd.Timestamp(c['required_end_exclusive'])
    outside=int(((data.index<start)|(data.index>=end)).sum())
    data=data[(data.index>=start)&(data.index<end)]
    grid=pd.date_range(start,end,freq='h',inclusive='left')
    ny=grid.tz_convert('America/New_York');day=ny.dayofweek;hour=ny.hour
    expected=grid[(day<4)|((day==4)&(hour<17))|((day==6)&(hour>=17))]
    missing=expected.difference(data.index)
    months=[]
    for month in sorted(set(grid.strftime('%Y-%m'))):
        obs=data[data.index.strftime('%Y-%m')==month]
        gap=missing[missing.strftime('%Y-%m')==month]
        months.append(dict(month=month,observed_rows=len(obs),
            expected_open_hours=int((expected.strftime('%Y-%m')==month).sum()),
            missing_expected_open_hours=len(gap),missing_timestamps=[v.isoformat() for v in gap]))
    # A jump across missing hours/weekends is not a one-hour return.
    returns=np.log(data.BidClose).diff()
    returns=returns.where(data.index.to_series().diff().eq(pd.Timedelta(hours=1)))
    train=returns[(returns.index>=pd.Timestamp(c['train_start']))&(returns.index<pd.Timestamp(c['train_end_exclusive']))].dropna()
    median=float(train.median()) if len(train) else None
    mad=float((train-median).abs().median()) if len(train) else None
    reference=dict(n=len(train),median=median,mad=mad)
    outliers=dict(state='NOT_ESTIMABLE',reference=reference,count=None)
    if mad is not None and mad>0:
        flagged=(.6744897501960817*(returns-median).abs()/mad)>3.5
        outliers.update(state='FLAGGED_NOT_REMOVED',count=int(flagged.sum()))
    return dict(schema='financial_data.native_fx_quality.v1',admitted=False,
        state='SOURCE_VALIDATION_REQUIRED',calendar_basis=c['calendar_basis'],
        calendar_holidays_certified=False,months=months,observed_rows=len(data),
        missing_expected_open_hours=len(missing),outside_required_range_rows=outside,
        identical_duplicates_removed=identical,interpolated_values=0,
        outlier_reference='TRAIN_ONLY',return_outliers=outliers,
        outside_assumed_open_schedule_rows=int(len(data.index.difference(expected))))


def status(root):
    root=Path(root)
    state=json.loads((root/'STATUS.json').read_text())
    if state['state']=='RUNNING':
        try:
            current_token=Path(f"/proc/{state['controller_pid']}/stat").read_text().rsplit(')',1)[1].split()[19]
        except (OSError,KeyError,IndexError):current_token=None
        if current_token!=state.get('controller_process_token') or current_token is None:
            state.update(state='INTERRUPTED',eta_seconds=None)
            return state
        current=state.get('current_year')
        if current:
            low=Path(state['output'])/str(current)/'STATUS.json'
            if low.exists():
                value=json.loads(low.read_text())
                state['current_source_progress']={k:value.get(k) for k in ('state','current','total','complete','periodicity')}
                done=value.get('complete',0)+len(value.get('failures',[]))
                elapsed=time.time()-state['current_started_at']
                total=value.get('total',0)
                if done>=5 and elapsed>0:
                    remaining=(total-done)+(state['total_years']-state['completed_years']-state['failed_years']-1)*total
                    state['eta_seconds']=max(0,remaining*elapsed/done)
    return state


def run_jobs(root,output,c,executor,sleep=time.sleep):
    validate(c);root=Path(root);output=Path(output)
    root.mkdir(parents=True,exist_ok=True);output.mkdir(parents=True,exist_ok=True)
    identity=digest({'config':c,'output':str(output.resolve())})
    path=root/'STATUS.json'
    if path.exists():
        state=json.loads(path.read_text())
        if state['identity']!=identity:raise ValueError('RECOVERY_IDENTITY_CHANGED')
    else:
        state=dict(schema='financial_data.native_fx_controller.v1',identity=identity,
            output=str(output.resolve()),admitted=False,state='RUNNING',total_years=len(years(c)),
            completed_years=0,failed_years=0,started_at=time.time(),eta_seconds=None,
            jobs=[dict(year=y,state='PENDING',attempts=[]) for y in years(c)])
    for job in state['jobs']:
        if job['state'] in ('COMPLETE','FAILED'):continue
        for record in job['attempts']:
            if record['state']=='RUNNING':record.update(state='INTERRUPTED',finished_at=time.time())
        state.update(state='RUNNING',current_year=job['year'],current_started_at=time.time(),eta_seconds=None)
        state.update(controller_pid=os.getpid(),controller_process_token=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
        while len(job['attempts'])<=c['retry_limit']:
            attempt=len(job['attempts'])+1
            record=dict(attempt=attempt,state='RUNNING',started_at=time.time())
            job['attempts'].append(record);job['state']='RUNNING';write_json(path,state)
            try:rc=executor(job['year'],attempt)
            except subprocess.TimeoutExpired:rc=124
            except Exception as exc:
                record.update(state='FAILED',reason=type(exc).__name__,finished_at=time.time())
                job['state']='FAILED'
                state.update(state='BLOCKED_EXECUTION',eta_seconds=None,error=type(exc).__name__)
                write_json(path,state)
                raise
            record.update(returncode=rc,state='COMPLETE' if rc==0 else 'INCOMPLETE',finished_at=time.time())
            if rc==0:job['state']='COMPLETE';break
            if rc not in (2,75,124,-9):job['state']='FAILED';break
            if attempt<=c['retry_limit']:
                state.update(state='RETRY_PENDING',eta_seconds=None);write_json(path,state)
                sleep(c['retry_wait_seconds']);state['state']='RUNNING'
        if job['state']!='COMPLETE':job['state']='FAILED'
        state['completed_years']=sum(j['state']=='COMPLETE' for j in state['jobs'])
        state['failed_years']=sum(j['state']=='FAILED' for j in state['jobs'])
        write_json(path,state)
    state.update(state='INCOMPLETE_SOURCE_RECOVERY' if state['failed_years'] else 'ACQUISITION_FINISHED_REQUIRES_DATA_VALIDATION',
        current_year=None,finished_at=time.time(),eta_seconds=None)
    write_json(path,state)
    return state


def resource_check(output,c):
    available=int(next(v.split()[1] for v in Path('/proc/meminfo').read_text().splitlines() if v.startswith('MemAvailable:')))*1024
    if available<c['minimum_memory_available_bytes']:raise RuntimeError('WAIT_HOST_MEMORY')
    if not Path(output).is_dir():raise RuntimeError('OUTPUT_DIRECTORY_REQUIRED')
    mounted=subprocess.run(['findmnt','-J','-T',str(Path(output).resolve()),'-o','FSTYPE,OPTIONS'],capture_output=True,text=True,check=True)
    fs=json.loads(mounted.stdout)['filesystems'][0]
    if fs['fstype'] not in c['allowed_output_filesystems']:raise RuntimeError('STORAGE_FILESYSTEM_MISMATCH')
    if 'ro' in fs['options'].split(','):raise RuntimeError('READ_ONLY_STORAGE')
    if shutil.disk_usage(output).free<c['minimum_disk_free_bytes']:raise RuntimeError('WAIT_DISK_SPACE')


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('command',choices=['run','status'])
    p.add_argument('--root',required=True);p.add_argument('--output')
    p.add_argument('--config');p.add_argument('--predictor-root')
    a=p.parse_args();root=Path(a.root)
    if a.command=='status':print(json.dumps(status(root),sort_keys=True));return
    if not all((a.output,a.config,a.predictor_root)):p.error('run requires --output, --config and --predictor-root')
    c=validate(json.loads(Path(a.config).read_text()));runtime=Path(a.predictor_root).resolve()
    files=[runtime/'tools/i6dmo'/f for f in ('recover_fxcm_quotes.py','recover_fx_quotes.py')]
    c['runtime_identity']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    c['controller_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    c['numeric_versions']=dict(python=sys.version,pandas=pd.__version__,numpy=np.__version__)
    resource_check(a.output,c)
    root.mkdir(parents=True,exist_ok=True)
    with (root/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def execute(year,attempt):
            resource_check(a.output,c)
            if {f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}!=c['runtime_identity']:
                raise ValueError('RUNTIME_IDENTITY_CHANGED')
            cooldown=root/'PROVIDER_COOLDOWN.json'
            if cooldown.exists():
                until=json.loads(cooldown.read_text())['retry_not_before_epoch']
                if until>time.time():
                    state=json.loads((root/'STATUS.json').read_text())
                    state.update(state='WAIT_PROVIDER',eta_seconds=None,retry_not_before_epoch=until)
                    write_json(root/'STATUS.json',state)
                    time.sleep(max(0,until-time.time()))
            command=[sys.executable,'-B','-m','tools.i6dmo.recover_fxcm_quotes',
                '--output',str(Path(a.output)/str(year)),'--periodicity','H1','--year',str(year),
                '--pairs',*c['pairs'],'--weeks',*map(str,c['weeks'])]
            env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
            rc=subprocess.run(command,cwd=runtime,env=env,timeout=c['year_timeout_seconds']).returncode
            low=Path(a.output)/str(year)/'STATUS.json'
            if low.exists():
                child=json.loads(low.read_text())
                if child.get('state')=='RATE_LIMITED':
                    write_json(cooldown,{'retry_not_before_epoch':child['retry_not_before_epoch']})
            return rc
        result=run_jobs(root,a.output,c,execute)
        reports={}
        for pair in c['pairs']:
            files=[Path(a.output)/str(y)/pair/f'{y}-1h.parquet' for y in years(c)]
            present=[f for f in files if f.is_file()]
            if not present:
                reports[pair]=dict(state='NO_SOURCE_ROWS',admitted=False)
                continue
            frames=[pd.read_parquet(f) for f in present]
            report=audit(pd.concat(frames,ignore_index=True),c)
            report['source_sha256']={str(f.relative_to(a.output)):hashlib.sha256(f.read_bytes()).hexdigest() for f in present}
            report['missing_year_files']=[str(f.relative_to(a.output)) for f in files if not f.is_file()]
            write_json(root/f'QUALITY.{pair}.json',report)
            reports[pair]={k:report[k] for k in ('observed_rows','missing_expected_open_hours','admitted')}
        result.update(quality=reports,state='RECOVERY_AWAITING_CLOCK_CALENDAR_AND_GAP_ACCEPTANCE',eta_seconds=None)
        write_json(root/'STATUS.json',result)
        print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
