"""Read-only indicative EURUSD H1 snapshots, with real receipt-time availability."""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import time

URL='https://query1.finance.yahoo.com/v8/finance/chart/EURUSD=X'


def closed_bars(payload,received):
    result=payload['chart']['result'][0]
    if result['meta']['symbol']!='EURUSD=X':raise ValueError('WRONG_INSTRUMENT')
    stamps=result['timestamp'];q=result['indicators']['quote'][0]
    if len(set(stamps))!=len(stamps) or stamps!=sorted(stamps):raise ValueError('TIMESTAMP_ORDER')
    bars=[];excluded=0
    for i,stamp in enumerate(stamps):
        if type(stamp) is not int or stamp%3600 or stamp+3600>received:
            excluded+=1;continue
        values=[q[key][i] for key in ('open','high','low','close')]
        if any(v is None for v in values):excluded+=1;continue
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in values):
            raise ValueError('NONFINITE_PRICE')
        op,hi,lo,cl=values
        if not lo<=min(op,cl)<=max(op,cl)<=hi:raise ValueError('INVALID_OHLC')
        bars.append(dict(bar_start_epoch=stamp,bar_end_epoch=stamp+3600,
            open=op,high=hi,low=lo,close=cl,received_at_epoch=received,available_at_epoch=received))
    return bars,excluded


def put(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.partial')
    with temporary.open('w') as f:
        json.dump(value,f,sort_keys=True,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temporary,path)


def run(root,store):
    import requests
    root=Path(root);store=Path(store);root.mkdir(parents=True,exist_ok=True);store.mkdir(parents=True,exist_ok=True)
    with (root/'.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return 0
        try:
            if shutil.disk_usage(store).free<10*1024**3:raise ValueError('DISK_RESERVE')
            response=requests.get(URL,params={'interval':'60m','range':'5d'},headers={'User-Agent':'Mozilla/5.0'},timeout=25)
            if response.status_code!=200:raise ValueError('PROVIDER_HTTP_'+str(response.status_code))
            receipt=time.time();bars,excluded=closed_bars(response.json(),receipt)
            if len(bars)<72:raise ValueError('INSUFFICIENT_OBSERVED_CONTEXT')
            latest=bars[-1]['bar_end_epoch'];fresh=receipt-latest<=7200
            pin=hashlib.sha256(response.content).hexdigest();raw=store/'raw'/f'{pin}.json';raw.parent.mkdir(exist_ok=True)
            if not raw.exists():
                with raw.open('xb') as f:f.write(response.content);f.flush();os.fsync(f.fileno())
            envelope=dict(schema='eurusd_forward_feed.v1',state='READY' if fresh else 'STALE',
                source='YAHOO_FINANCE_INDICATIVE',quote_type='INDICATIVE_NOT_BROKER_BID_ASK',
                source_url=URL,symbol='EURUSD',timeframe='1h',bar_timestamp_semantics='UTC_BAR_START',
                received_at_epoch=receipt,decision_as_of_epoch=receipt,latest_bar_end_epoch=latest,
                lag_seconds=receipt-latest,raw_sha256=pin,excluded_rows=excluded,bars=bars,
                historical_context_only=True,live_prediction_backdating_allowed=False,
                execution='NO_ORDERS_NO_BROKER_WRITE',broker_execution_parity=False)
            put(store/'LATEST.json',envelope)
            with (store/'receipts.jsonl').open('a') as f:
                f.write(json.dumps({k:v for k,v in envelope.items() if k!='bars'},sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
            put(root/'STATUS.json',dict(state=envelope['state'],bars=len(bars),latest_bar_end_epoch=latest,
                received_at_epoch=receipt,snapshot=str(store/'LATEST.json'),raw_sha256=pin))
            return 0 if fresh else 2
        except (ValueError,KeyError,TypeError,IndexError,OSError,requests.RequestException) as exc:
            failure=dict(schema='eurusd_forward_feed.v1',state='UNAVAILABLE',error_type=type(exc).__name__,
                         received_at_epoch=time.time(),bars=[])
            put(root/'STATUS.json',failure)
            put(store/'LATEST.json',failure)
            return 2


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--state',required=True);p.add_argument('--store',required=True)
    a=p.parse_args();raise SystemExit(run(a.state,a.store))
