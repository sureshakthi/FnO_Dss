import warnings
import json
from datetime import datetime, timezone

import requests
import pandas as pd
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import SYMBOLS

PROXY   = "http://proxy.cat.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://finance.yahoo.com/",
}

def _make_session(use_proxy: bool = True) -> requests.Session:
    s = requests.Session()
    if use_proxy:
        s.proxies = {"http": PROXY, "https": PROXY}
    s.verify  = False
    s.headers.update(HEADERS)
    return s

def _test_proxy() -> bool:
    try:
        r = requests.get("https://finance.yahoo.com",
                         proxies={"http": PROXY, "https": PROXY},
                         timeout=4, verify=False)
        return r.status_code < 500
    except Exception:
        return False

_USE_PROXY = _test_proxy()
SESSION    = _make_session(_USE_PROXY)

YF_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"


def _fetch_chart(ticker: str, interval: str, range_str: str) -> pd.DataFrame:
    url = f"{YF_BASE}/{ticker}"
    params = {
        "interval": interval,
        "range":    range_str,
        "indicators": "quote",
        "includeTimestamps": "true",
    }
    try:
        r = SESSION.get(url, params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        result = data["chart"]["result"][0]
        ts     = result["timestamp"]
        q      = result["indicators"]["quote"][0]
        df = pd.DataFrame({
            "Open":   q["open"],
            "High":   q["high"],
            "Low":    q["low"],
            "Close":  q["close"],
            "Volume": q["volume"],
        }, index=pd.to_datetime(ts, unit="s", utc=True))
        df.index = df.index.tz_convert("Asia/Kolkata")
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[ERROR] _fetch_chart({ticker}, {interval}, {range_str}): {e}")
        return pd.DataFrame()


def fetch_daily_data(symbol_key: str, days: int = 60) -> pd.DataFrame:
    ticker  = SYMBOLS.get(symbol_key, symbol_key).replace("^", "%5E")
    range_s = f"{min(days, 100)}d" if days <= 100 else "1y"
    return _fetch_chart(ticker, "1d", range_s)


def fetch_intraday_data(symbol_key: str, interval: str = "5m") -> pd.DataFrame:
    ticker = SYMBOLS.get(symbol_key, symbol_key).replace("^", "%5E")
    return _fetch_chart(ticker, interval, "1d")


def get_current_price(symbol_key: str) -> float:
    df = fetch_daily_data(symbol_key, days=2)
    if not df.empty:
        return float(df["Close"].iloc[-1])
    return 0.0


def fetch_vix() -> dict:
    df = _fetch_chart("%5EINDIAVIX", "1d", "5d")
    if df.empty or len(df) < 2:
        return {"value": 0.0, "prev": 0.0, "change_pct": 0.0, "level": "UNKNOWN"}
    val  = float(df["Close"].iloc[-1])
    prev = float(df["Close"].iloc[-2])
    chg  = round((val - prev) / prev * 100, 2) if prev else 0.0
    if val < 13:
        level = "LOW (complacent)"
    elif val < 20:
        level = "NORMAL"
    elif val < 30:
        level = "ELEVATED (caution)"
    else:
        level = "HIGH (panic/fear)"
    return {"value": round(val, 2), "prev": round(prev, 2),
            "change_pct": chg, "level": level}
