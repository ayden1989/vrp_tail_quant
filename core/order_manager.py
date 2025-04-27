"""
core/order_manager.py
Place Monday-morning 30-DTE SPX strangle *only* when
signals/latest_signal.json says enter_trade == True.
Runs in PAPER account first!
"""
import json, os, sqlite3, yaml, sys
from datetime import datetime
from math import floor
from ib_insync import IB, Order, Contract
from dotenv import load_dotenv

load_dotenv()
CONFIG = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
DB_PATH = os.path.join(os.path.dirname(__file__), os.pardir, CONFIG["database"])

# ── tiny helpers ───────────────────────────────────────────────────────────
def is_monday_open():
    now = datetime.now()
    return now.weekday() == 0 and (now.hour == 9 and 45 <= now.minute <= 15)

def load_signal():
    try:
        return json.load(open("signals/latest_signal.json"))
    except FileNotFoundError:
        return {"enter_trade": False}

def log_trade(rowdict):
    conn = sqlite3.connect(DB_PATH)
    cols, vals = zip(*rowdict.items())
    q = f"INSERT INTO trades ({','.join(cols)}) VALUES ({','.join('?'*len(vals))})"
    conn.execute(q, vals)
    conn.commit()
    conn.close()

# ── main engine ────────────────────────────────────────────────────────────
def main(paper=True):
    sig = load_signal()
    if not (sig.get("enter_trade") and is_monday_open()):
        print("No trade today.")
        return

    ib = IB()
    ib.connect(
        os.getenv("IB_HOST", "127.0.0.1"),
        int(os.getenv("IB_PORT", "7497")),      # 7497 = paper, 7496 = live
        clientId=int(os.getenv("IB_CLIENT_ID", "1"))
    )

    # 1️⃣  account size
    acct = ib.accountSummary()
    nlv = float(next(x.value for x in acct if x.tag == "NetLiquidation"))
    risk_cap = nlv * CONFIG["sizing"]["max_margin_pct"]

    # 2️⃣  underlying snapshot
    spx = Contract(symbol="SPX", secType="IND", exchange="CBOE", currency="USD")
    ticker = ib.reqMktData(spx, "", False, False)
    ib.sleep(1)
    spot = ticker.last or ticker.close
    margin_per_leg = 50 * spot   # rough = $50 * index-level
    contracts = max(1, floor(risk_cap / margin_per_leg))

    # 3️⃣  strikes: 15-delta ≈ ±10 % OTM when VIX ~20
    call_strike = round(spot * 1.10, -1)
    put_strike  = round(spot * 0.90, -1)

    expiry = (datetime.now().date().replace(day=1) + 
              timedelta(days=40)).strftime("%Y%m%d")  # ~30D
    call = Contract(symbol="SPX", lastTradeDateOrContractMonth=expiry,
                    strike=call_strike, right="C",
                    secType="OPT", exchange="SMART", currency="USD")
    put = Contract(symbol="SPX", lastTradeDateOrContractMonth=expiry,
                   strike=put_strike, right="P",
                   secType="OPT", exchange="SMART", currency="USD")
    ib.qualifyContracts(call, put)

    # 4️⃣  limit price = mid
    tick_c = ib.reqMktData(call, "", False, False)
    tick_p = ib.reqMktData(put,  "", False, False)
    ib.sleep(1)
    mid_c = (tick_c.bid + tick_c.ask)/2
    mid_p = (tick_p.bid + tick_p.ask)/2
    credit = mid_c + mid_p

    # 5️⃣  bracket: parent = combo SELL, children = TP & SL
    parent = Order(action="SELL", orderType="LMT", totalQuantity=contracts,
                   lmtPrice=round(credit, 2), transmit=False)
    tp = Order(action="BUY",  orderType="LMT", totalQuantity=contracts,
               lmtPrice=round(credit*0.50, 2), parentId=0, transmit=False)
    sl = Order(action="BUY",  orderType="LMT", totalQuantity=contracts,
               lmtPrice=round(credit*2.00, 2), parentId=0, transmit=True)

    # 6️⃣  place orders & log
    oids = ib.placeOrder(call, parent)  # sell call
    oids += ib.placeOrder(call, tp)
    oids += ib.placeOrder(call, sl)

    log_trade({
        "timestamp": datetime.utcnow().isoformat(),
        "strike_c": call_strike, "strike_p": put_strike,
        "qty": contracts, "credit": credit,
        "tp": credit*0.5, "sl": credit*2.0,
        "order_ids": str([o.orderId for o in oids]),
        "status": "submitted"
    })
    print("Trade submitted:", oids)
    ib.disconnect()

if __name__ == "__main__":
    main()