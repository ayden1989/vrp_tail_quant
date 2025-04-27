import os
import json
from core.signal_vrp import make_signal

def test_signal_file_creation(tmp_path, monkeypatch):
    # Point to our test DB (reuse from data_pull test)
    monkeypatch.setenv("DATABASE", str(tmp_path/"test.db"))
    import core.data_pull as dp
    dp.DB_PATH = str(tmp_path/"test.db")
    # Create tables only
    import core.data_pull as dpmod
    dpmod.connect_db().execute(f"CREATE TABLE IF NOT EXISTS options_{datetime.utcnow().strftime('%Y%m%d')} (symbol)")
    dpmod.connect_db().execute("CREATE TABLE IF NOT EXISTS vix_curve (timestamp,contract,price,expiry)")
    dpmod.connect_db().execute("CREATE TABLE IF NOT EXISTS underlyings (timestamp,symbol,price)")
    # Run signal
    make_signal()
    assert os.path.exists("signals/latest_signal.json")
    data = json.load(open("signals/latest_signal.json"))
    assert "enter_trade" in data