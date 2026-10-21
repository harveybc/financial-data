import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workers'))
import eurusd_forward_feed as F


def payload():
    return {'chart':{'result':[{'meta':{'symbol':'EURUSD=X'},'timestamp':[0,3600,7200,10900],
        'indicators':{'quote':[dict(open=[1]*4,high=[2]*4,low=[.5]*4,close=[1.5]*4)]}}]}}


def test_only_closed_hourly_bars_and_receipt_availability():
    bars,excluded=F.closed_bars(payload(),8000)
    assert [r['bar_start_epoch'] for r in bars]==[0,3600]
    assert excluded==2 and all(r['received_at_epoch']==8000 for r in bars)
    assert all(r['available_at_epoch']==8000 for r in bars)


def test_future_changes_do_not_change_closed_context():
    p=payload();before=F.closed_bars(p,8000)
    p['chart']['result'][0]['indicators']['quote'][0]['high'][2]=1000
    assert F.closed_bars(p,8000)==before


def test_invalid_ohlc_and_wrong_instrument_rejected():
    p=payload();p['chart']['result'][0]['indicators']['quote'][0]['low'][0]=9
    with pytest.raises(ValueError):F.closed_bars(p,8000)
    p=payload();p['chart']['result'][0]['meta']['symbol']='OTHER'
    with pytest.raises(ValueError):F.closed_bars(p,8000)


def test_duplicate_timestamp_and_missing_value_not_filled():
    p=payload();p['chart']['result'][0]['timestamp'][1]=0
    with pytest.raises(ValueError):F.closed_bars(p,8000)
    p=payload();p['chart']['result'][0]['indicators']['quote'][0]['close'][0]=None
    bars,excluded=F.closed_bars(p,8000)
    assert [r['bar_start_epoch'] for r in bars]==[3600] and excluded==3
