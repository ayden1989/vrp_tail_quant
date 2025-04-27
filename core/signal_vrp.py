"""
core/signal_vrp.py

Generate a Boolean signal for entering the weekly 30-DTE strangle
based on implied vs. realized move and VIX front vs. its 252-day median.
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd
import yaml
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load config
load_dotenv()
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CONFIG_PATH) as f:
    cfg = yaml.safe_load(f)

DB_PATH = os.path.join(os.path.dirname(__file__), os.pardir, cfg["database"])
VIX_MED_WINDOW = cfg.get("vix_median_window", 252)
STD_MULTIPLIER = 1.0

def load_table(table_name):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(f"SELECT * FROM {table_name}", conn, parse_dates=["timestamp"])
    conn.close()
    return df

def compute_implied_move(option_df, spot_price, days_to_expiry):
    # Mid = (bid+ask)/2 for both call & put at ATM
    atm_calls = option_df[option_df["putCall"]=="C"].assign(mid=lambda d: (d.bid+d.ask)/2)
    atm_puts  = option_df[option_df["putCall"]=="P"].assign(mid=lambda d: (d.bid+d.ask)/2)
    atm_straddle = atm_calls.mid.mean() + atm_puts.mid.mean()
    return atm_straddle/spot_price * np.sqrt(365/days_to_expiry)

def compute_realized_move(under_df):
    under_df = under_df.sort_values("timestamp").set_index("timestamp")
    returns = under_df.price.pct_change().dropna()
    sigma = returns.rolling(20).std().iloc[-1]
    return sigma * np.sqrt(365/20)

def make_signal():
    # 1) Load data
    today = datetime.utcnow().strftime("%Y%m%d")
    opt_tbl = f"options_{today}"
    opt_df = load_table(opt_tbl)
    vix_df = load_table("vix_curve")
    und_df = load_table("underlyings")

    # 2) Spot price
    spot = und_df.price.iloc[-1]

    # 3) Days to expiry
    dte = (pd.to_datetime(opt_df.expiry.iloc[0], format="%Y%m%d") - datetime.utcnow()).days

    # 4) Implied vs. Realized
    implied = compute_implied_move(opt_df, spot, dte)
    realized = compute_realized_move(und_df)

    # 5) VIX front vs. median
    vix_front = vix_df[vix_df.contract=="VX"].price.iloc[-1]
    med = vix_df.price.rolling(VIX_MED_WINDOW).median().iloc[-1]

    enter = (implied/realized) > (1 + STD_MULTIPLIER) and (vix_front > med)

    signal = {
        "timestamp": datetime.utcnow().isoformat(),
        "implied_move": float(implied),
        "realized_move": float(realized),
        "vix_front": float(vix_front),
        "vix_median": float(med),
        "enter_trade": enter,
        "dte": int(dte)
    }

    # 6) Output JSON
    os.makedirs("signals", exist_ok=True)
    with open("signals/latest_signal.json", "w") as f:
        json.dump(signal, f, indent=2)

if __name__ == "__main__":
    make_signal()