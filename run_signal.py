"""
Cloud Signal Runner — IC + 0-DTE Only
======================================
Sends ONLY theta-based signals:
  1. Iron Condor (on SIDEWAYS days, sweet-spot ≥ 3)
  2. 0-DTE Iron Condor (every day if ADX ≤ 35)

No directional BUY/SELL signals.
Premiums are estimated — verify on broker before entering.

GitHub Actions cron:
    cron: '30 1 * * 1-5'   (Mon-Fri 1:30 AM UTC = 7:00 AM IST)
"""

import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from config import SYMBOLS, LOT_SIZE
from data_layer import fetch_daily_data, fetch_vix
from strategy import generate_signal, calculate_indicators
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
                "theta":    None,
                "sweet":    None,
                "dte_ic":   None,
            }

            # Theta IC (for SIDEWAYS days, ADX < 20)
            if regime == 'SIDEWAYS' and adx < 20:
                try:
                    setups = get_theta_setups(name, signal, vix_val, df)
                    sweet  = _sweet_spot_score(name, signal, vix_val, df)
                    sym_data['sweet'] = sweet
                    if setups:
                        s = setups[0]
                        # Calculate per-leg premiums for IC
                        lot_size  = LOT_SIZE.get(name, 50)
                        round_to  = 100 if name == 'BANKNIFTY' else 50
                        sigma_ic  = vix_val / 100.0
                        t_ic      = 7 / 365.0
                        # Use backtest-optimised strikes from theta_strategy (2.5x ATR)
                        sc_strike = s.get('sell_call_strike', int(round((price + atr * 2.5) / round_to) * round_to))
                        bc_strike = s.get('buy_call_strike', sc_strike + round_to)
                        sp_strike = s.get('sell_put_strike', int(round((price - atr * 2.5) / round_to) * round_to))
                        bp_strike = s.get('buy_put_strike', sp_strike - round_to)

                        def _ic_prem(strike):
                            m = abs(price - strike) / price
                            atm = price * sigma_ic * math.sqrt(t_ic) * 0.40
                            decay = math.exp(-0.5 * (m / (sigma_ic * math.sqrt(t_ic) + 1e-6))**2)
                            return max(5.0, round(atm * decay, 0))

                        sym_data['theta'] = {
                            "name":       s.get('name'),
                            "legs":       s.get('legs', []),
                            "credit":     s.get('net_credit', 0),
                            "max_profit": s.get('max_profit', 0),
                            "max_loss":   s.get('max_loss', 0),
                            "sell_call": sc_strike, "buy_call": bc_strike,
                            "sell_put": sp_strike, "buy_put": bp_strike,
                            "sc_prem": _ic_prem(sc_strike), "bc_prem": _ic_prem(bc_strike),
                            "sp_prem": _ic_prem(sp_strike), "bp_prem": _ic_prem(bp_strike),
                            "lot_size": lot_size,
                        }
                except Exception:
                    pass

            # 0-DTE on Thursdays only (weekly expiry day)
            if is_thursday:
                if adx > 25:
                    sym_data['dte_ic'] = {"skip": True, "reason": f"ADX {adx:.1f} > 25"}
                else:
                    lot_size  = LOT_SIZE.get(name, 50)
                    round_to  = 100 if name == 'BANKNIFTY' else 50
                    buffer    = atr * 1.5
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
                        "sc_prem": sc_p, "bc_prem": bc_p,
                        "sp_prem": sp_p, "bp_prem": bp_p,
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

        reg_emoji = {"TRENDING": "📈", "SIDEWAYS": "↔️", "VOLATILE": "⚡"}.get(regime, "❓")
        lines.append(f"{reg_emoji} Regime: <b>{regime}</b>  |  ADX: {adx:.1f}")
        lines.append(f"💰 Market Price: <b>{price:,.0f}</b>")

        # ── SIDEWAYS: Theta IC ──
        if regime == 'SIDEWAYS':
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
                t_lot      = theta.get('lot_size', lot)
                lines.append(f"✅ <b>SELL IRON CONDOR</b>  (Sweet-spot: {sc}/5)")
                lines.append(f"   📌 Action : Sell Iron Condor at 9:15 AM")
                lines.append("")
                lines.append(f"   📋 <b>CALL LEG (CE):</b>")
                lines.append(f"   ▸ SELL: <b>{sym} {theta['sell_call']} CE</b>  @ ≈₹{theta['sc_prem']:.0f}")
                lines.append(f"   ▸ BUY:  <b>{sym} {theta['buy_call']} CE</b>  @ ≈₹{theta['bc_prem']:.0f}")
                lines.append(f"   📋 <b>PUT LEG (PE):</b>")
                lines.append(f"   ▸ SELL: <b>{sym} {theta['sell_put']} PE</b>  @ ≈₹{theta['sp_prem']:.0f}")
                lines.append(f"   ▸ BUY:  <b>{sym} {theta['buy_put']} PE</b>  @ ≈₹{theta['bp_prem']:.0f}")
                lines.append("")
                sc_cost = int(theta['sc_prem'] * t_lot)
                sp_cost = int(theta['sp_prem'] * t_lot)
                lines.append(f"   💰 You Receive  : <b>+{credit:.0f} pts = ₹{profit_rs:,}</b>")
                lines.append(f"   💵 Per lot: SELL CE ₹{sc_cost:,} + SELL PE ₹{sp_cost:,}")
                lines.append(f"   🎯 Max Profit   : ₹{profit_rs:,}  (keep if stays sideways)")
                lines.append(f"   🛑 Max Loss     : ₹{loss_rs:,}  (if market breaks out)")
                lines.append(f"   📦 Lot size     : {t_lot}")
            else:
                lines.append(f"⏭️ <b>IC SKIP</b> — Sideways but conditions not ideal ({sc}/5, need ≥3)")

        elif regime == 'VOLATILE':
            lines.append(f"⚡ <b>VOLATILE — STAND ASIDE</b>")
            lines.append(f"   No trade today. Preserve capital.")

        # ── 0-DTE IC (every day) ──
        dte = sd.get('dte_ic')
        if dte:
            lines.append("")
            if dte.get('skip'):
                lines.append(f"🕐 0-DTE IC: <b>SKIP</b> — {dte.get('reason', '')}")
            else:
                lot_sz = dte.get('lot_size', LOT_SIZE.get(sym, 50))
                credit_rs = int(dte['credit'] * lot_sz)
                lines.append(f"🕐 <b>0-DTE IRON CONDOR</b> (expires today)")
                lines.append(f"")
                lines.append(f"   📋 <b>CALL LEG (CE):</b>")
                lines.append(f"   ▸ SELL: <b>{sym} {dte['sell_call']} CE</b>  @ ≈₹{dte['sc_prem']:.0f}")
                lines.append(f"   ▸ BUY:  <b>{sym} {dte['buy_call']} CE</b>  @ ≈₹{dte['bc_prem']:.0f}")
                lines.append(f"   📋 <b>PUT LEG (PE):</b>")
                lines.append(f"   ▸ SELL: <b>{sym} {dte['sell_put']} PE</b>  @ ≈₹{dte['sp_prem']:.0f}")
                lines.append(f"   ▸ BUY:  <b>{sym} {dte['buy_put']} PE</b>  @ ≈₹{dte['bp_prem']:.0f}")
                lines.append(f"")
                sc_cost = int(dte['sc_prem'] * lot_sz)
                sp_cost = int(dte['sp_prem'] * lot_sz)
                lines.append(f"   💰 Net Credit : <b>+{dte['credit']:.0f} pts = ₹{credit_rs:,}</b>")
                lines.append(f"   💵 Per lot: SELL CE ₹{sc_cost:,} + SELL PE ₹{sp_cost:,}")
                lines.append(f"   📊 Safe Zone  : {dte['sell_put']} – {dte['sell_call']}")
                lines.append(f"   📦 Lot size     : {lot_sz}")

        lines.append("")

    lines.append("<i>⏰ Enter 9:15–9:30 AM. Premiums estimated — verify on broker.</i>")
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
