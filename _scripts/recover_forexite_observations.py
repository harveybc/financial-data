"""Acquire real missing-interval quotes, preserving their native clock.

These files are recovery candidates outside the admitted lake. This script
does not guess a UTC offset, fill a price or authorize model training.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import time
import zipfile

import numpy as np
import pandas as pd
import requests


def parse(raw):
    if len(raw)>16*1024**2:raise ValueError('ARCHIVE_TOO_LARGE')
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>64*1024**2 or z.testzip() is not None:
            raise ValueError('ARCHIVE_SIZE_OR_CRC')
        names=[n for n in z.namelist() if n.lower().endswith('.txt')]
        if len(names)!=1:raise ValueError('ARCHIVE_SCHEMA')
        with z.open(names[0]) as f:df=pd.read_csv(f,dtype={'<TIME>':str,'<DTYYYYMMDD>':str})
    df.columns=df.columns.str.strip('<>')
    required={'TICKER','DTYYYYMMDD','TIME','OPEN','HIGH','LOW','CLOSE'}
    if set(df.columns)!=required:raise ValueError('QUOTE_SCHEMA')
    df=df[df.TICKER.isin(['EURUSD','GBPUSD'])].copy()
    if df.empty:raise ValueError('NO_REQUIRED_PAIRS')
    df['timestamp_native']=pd.to_datetime(df.DTYYYYMMDD+df.TIME.str.zfill(6),format='%Y%m%d%H%M%S',errors='raise')
    values=df[['OPEN','HIGH','LOW','CLOSE']].to_numpy(float)
    if not np.isfinite(values).all() or (values<=0).any():raise ValueError('INVALID_PRICE')
    if (df.HIGH<df[['OPEN','LOW','CLOSE']].max(axis=1)).any() or (df.LOW>df[['OPEN','HIGH','CLOSE']].min(axis=1)).any():
        raise ValueError('INVALID_OHLC')
    if df.duplicated(['TICKER','timestamp_native']).any():raise ValueError('DUPLICATE_QUOTES')
    return df[['TICKER','timestamp_native','OPEN','HIGH','LOW','CLOSE']].sort_values(['TICKER','timestamp_native'])


def write_json(path,body):
    tmp=path.with_suffix('.partial');tmp.write_text(json.dumps(body,sort_keys=True,indent=2));os.replace(tmp,path)


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--dates',nargs='+',required=True)
    a=p.parse_args();root=Path(a.output);root.mkdir(parents=True,exist_ok=True)
    status=dict(state='ACQUIRING',total=len(a.dates),complete=0,results=[],failures=[],
                qualification='OBSERVED_CANDIDATES_NATIVE_CLOCK_NOT_YET_ADMITTED',interpolation=False)
    with requests.Session() as session:
        for value in a.dates:
            date=pd.Timestamp(value)
            name=date.strftime('%d%m%y')
            raw=root/(name+'.zip')
            try:
                if not raw.exists():
                    url=f'https://www.forexite.com/free_forex_quotes/{date.year}/{date.month:02d}/{name}.zip'
                    r=session.get(url,timeout=(15,40));r.raise_for_status();parse(r.content)
                    temp=raw.with_suffix('.partial');temp.write_bytes(r.content);os.replace(temp,raw)
                df=parse(raw.read_bytes())
                target=root/(name+'.parquet')
                if target.exists():pd.testing.assert_frame_equal(pd.read_parquet(target),df.reset_index(drop=True))
                else:df.reset_index(drop=True).to_parquet(target,index=False)
                record=dict(date=value,observations=df.groupby('TICKER').size().astype(int).to_dict(),
                            source_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                            parquet_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
                status['results'].append(record);status['complete']+=1;print(json.dumps(record),flush=True)
            except Exception as exc:status['failures'].append(dict(date=value,error_type=type(exc).__name__))
            write_json(root/'STATUS.json',status);time.sleep(.3)
    status['state']='ACQUIRED' if not status['failures'] else 'INCOMPLETE';write_json(root/'STATUS.json',status)
    raise SystemExit(0 if status['state']=='ACQUIRED' else 2)


if __name__=='__main__':main()
