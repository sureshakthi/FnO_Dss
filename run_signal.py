"""
Cloud Signal Runner — for PythonAnywhere / GitHub Actions
=========================================================
This script is the CLOUD VERSION of main.py.
  - No rich terminal colors (works headless on any server)
  - Fetches signal → sends to Telegram automatically
  - Schedule this to run at 7:00 AM IST (1:30 AM UTC) every weekday

PythonAnywhere schedule command:
    python /home/YOURUSERNAME/FnO_DSS/run_signal.py

GitHub Actions cron:
    cron: '30 1 * * 1-5'   (Mon-Fri 1:30 AM UTC = 7:00 AM IST)
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config import SYMBOLS, LOT_SIZE
from data_layer import fetch_daily_data, fetch_vix
from strategy import generate_signal, calculate_indicators
from risk import calculate_position
from theta_strategy import get_theta_setups
from telegram_notifier import send_message, is_configured


def _bb_width(df) -> float:
    try:
        close = df['Close'].values
        ma  = sum(close[-20:]) / 20
        std = (sum((c - ma)**2 for c in close[-20:]) / 20) ** 0.5
        return round((4 * std) / ma * 100, 2) if ma > 0 else 0.0
    except Exception:
        return 0.0


def _sweet_spot_score(symbol, signal, vix_value, df) -> dict:
    dow   = datetime.now().weekday()
    adx   = signal.get('adx', 0)
    bb_w  = _bb_width(df)
    score = 0

    if symbol == 'NIFTY':
        if dow == 4:        score += 2   # Friday
        if 17 <= adx <= 22: score += 1
        if 20 <= vix_value <= 25: score += 1
        if bb_w < 2.2:      score += 1
    else:  # BANKNIFTY
        if dow in (2, 3):   score += 2   # Wed/Thu
        if adx < 17:        score += 1
        if 20 <= vix_value <= 25: score += 1
        if bb_w > 3.4:      score += 1

    return {"score": score, "max_score": 5, "is_sweet": score >= 3}


def build_signal_data() -> dict:
    """Run full signal pipeline and return data dict for Telegram."""
    today = datetime.now()
    is_thursday = (today.weekday() == 3)

    # VIX
    try:
        vix_info = fetch_vix()
    except Exception:
        vix_info = {"value": 0.0, "prev": 0.0, "change_pct": 0.0, "level": "UNKNOWN"}

    vix_val = vix_info.get('value', 0.0)

    result = {
        "date":      today.strftime("%A, %d %B %Y"),
        "timestamp": today.strftime("%A, %d %B %Y"),
        "vix":       vix_info,
        "symbols":   {},
    }

    for name, ticker in SYMBOLS.items():
        try:
            df     = fetch_daily_data(ticker)
            signal = generate_signal(df)
            regime = signal.get('regime', 'UNKNOWN')
            adx    = signal.get('adx', 0)
            price  = signal.get('current_price', float(df['Close'].iloc[-1]))
            atr    = signal.get('atr', price * 0.015)

            sym_data = {
                "regime":   regime,
                "adx":      adx,
                "price":    price,
                "signal":   signal.get('signal', 'NEUTRAL'),
                "score":    signal.get('signal_score', 0),
                "reasons":  signal.get('reasons', []),
                "pos":      None,
                "theta":    None,
                "sweet":    None,
                "dte_ic":   None,
            }

            # Position sizing (for TRENDING breakout)
            if regime == 'TRENDING' and sym_data['signal'] in ('BUY', 'SELL'):
                try:
                    pos = calculate_position(signal)
                    sym_data['pos'] = {
                        "entry":  pos.get('entry_price'),
                        "sl":     pos.get('stop_loss'),
                        "target": pos.get('target'),
                        "lots":   pos.get('lots', 1),
                    }
                except Exception:
                    pass

            # Theta setups (for SIDEWAYS)
            if regime == 'SIDEWAYS':
                try:
                    setups = get_theta_setups(name, signal, vix_val, df)
                    sweet  = _sweet_spot_score(name, signal, vix_val, df)
                    sym_data['sweet'] = sweet
                    if setups:
                        s = setups[0]
                        sym_data['theta'] = {
                            "name":       s.get('name'),
                            "legs":       s.get('legs', []),
                            "credit":     s.get('net_credit', 0),
                            "max_profit": s.get('max_profit', 0),
                            "max_loss":   s.get('max_loss', 0),
                        }
                except Exception:
                    pass

            # 0-DTE on Thursdays
            if is_thursday:
                if adx > 35:
                    sym_data['dte_ic'] = {"skip": True, "reason": f"ADX {adx:.1f} > 35"}
                else:
                    lot_size  = LOT_SIZE.get(name, 50)
                    round_to  = 100 if name == 'BANKNIFTY' else 50
                    buffer    = atr * 0.6
                    sell_call = int(round((price + buffer) / round_to) * round_to)
                    buy_call  = sell_call + round_to
                    sell_put  = int(round((price - buffer) / round_to) * round_to)
                    buy_put   = sell_put  - round_to

                    def _prem(strike):
                        m = abs(price - strike) / price
                        sigma = vix_val / 100.0
                        t = 1 / 365.0
                        atm = price * sigma * math.sqrt(t) * 0.40
                        decay = math.exp(-0.5 * (m / (sigma * math.sqrt(t) + 1e-6))**2)
                        return max(3.0, round(atm * decay, 0))

                    sc_p = _prem(sell_call)
                    bc_p = _prem(buy_call)
                    sp_p = _prem(sell_put)
                    bp_p = _prem(buy_put)
                    net  = round(sc_p + sp_p - bc_p - bp_p, 0)
                    sym_data['dte_ic'] = {
                        "skip":     False,
                        "sell_call": sell_call, "buy_call": buy_call,
                        "sell_put":  sell_put,  "buy_put":  buy_put,
                        "credit":    net,
                        "lot_size":  lot_size,
                    }

            result["symbols"][name] = sym_data

        except Exception as e:
            result["symbols"][name] = {"error": str(e)}

    return result


def _format_telegram_message(data: dict) -> str:
    """Format signal data as a clean Telegram message (HTML)."""
    lines = []

    # ── Header ──
    vix = data.get('vix', {})
    vix_val = vix.get('value', 0) if isinstance(vix, dict) else float(vix)
    vix_chg = vix.get('change_pct', 0) if isinstance(vix, dict) else 0
    vix_lvl = vix.get('level', '') if isinstance(vix, dict) else ''
    vix_emoji = "🔴" if vix_val >= 25 else "🟡" if vix_val >= 18 else "🟢"
    lines.append(f"🇮🇳 <b>F&amp;O Signal — {data['date']}</b>")
    lines.append(f"🌡️ India VIX: <b>{vix_val:.1f}</b>  {vix_emoji} {vix_lvl}  ({vix_chg:+.1f}%)")
    lines.append("")

    for sym, sd in data.get('symbols', {}).items():
        lines.append(f"{'━'*8} {sym} {'━'*8}")

        if 'error' in sd:
            lines.append(f"⚠️ Data error — skipping")
            lines.append("")
            continue

        regime  = sd.get('regime', '?')
        price   = sd.get('price', 0)
        adx     = sd.get('adx', 0)
        signal  = sd.get('signal', 'NEUTRAL')
        score   = sd.get('score', 0)

        reg_emoji = {"TRENDING": "📈", "SIDEWAYS": "↔️", "VOLATILE": "⚡"}.get(regime, "❓")
        lines.append(f"{reg_emoji} Regime: <b>{regime}</b>  |  ADX: {adx:.1f}")
        lines.append(f"💰 Market Price: <b>{price:,.0f}</b>")

        # ── TRENDING: BUY or SELL ──
        if regime == 'TRENDING' and signal in ('BUY', 'SELL'):
            sig_emoji = "🟢" if signal == 'BUY' else "🔴"
            lines.append(f"{sig_emoji} <b>SIGNAL: {signal}</b>  (Score: {score}/6)")
            pos = sd.get('pos')
            lot = LOT_SIZE.get(sym, 50)
            if pos:
                entry  = pos.get('entry') or price
                sl     = pos.get('sl') or 0
                target = pos.get('target') or 0
                lots   = pos.get('lots', 1)
                profit_pts = abs(target - entry)
                loss_pts   = abs(entry - sl)
                profit_rs  = int(profit_pts * lot * lots)
                loss_rs    = int(loss_pts * lot * lots)
                lines.append(f"   📌 Entry  : <b>{entry:,.0f}</b>")
                lines.append(f"   🎯 Target : <b>{target:,.0f}</b>  (+{profit_pts:.0f} pts = <b>₹{profit_rs:,} profit</b>)")
                lines.append(f"   🛑 SL     : <b>{sl:,.0f}</b>  (-{loss_pts:.0f} pts = <b>₹{loss_rs:,} loss</b>)")
                lines.append(f"   📦 Lots   : {lots}  ×  {lot} qty = {lots * lot} units")
            else:
                lines.append(f"   📌 Entry at market open (9:15 AM)")

        # ── TRENDING: NEUTRAL ──
        elif regime == 'TRENDING' and signal == 'NEUTRAL':
            lines.append(f"⚪ <b>NEUTRAL</b> — Trend weak. No trade today.")

        # ── SIDEWAYS: Theta IC ──
        elif regime == 'SIDEWAYS':
            sweet = sd.get('sweet') or {}
            sc    = sweet.get('score', 0)
            is_sw = sweet.get('is_sweet', False)
            theta = sd.get('theta')
            lot   = LOT_SIZE.get(sym, 50)

            if is_sw and theta:
                credit     = theta.get('credit', 0)
                max_loss   = theta.get('max_loss', 0)
                profit_rs  = int(credit * lot)
                loss_rs    = int(max_loss * lot)
                legs       = theta.get('legs', [])
                lines.append(f"✅ <b>SELL IRON CONDOR</b>  (Sweet-spot: {sc}/5)")
                lines.append(f"   📌 Action : Sell Iron Condor at 9:15 AM")
                lines.append(f"   📊 Market Price: <b>{price:,.0f}</b>")
                lines.append("")
                if legs:
                    for leg in legs:
                        lines.append(f"   {leg}")
                lines.append("")
                lines.append(f"   💰 You Receive  : <b>+{credit:.0f} pts = ₹{profit_rs:,}</b>")
                lines.append(f"   🎯 Max Profit   : ₹{profit_rs:,}  (keep if stays sideways)")
                lines.append(f"   🛑 Max Loss     : ₹{loss_rs:,}  (if market breaks out)")
                lines.append(f"   📦 Lot size     : {lot}")
            else:
                lines.append(f"⏭️ <b>SKIP</b> — Market sideways but conditions not ideal ({sc}/5, need ≥3)")
                lines.append(f"   No trade today.")

        # ── VOLATILE ──
        elif regime == 'VOLATILE':
            lines.append(f"⚡ <b>VOLATILE — STAND ASIDE</b>")
            lines.append(f"   No trade today. Preserve capital.")

        # ── 0-DTE Thursday IC ──
        dte = sd.get('dte_ic')
        if dte:
            lines.append("")
            if dte.get('skip'):
                lines.append(f"🕐 0-DTE IC: <b>SKIP</b> — {dte.get('reason', '')}")
            else:
                lot_sz = dte.get('lot_size', LOT_SIZE.get(sym, 50))
                credit_rs = int(dte['credit'] * lot_sz)
                lines.append(f"🕐 <b>0-DTE IRON CONDOR</b> (expires today)")
                lines.append(f"   📌 Enter at: <b>{price:,.0f}</b> (current price)")
                lines.append(f"   SELL {dte['sell_call']} CE | BUY {dte['buy_call']} CE")
                lines.append(f"   SELL {dte['sell_put']} PE  | BUY {dte['buy_put']} PE")
                lines.append(f"   💰 Net Credit : <b>+{dte['credit']:.0f} pts = ₹{credit_rs:,}</b>")
                lines.append(f"   📊 Safe Zone  : {dte['sell_put']} – {dte['sell_call']}")

        lines.append("")

    lines.append("<i>⏰ Enter 9:15–9:30 AM. Always set stop loss first.</i>")
    return "\n".join(lines)


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Building signals...")

    if not is_configured():
        print("ERROR: Telegram not configured.")
        print("Run:  python telegram_notifier.py --setup")
        sys.exit(1)

    data    = build_signal_data()
    message = _format_telegram_message(data)
    ok      = send_message(message)

    if ok:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Signal sent to Telegram!")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Telegram send failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
