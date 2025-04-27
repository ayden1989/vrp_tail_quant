"""
core/delta_hedge.py
Twice-weekly MES hedge.  Run via cron Tue/Thu 15:30 ET.
"""
import os, sqlite3, yaml, json, math
from datetime import datetime
from ib_insync import IB, Future
from dotenv import load_dotenv

load_dotenv()
CFG = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
DB = os.path.join(os.path.dirname(__file__), os.pardir, CFG["database"])

def connect():
    ib = IB()
    ib.connect(os.getenv("IB_HOST","127.0.0.1"),
               int(os.getenv("IB_PORT","7497")),
               clientId=int(os.getenv("IB_CLIENT_ID","2")))
    return ib

def net_position_delta(ib):
    # IBKR greeks call
    total = 0
    for p in ib.positions():
        if p.contract.secType == "OPT":
            g = ib.reqMktData(p.contract, "106", False, False)  # 106=option greeks
            ib.sleep(0.5)
            total += g.modelGreeks.delta * p.position * 100
    return total   # SPX delta $

def size_mes_contracts(delta_dollars, spx_price):
    mes_mult = 5   # MES = $5 × index
    contracts = -delta_dollars / (mes_mult * spx_price)
    return math.copysign(math.floor(abs(contracts)+0.5), contracts)  # nearest int

def log_hedge(qty):
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS hedges (ts TEXT, qty INTEGER)")
    conn.execute("INSERT INTO hedges VALUES (?,?)", (datetime.utcnow().isoformat(), qty))
    conn.commit(); conn.close()

def main():
    ib = connect()
    delta = net_position_delta(ib)
    if abs(delta) < 1:         # already flat
        print("Delta ≈ 0, no hedge needed."); ib.disconnect(); return
    # need SPX spot to scale MES
    spx = ib.reqMktData(Future(symbol="MES", lastTradeDateOrContractMonth="", exchange="CME",
                               currency="USD"), "", False, False)
    ib.sleep(1)
    spot = spx.last or spx.close
    qty = size_mes_contracts(delta, spot)
    print(f"Net Δ = {delta:,.0f}$ ; sending MES {qty:+d}")
    mes = Future(symbol="MES", lastTradeDateOrContractMonth="", exchange="CME",
                 currency="USD")
    ib.qualifyContracts(mes)
    ib.placeOrder(mes, ib.marketOrder("BUY" if qty>0 else "SELL", abs(qty)))
    log_hedge(qty)
    ib.disconnect()

if __name__ == "__main__":
    main()