"""Publish new source-quality evidence, never model results or lake admission."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024**2),b''):h.update(part)
    return h.hexdigest()


def verify_sources(quality,bulk):
    bulk=Path(bulk).resolve()
    for name,expected in quality['source_sha256'].items():
        path=(bulk/name).resolve()
        if not path.is_relative_to(bulk):raise ValueError('SOURCE_PATH_ESCAPES_RECOVERY')
        if not path.is_file() or file_sha(path)!=expected:raise ValueError('SOURCE_DIGEST_MISMATCH')


def build_report(pair,q,identity,code_commit):
    if (pair not in ('eurusd','gbpusd') or q.get('schema')!='financial_data.native_fx_quality.v1'
            or q.get('admitted') is not False or q.get('interpolated_values')!=0 or q.get('quote_view')!='BID'):
        raise ValueError('NEW_UNADMITTED_OBSERVED_BID_QUALITY_REQUIRED')
    if not q.get('source_sha256'):raise ValueError('SOURCE_IDENTITIES_REQUIRED')
    for value in q['source_sha256'].values():
        if len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('SOURCE_IDENTITY_FORMAT')
    sha=hashlib.sha256(json.dumps(q,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    metrics=[]
    def add(name,value,unit='count',split='quality'):
        metrics.append(dict(metric=name,value=value,unit=unit,split=split,horizon=None))
    for month in q['months']:
        year=int(month['month'][:4]);split='train' if year<=2023 else 'validation' if year==2024 else 'test' if year==2025 else 'quality'
        for field in ('observed_rows','expected_open_hours','missing_expected_open_hours'):
            add(f"coverage.{month['month']}.{field}",month[field],split=split)
    for field in ('observed_rows','missing_expected_open_hours','identical_duplicates_removed',
                  'outside_assumed_open_schedule_rows','crossed_side_bar_endpoints'):
        add(field,q[field])
    add('return_outlier_count',q['return_outliers']['count'])
    for field,value in q['return_outliers']['reference'].items():
        add('return_outlier_reference.'+field,value,'count' if field=='n' else 'log_return',split='train')
    return dict(experiment_key=f'native-fx-quality:{pair}:{sha}',experiment_set_key='canonical-native-fx-recovery',
        actor='canonical-data-curation',lake='acquisition-not-admitted',lineage='UNVERIFIED',
        project='financial-data',phase='NATIVE_SOURCE_QUALITY',config_sha256=identity,code_commit=code_commit,
        tags=dict(kind='native_source_quality',pair=pair,admission='NOT_ADMITTED',quote_view='BID',
            calendar=q['calendar_basis'],outlier_state=q['return_outliers']['state'],
            source_quality_sha256=sha,executable_spread_eligible='false',model_training='false'),
        datasets=[dict(lake='acquisition-not-admitted',resource=pair+'/'+name,sha256=value,
            role='native_bid_candle_candidate',lineage='UNVERIFIED',reason='Source/calendar acceptance pending')
            for name,value in sorted(q['source_sha256'].items())],metrics=metrics)


def write_json(path,body):
    path=Path(path);temp=path.with_suffix('.partial')
    with temp.open('w') as f:
        json.dump(body,f,sort_keys=True,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def snapshot(path,reports):
    import duckdb
    from predictor_olap_store.query import normalise_report
    conn=duckdb.connect(str(path),config={'memory_limit':'256MB','threads':1})
    try:
        conn.execute('CREATE TABLE IF NOT EXISTS quality_report(report_sha256 VARCHAR PRIMARY KEY,body_json VARCHAR)')
        conn.execute('CREATE TABLE IF NOT EXISTS quality_metric(report_sha256 VARCHAR,metric VARCHAR,split VARCHAR,value DOUBLE,unit VARCHAR,PRIMARY KEY(report_sha256,metric,split))')
        for report in reports:
            sha=report['report_sha256']
            body=json.dumps(report,sort_keys=True,allow_nan=False)
            existing=conn.execute('SELECT body_json FROM quality_report WHERE report_sha256=?',[sha]).fetchone()
            if existing and existing[0]!=body:raise ValueError('PHYSICAL_REPORT_CONFLICT')
            conn.execute('INSERT OR IGNORE INTO quality_report VALUES (?,?)',[sha,body])
            for m in normalise_report(report)['metrics']:
                row=[sha,m['metric'],m['split'],m['value'],m['unit']]
                existing=conn.execute('SELECT value,unit FROM quality_metric WHERE report_sha256=? AND metric=? AND split=?',row[:3]).fetchone()
                if existing is not None and existing!=(m['value'],m['unit']):raise ValueError('PHYSICAL_METRIC_CONFLICT')
                conn.execute('INSERT OR IGNORE INTO quality_metric VALUES (?,?,?,?,?)',row)
            stored=conn.execute('SELECT metric,split,value,unit FROM quality_metric WHERE report_sha256=? ORDER BY metric,split',[sha]).fetchall()
            expected=sorted((m['metric'],m['split'],m['value'],m['unit']) for m in normalise_report(report)['metrics'])
            if stored!=expected:raise ValueError('PHYSICAL_METRIC_READBACK_MISMATCH')
        conn.execute('CHECKPOINT')
    finally:conn.close()
    return file_sha(path)


def copy_closed(source,destination):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    temp=destination.with_suffix('.partial');shutil.copyfile(source,temp)
    if file_sha(temp)!=file_sha(source):temp.unlink();raise ValueError('LOCAL_COPY_DIGEST_MISMATCH')
    with temp.open('rb') as stream:os.fsync(stream.fileno())
    os.replace(temp,destination)
    return file_sha(destination)


def mirror_closed(source,host,relative):
    if host.startswith('-') or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('MIRROR_TARGET_CONTRACT')
    sha=file_sha(source)
    code="""import sys,hashlib,os,json
