import csv
import os
from datetime import datetime

import pandas as pd

TRADES_FILE = os.path.join(os.path.dirname(__file__), "trades_log.csv")

FIELDNAMES = [
    'date', 'symbol', 'direction', 'action',
    'entry', 'sl', 'target',
    'day_open', 'day_high', 'day_low', 'day_close',
    'result', 'exit_price', 'pnl_points', 'pnl_inr',
    'brokerage', 'net_pnl',
    'signal_strength', 'regime', 'weekly_trend', 'rsi', 'adx', 'vol_ratio',
    'reasons',
]


def load_trades() -> list:
    if not os.path.exists(TRADES_FILE):
        return []
    with open(TRADES_FILE, 'r', newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def save_trade(trade: dict):
    exists = os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
        if not exists:
            writer.writeheader()
        writer.writerow(trade)


def simulate_eod_result(position: dict,
                        day_open:  float,
                        day_high:  float,
                        day_low:   float,
                        day_close: float,
                        brokerage: float = 0.0) -> dict:
    """
    Realistic simulation:
    - Entry at day_open (signal fires EOD, execute at NEXT day's open)
    - Check if SL or Target hit during that day (using High/Low)
    - Conservative: if both SL and Target hit, assume SL hit first
    """
    if position.get('direction') == 'NEUTRAL':
        return {"result": "NO_TRADE", "exit_price": 0,
                "pnl_points": 0, "pnl_inr": 0, "brokerage": 0, "net_pnl": 0}

    entry     = day_open       # â† enter at next day's OPEN (realistic)
    target    = position['target_index']
    sl        = position['sl_index']
    direction = position['direction']

    # Recalculate SL/Target relative to actual open (not previous close)
    sl_dist  = position['sl_distance']
    tgt_dist = position['target_distance']
    if direction == "BUY":
        sl     = round(entry - sl_dist, 2)
        target = round(entry + tgt_dist, 2)
        sl_hit  = day_low  <= sl
        tgt_hit = day_high >= target
        if sl_hit and tgt_hit:
            result, exit_p = "SL_HIT", sl          # worst-case
        elif tgt_hit:
            result, exit_p = "TARGET_HIT", target
        elif sl_hit:
            result, exit_p = "SL_HIT", sl
        else:
            result, exit_p = "OPEN", day_close
        pnl_pts = exit_p - entry
    else:  # SELL signal â†’ PE
        sl     = round(entry + sl_dist, 2)
        target = round(entry - tgt_dist, 2)
        sl_hit  = day_high >= sl
        tgt_hit = day_low  <= target
        if sl_hit and tgt_hit:
            result, exit_p = "SL_HIT", sl
        elif tgt_hit:
            result, exit_p = "TARGET_HIT", target
        elif sl_hit:
            result, exit_p = "SL_HIT", sl
        else:
            result, exit_p = "OPEN", day_close
        pnl_pts = entry - exit_p

    pnl_inr = round(pnl_pts, 2)
    net_pnl = round(pnl_inr - brokerage, 2)

    return {
        "result":     result,
        "exit_price": round(exit_p, 2),
        "entry_used": entry,
        "pnl_points": round(pnl_pts, 2),
        "pnl_inr":    pnl_inr,
        "brokerage":  brokerage,
        "net_pnl":    net_pnl,
    }


def get_eod_report() -> dict:
    trades = load_trades()
    if not trades:
        return {}

    df = pd.DataFrame(trades)
    for col in ['pnl_inr', 'pnl_points', 'net_pnl', 'brokerage']:
        df[col] = pd.to_numeric(df.get(col, 0), errors='coerce').fillna(0)

    done  = df[df['result'].isin(['TARGET_HIT', 'SL_HIT'])]
    total = len(done)
    wins  = int((done['result'] == 'TARGET_HIT').sum())
    losses = int((done['result'] == 'SL_HIT').sum())
    win_rate  = round(wins / total * 100, 1) if total else 0
    total_pnl = round(df['net_pnl'].sum(), 2)
    total_brk = round(df['brokerage'].sum(), 2)

    avg_win  = round(done[done['result'] == 'TARGET_HIT']['net_pnl'].mean(), 2) if wins   else 0
    avg_loss = round(done[done['result'] == 'SL_HIT']['net_pnl'].mean(),     2) if losses else 0

    # Max drawdown
    cumulative = df['net_pnl'].cumsum()
    running_max = cumulative.cummax()
    drawdown    = (cumulative - running_max)
    max_dd      = round(float(drawdown.min()), 2)

    # Consecutive losses
    results_list = df['result'].tolist()
    max_streak = cur_streak = 0
    for r in results_list:
        if r == 'SL_HIT':
            cur_streak += 1
            max_streak = max(max_streak, cur_streak)
        else:
            cur_streak = 0

    return {
        "total_trades":    total,
        "wins":            wins,
        "losses":          losses,
        "open_trades":     int((df['result'] == 'OPEN').sum()),
        "win_rate":        win_rate,
        "total_pnl_inr":   total_pnl,
        "total_brokerage": total_brk,
        "avg_win":         avg_win,
        "avg_loss":        avg_loss,
        "max_drawdown":    max_dd,
        "max_loss_streak": max_streak,
        "recent_trades":   trades[-10:],
    }


def update_open_trades(daily_data: dict) -> int:
    """
    Re-check any OPEN trades against actual price data that came in since.
    daily_data = {"NIFTY": df, "BANKNIFTY": df}
    Returns the number of trades updated.
    """
    trades = load_trades()
    updated_count = 0

    for i, trade in enumerate(trades):
        if trade.get('result') != 'OPEN':
            continue

        symbol    = trade.get('symbol', '')
        direction = trade.get('direction', 'NEUTRAL')
        df        = daily_data.get(symbol)
        if df is None or df.empty or direction == 'NEUTRAL':
            continue

        trade_date = trade.get('date', '')[:10]
        # Get all rows AFTER the trade date
        try:
            df_after = df[df.index.strftime('%Y-%m-%d') > trade_date]
        except Exception:
            continue
        if df_after.empty:
            continue

        try:
            entry   = float(trade.get('entry', 0))
            sl_raw  = float(trade.get('sl', 0))
            tgt_raw = float(trade.get('target', 0))
            brk     = float(trade.get('brokerage', 0))
        except (ValueError, TypeError):
            continue
        if entry == 0:
            continue

        sl     = sl_raw  if sl_raw  else (entry * 0.994 if direction == "BUY" else entry * 1.006)
        target = tgt_raw if tgt_raw else (entry * 1.012 if direction == "BUY" else entry * 0.988)

        result = "OPEN"
        exit_p = float(df_after['Close'].iloc[-1])   # default: last known close

        for _, row in df_after.iterrows():
            hi = float(row['High'])
            lo = float(row['Low'])
            sl_hit  = (lo <= sl)     if direction == "BUY" else (hi >= sl)
            tgt_hit = (hi >= target) if direction == "BUY" else (lo <= target)
            if sl_hit and tgt_hit:
                result, exit_p = "SL_HIT", sl
                break
            elif tgt_hit:
                result, exit_p = "TARGET_HIT", target
                break
            elif sl_hit:
                result, exit_p = "SL_HIT", sl
                break

        if result != "OPEN":
            pnl_pts = round((exit_p - entry) if direction == "BUY" else (entry - exit_p), 2)
            net_pnl = round(pnl_pts - brk, 2)
            trades[i]['result']      = result
            trades[i]['exit_price']  = str(round(exit_p, 2))
            trades[i]['pnl_points']  = str(pnl_pts)
            trades[i]['pnl_inr']     = str(pnl_pts)
            trades[i]['net_pnl']     = str(net_pnl)
            updated_count += 1

    if updated_count > 0:
        with open(TRADES_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(trades)

    return updated_count

