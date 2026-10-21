import json
import sys
from pathlib import Path
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workers'))
import stage16_fxmacrodata_history_worker as W


def test_nested_forecast_time_and_class_are_separate():
    rows=W.forecast_rows({'data':[{'announcement_datetime':1000,'announcement_id':'a',
        'predictions':[{'generated_at':900,'prediction_class':'model_nowcast','predicted_value':2}]}]})
    assert len(rows)==1 and rows[0]['prediction_class']=='model_nowcast'
    assert W.label_consensus(rows[0])=='PRE_RELEASE'


def test_prediction_and_announcement_pagination():
    assert W.next_page('predictions/usd/inflation',{'has_more':True,'next_cursor':'2024-03-01'})=={'before_date':'2024-03-01'}
    assert W.next_page('announcements/usd/inflation',{'dataset_version':'v','pagination':{'has_more':True,'next_offset':100}})=={'offset':100,'dataset_version':'v'}
    with pytest.raises(W.Refusal):W.next_page('predictions/usd/inflation',{'has_more':True})


def test_all_pages_are_retained_with_global_request_bound(tmp_path,monkeypatch):
    monkeypatch.setenv('FXMACRODATA_API_KEY','private-test-key')
    args=W.parser().parse_args(['--out',str(tmp_path),'--probe','--max-requests','4'])
    calls=[]
    def fetch(ep,params,key):
        calls.append((ep,params.copy()))
        if ep.startswith('announcements/'):
            data={'data':[{'announcement_datetime':1}], 'dataset_version':'v',
                'pagination':{'has_more':'offset' not in params,'next_offset':100}}
        else:data={'data':[],'has_more':False}
        return 200,json.dumps(data).encode()
    s=W.run(args,fetch=fetch,throttle=W.Throttle(0))
    assert len(calls)==4 and s['http_requests']==4 and not s['complete']
    assert calls[1][1]['offset']==100 and calls[1][1]['dataset_version']=='v'
    assert len((tmp_path/'RAW.jsonl').read_text().splitlines())==4


def test_missing_cursor_is_recorded_as_incomplete(tmp_path,monkeypatch):
    monkeypatch.setenv('FXMACRODATA_API_KEY','private-test-key')
    args=W.parser().parse_args(['--out',str(tmp_path),'--probe','--max-requests','1'])
    s=W.run(args,fetch=lambda *a:(200,b'{"data":[],"pagination":{"has_more":true}}'),throttle=W.Throttle(0))
    assert not s['complete'] and s['pagination_errors']


def test_reexecution_never_overwrites_retained_raw(tmp_path,monkeypatch):
    monkeypatch.setenv('FXMACRODATA_API_KEY','private-test-key')
    (tmp_path/'RAW.jsonl').write_text('retained')
    args=W.parser().parse_args(['--out',str(tmp_path),'--probe'])
    with pytest.raises(W.Refusal):W.run(args,fetch=lambda *a:pytest.fail('network'))
    assert (tmp_path/'RAW.jsonl').read_text()=='retained'


def test_live_contract_options_and_derived_secret_redaction(tmp_path,monkeypatch):
    secret='private-test-key';monkeypatch.setenv('FXMACRODATA_API_KEY',secret)
    args=W.parser().parse_args(['--out',str(tmp_path),'--probe'])
    def fetch(ep,params,key):
        assert params['limit']==100 and params['as_of']=='2025-01-01T00:00:00Z'
        if ep.startswith('announcements/'):
            assert params['revisions']=='latest'
            return 200,b'{"data":[],"pagination":{"has_more":false}}'
        assert params['official_limit']==0 and params['pre_release_only']=='true'
        return 200,json.dumps({'has_more':False,'data':[{'announcement_datetime':1000,
            'predictions':[{'generated_at':900,'prediction_class':'model_nowcast','source_url':'https://example.com/?api_key='+key}]}]}).encode()
    s=W.run(args,fetch=fetch,throttle=W.Throttle(0))
    assert s['complete'] and s['prediction_classes']=={'model_nowcast':3}
    assert secret not in (tmp_path/'FORECASTS.jsonl').read_text()


def test_catalogue_supported_scope_and_mom_alias():
    requests=W.plan(['usd','eur'],'2020-01-01','2025-01-01',True)
    assert all(not r['endpoint'].endswith(('/pmi','/nmi')) for r in requests)
    assert W.ALIASES['inflation_mom']==('inflation',{'frequency':'mom'})
