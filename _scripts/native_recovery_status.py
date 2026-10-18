"""Read-only stage status. Source files and candidate dates are not admission."""
import argparse
from datetime import date
import json
from pathlib import Path


def load(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def snapshot(root,alternative_output=None):
    root=Path(root);parent=load(root/'STATUS.json')
    result=dict(state=parent.get('state','NOT_INITIALIZED'),data_admission_complete=False,
        feature_selection_complete=False,model_training_authorized=False)
    jobs=parent.get('jobs',[])
    native=dict(years_declared=len(jobs),years_processed=sum(j.get('state') in ('COMPLETE','FAILED') for j in jobs),
        requested_week_files=0,available_week_files=0,unavailable_week_files=0)
    if parent.get('output'):
        for job in jobs:
            low=load(Path(parent['output'])/str(job['year'])/'STATUS.json')
            native['requested_week_files']+=low.get('total',0)
            native['available_week_files']+=low.get('complete',0)
            native['unavailable_week_files']+=len(low.get('failures',[]))
    result['native']=native
    result['native_quality']={pair:{k:q.get(k) for k in ('observed_rows','missing_expected_open_hours','calendar_basis','admitted')}
        for pair in ('eurusd','gbpusd') if (q:=load(root/f'QUALITY.{pair}.json'))}
    plan=load(root/'GAP_RECOVERY_PLAN.json');available={};failures={}
    for batch in plan.get('batches',[]):
        for attempt in batch.get('attempts',[]):
            for record in attempt.get('result',{}).get('results',[]):available[record['date']]=record
            for record in attempt.get('result',{}).get('failures',[]):failures[record['date']]=record
    dates=set(plan.get('requested_dates',[]))
    if alternative_output:
        current=load(Path(alternative_output)/'STATUS.json')
        for record in current.get('results',[]):
            if record['date'] in dates:available[record['date']]=record
        for record in current.get('failures',[]):
            if record['date'] in dates:failures[record['date']]=record
    counts={}
    for record in available.values():
        for pair,n in record.get('observations',{}).items():counts[pair]=counts.get(pair,0)+n
    result['alternative']=dict(state=load(root/'GAP_RECOVERY_STATUS.json').get('state','NOT_STARTED'),
        requested_native_dates=len(dates),available_native_dates=len(available),
        remaining_unavailable_or_pending_dates=len(dates-set(available)),
        candidate_minute_observations=counts,hours_verified_as_repaired=None,
        unavailable_date_diagnostics=[dict(date=d,weekday=date.fromisoformat(d).strftime('%A'),
            reason=failures.get(d,{}).get('reason','PENDING_OR_UNAVAILABLE'),
            calendar_disposition='UNVERIFIED') for d in sorted(dates-set(available))],
        clock_verified=False,admitted=False)
    result['publication']=load(root/'PUBLICATION_STATUS.json')
    return result


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--root',required=True)
    p.add_argument('--alternative-output')
    a=p.parse_args();print(json.dumps(snapshot(a.root,a.alternative_output),sort_keys=True,indent=2))


if __name__=='__main__':main()
