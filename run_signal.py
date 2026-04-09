"""
Cloud Signal Runner — for PythonAnywhere / GitHub Actions
=========================================================
This script is the CLOUD VERSION of main.py.
  - No rich terminal colors (works headless on any server)
  - Fetches signal → sends to Telegram automatically
  - Schedule this to run at 9:10 AM IST (3:40 AM UTC) every weekday

PythonAnywhere schedule command:
    python /home/YOURUSERNAME/FnO_DSS/run_signal.py

GitHub Actions cron:
    cron: '40 3 * * 1-5'   (Mon-Fri 3:40 AM UTC = 9:10 AM IST)
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config import SYMBOLS, LOT_SIZE
from data_layer import fetch_daily_data, fetch_vix
from strategy import generate_signal, calculate_indicators
from risk import calculate_position
from theta_strategy import get_theta_setups
from telegram_notifier import send_signal_summary, is_configured


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

    result = {
        "date":    today.strftime("%A, %d %B %Y"),
        "vix":     vix_info,
        "symbols": {},
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
    lines.append(f"<b>F&O Signal — {data['date']}</b>")
    vix = data.get('vix', 0)
    vix_emoji = "🔴" if vix >= 25 else "🟡" if vix >= 18 else "🟢"
    lines.append(f"{vix_emoji} India VIX: <b>{vix:.1f}</b>")
    lines.append("")

    for sym, sd in data.get('symbols', {}).items():
        if 'error' in sd:
            lines.append(f"<b>{sym}</b>: ⚠️ Error — {sd['error']}")
            continue

        regime  = sd.get('regime', '?')
        price   = sd.get('price', 0)
        adx     = sd.get('adx', 0)
        signal  = sd.get('signal', 'NEUTRAL')
        score   = sd.get('score', 0)

        reg_emoji = {"TRENDING": "📈", "SIDEWAYS": "↔️", "VOLATILE": "⚡"}.get(regime, "❓")
        lines.append(f"{reg_emoji} <b>{sym}</b> @ {price:,.0f}  |  Regime: <b>{regime}</b>  |  ADX: {adx:.1f}")

        if regime == 'TRENDING' and signal in ('BUY', 'SELL'):
            sig_emoji = "🟢" if signal == 'BUY' else "🔴"
            lines.append(f"  {sig_emoji} Signal: <b>{signal}</b>  (Score: {score}/6)")
            pos = sd.get('pos')
            if pos:
                lines.append(f"  Entry : {pos['entry']:,.0f}")
                lines.append(f"  SL    : {pos['sl']:,.0f}")
                lines.append(f"  Target: {pos['target']:,.0f}")
                lines.append(f"  Lots  : {pos['lots']}")
        elif regime == 'SIDEWAYS':
            sweet = sd.get('sweet', {})
            sc    = sweet.get('score', 0)
            is_sw = sweet.get('is_sweet', False)
            if is_sw:
                lines.append(f"  ✅ Sweet-spot: {sc}/5 — ENTER THETA IC")
                theta = sd.get('theta')
                if theta:
                    lines.append(f"  Name: {theta.get('name')}")
                    lines.append(f"  Net Credit: +{theta.get('credit', 0):.0f} pts")
                    lines.append(f"  Max Profit: +{theta.get('max_profit', 0):.0f} pts")
                    lines.append(f"  Max Loss  : -{theta.get('max_loss', 0):.0f} pts")
            else:
                lines.append(f"  ⏭️ Sweet-spot: {sc}/5 — SKIP (need ≥3)")
        elif regime == 'VOLATILE':
            lines.append("  ⚡ Market VOLATILE — Stand Aside. No trade today.")

        # 0-DTE Thursday
        dte = sd.get('dte_ic')
        if dte:
            if dte.get('skip'):
                lines.append(f"  🕐 0-DTE IC: SKIP ({dte.get('reason', '')})")
            else:
                lines.append(f"  🕐 0-DTE IC (expires today):")
                lines.append(f"     SELL {dte['sell_call']} CE | BUY {dte['buy_call']} CE")
                lines.append(f"     SELL {dte['sell_put']}  PE | BUY {dte['buy_put']}  PE")
                lines.append(f"     Net Credit: +{dte['credit']:.0f} pts")
                lines.append(f"     Safe Zone: {dte['sell_put']} – {dte['sell_call']}")
        lines.append("")

    lines.append("<i>Entry at 9:15–9:30 AM. Always set stop loss.</i>")
    return "\n".join(lines)


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Building signals...")

    if not is_configured():
        print("ERROR: Telegram not configured.")
        print("Run:  python telegram_notifier.py --setup")
        sys.exit(1)

    data    = build_signal_data()
    message = _format_telegram_message(data)

    # Try structured send first, fall back to plain text
    ok = send_signal_summary(data)
    if not ok:
        # Fallback: send plain formatted text directly
        from telegram_notifier import send_message
        ok = send_message(message)

    if ok:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Signal sent to Telegram!")
    else:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Telegram send failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
