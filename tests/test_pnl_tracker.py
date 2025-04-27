import core.pnl_tracker as pt

class DummyIB:
    def __init__(self):
        from collections import namedtuple
        Row = namedtuple("Row","tag value")
        self._rows = [Row("NetLiquidation","40000"),
                      Row("RealizedPnL","150"),
                      Row("UnrealizedPnL","-20")]
    def connect(self,*a,**k): pass
    def disconnect(self): pass
    def accountSummary(self): return self._rows

def test_log_insert(monkeypatch,tmp_path):
    # point DB to temp file
    monkeypatch.setattr(pt,"DB", str(tmp_path/"test.db"))
    monkeypatch.setattr(pt,"connect_ib", lambda: DummyIB())
    monkeypatch.setattr(pt,"send_email", lambda *_: None)   # skip SMTP
    pt.main()
    import sqlite3, pandas as pd
    df = pd.read_sql("SELECT * FROM daily_equity", sqlite3.connect(pt.DB))
    assert len(df)==1
    assert df.nlv.iloc[0] == 40000