from pathlib import Path
p=Path.home()/sys.argv[1]
b=sys.stdin.buffer.read(32*1024**2+1)
if len(b)>32*1024**2 or hashlib.sha256(b).hexdigest()!=sys.argv[2]:raise ValueError('MIRROR_INPUT_DIGEST')
p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.partial')
with tmp.open('wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
os.replace(tmp,p)
sha=hashlib.sha256(p.read_bytes()).hexdigest()
if sha!=sys.argv[2]:raise ValueError('MIRROR_READBACK_DIGEST')
print(json.dumps({'sha256':sha,'bytes':len(b)}))
"""
    command='python3 -c '+shlex.quote(code)+' '+shlex.quote(relative)+' '+sha
    r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10',host,command],
        input=Path(source).read_bytes(),capture_output=True,timeout=45,check=True)
    result=json.loads(r.stdout)
    if result['sha256']!=sha:raise ValueError('REMOTE_COPY_DIGEST_MISMATCH')
    return result


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('command',choices=['run','status'])
    p.add_argument('--root',required=True);p.add_argument('--predictor-root')
    p.add_argument('--warehouse-url');p.add_argument('--token-env',default='DATA_GOV_LAKE_TOKEN')
    p.add_argument('--code-commit')
    p.add_argument('--mirror-host');p.add_argument('--mirror-relative-path')
    a=p.parse_args();root=Path(a.root);target=root/'PUBLICATION_STATUS.json'
    if a.command=='status':print(target.read_text());return
    if not all((a.predictor_root,a.warehouse_url,a.mirror_host,a.mirror_relative_path,a.code_commit)):
        p.error('run requires runtime, warehouse, mirror and code-commit arguments')
    state_path=root/'STATUS.json'
    if not state_path.exists():return
    with (root/'publication.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=json.loads(state_path.read_text());ready=[(pair,root/f'QUALITY.{pair}.json') for pair in ('eurusd','gbpusd')]
        if not all(path.is_file() for _,path in ready):
            write_json(target,dict(state='WAIT_SOURCE_QUALITY',admitted=False,expected_pairs=2,
                available_pairs=sum(path.is_file() for _,path in ready)))
            return
        runtime=Path(a.predictor_root).resolve();sys.path.insert(0,str(runtime))
        from tools.i6dmo.outbox import Outbox,HttpWarehouse
        pinned=subprocess.run(['git','-C',str(Path(__file__).parents[1]),'show',a.code_commit+':_scripts/publish_native_fx_quality.py'],capture_output=True,check=True).stdout
        if hashlib.sha256(pinned).hexdigest()!=file_sha(__file__):raise ValueError('PUBLISHER_CODE_NOT_PINNED')
        code=a.code_commit
        box=Outbox(root/'quality-outbox.sqlite')
        try:
            for pair,path in ready:
                q=json.loads(path.read_text());verify_sources(q,Path(state['output']))
                box.enqueue(build_report(pair,q,state['identity'],code),source_unit='native-source-quality:'+pair)
            delivery=box.pump(HttpWarehouse(a.warehouse_url,a.token_env))
            reports=[json.loads(item['body']) for item in box.items()]
            physical=root/'native_fx_quality.duckdb';sha=snapshot(physical,reports)
            copy=Path(state['output']).parent/'quality-copies/native_fx_quality.duckdb'
            if copy_closed(physical,copy)!=sha:raise ValueError('LOCAL_MIRROR_MISMATCH')
            mirror=mirror_closed(physical,a.mirror_host,a.mirror_relative_path)
            complete=delivery['pending']==0 and delivery['mismatch']==0 and delivery['delivered']==len(ready)
            write_json(target,dict(state='QUALITY_PUBLISHED_NOT_ADMITTED' if complete else 'QUALITY_PUBLICATION_PENDING',
                admitted=False,warehouse=delivery,physical_sha256=sha,second_machine=mirror))
        except Exception as exc:
            write_json(target,dict(state='PUBLICATION_RETRY_PENDING',admitted=False,error_type=type(exc).__name__))
            raise
        finally:box.close()


if __name__=='__main__':main()
