import io
import zipfile

import pandas as pd
import pytest

from _scripts.recover_forexite_observations import parse


def archive(row):
    b=io.BytesIO()
    with zipfile.ZipFile(b,'w') as z:
        z.writestr('030723.txt','<TICKER>,<DTYYYYMMDD>,<TIME>,<OPEN>,<HIGH>,<LOW>,<CLOSE>\n'+row)
    return b.getvalue()


GOOD='EURUSD,20230703,000100,1.09,1.10,1.08,1.095\n'


def test_native_time_retained_without_invented_utc_offset():
    d=parse(archive(GOOD))
    assert d.timestamp_native.iloc[0]==pd.Timestamp('2023-07-03T00:01:00')
    assert d.timestamp_native.dt.tz is None


@pytest.mark.parametrize('row,reason',[(GOOD+GOOD,'DUPLICATE'),(GOOD.replace('1.095','nan'),'INVALID_PRICE'),(GOOD.replace('1.10','1.07'),'INVALID_OHLC')])
def test_invalid_quotes_not_adopted(row,reason):
    with pytest.raises(ValueError,match=reason):parse(archive(row))
