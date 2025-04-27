"""
core/pnl_tracker.py
Runs once at 17:00 ET.  Logs equity   → vrp_data.db:daily_equity
                               and emails / Discords a summary.
"""
import os, sqlite3, smtplib, yaml, json
from email.mime.text import MIMEText
from datetime import datetime
from ib_insync import IB
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
CFG = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
DB  = os.path.join(os.path.dirname(__file__), os.pardir, CFG["database"])

def connect_ib():
    ib = IB()
    ib.connect(os.getenv("IB_HOST","127.0.0.1"),
               int(os.getenv("IB_PORT","7497")),
               clientId=int(os.getenv("IB_CLIENT_ID","3")))
    return ib

def record_equity(nlv, realized, unrealized):
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS daily_equity
                    (ts TEXT, nlv REAL, realized REAL, unrealized REAL)""")
    conn.execute("INSERT INTO daily_equity VALUES (?,?,?,?)",
                 (datetime.utcnow().isoformat(), nlv, realized, unrealized))
    conn.commit(); conn.close()

def fetch_last_n_days(n=20):
    df = pd.read_sql("SELECT * FROM daily_equity ORDER BY ts DESC LIMIT ?", 
                     sqlite3.connect(DB), params=(n,))
    return df.sort_values("ts")

def send_email(body):
    if not os.getenv("SMTP_HOST"):        # skip if no creds
        print("No SMTP creds, email skipped"); return
    msg = MIMEText(body, "plain")
    msg["Subject"]="VRP daily PnL"
    msg["From"]=os.getenv("EMAIL_FROM")
    msg["To"]=os.getenv("EMAIL_TO")
    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT","587"))) as s:
        s.starttls(); s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        s.send_message(msg)

def main(paper=True):
    ib = connect_ib()
    row = {x.tag: float(x.value) for x in ib.accountSummary()}
    ib.disconnect()
    nlv = row["NetLiquidation"]
    realized = row["RealizedPnL"]
    unrealized = row["UnrealizedPnL"]

    record_equity(nlv, realized, unrealized)

    df = fetch_last_n_days()
    body = (f"Date: {datetime.now().strftime('%Y-%m-%d')}\n"
            f"NLV:  ${nlv:,.0f}\n"
            f"Realized PnL today: ${realized:,.0f}\n"
            f"Unrealized PnL:    ${unrealized:,.0f}\n\n"
            "Equity (last 20d):\n"
            + df[ ['ts','nlv'] ].to_string(index=False))

    send_email(body)
    print(body)

if __name__ == "__main__":
    main()