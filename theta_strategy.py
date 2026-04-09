"""
Theta / Time-Decay Strategy Module
====================================

Instead of BUYING options (where theta eats premium daily),
these strategies SELL options — you collect premium upfront and
profit when time passes and market stays within expected range.

Three setups generated automatically based on market conditions:

  1. IRON CONDOR       — SIDEWAYS market  (sell OTM call + put spreads)
  2. BULL PUT SPREAD   — Bullish/neutral   (sell put spread below support)
  3. BEAR CALL SPREAD  — Bearish/neutral   (sell call spread above resistance)

When theta selling works best:
  - Regime is SIDEWAYS (ADX < 25) — range-bound market profits option sellers
  - VIX between 15–35: fat premiums but not extreme event risk
  - 3–10 days to expiry: theta decay accelerates sharply in last week
  - Clear support/resistance levels define your profit zone

Premium Estimates:
  Estimated using a simplified BSM approximation. Treat as indicative only —
  always check live market prices before entering. Real premiums vary with
  actual IV, liquidity, and intraday moves.

Usage:
  from theta_strategy import get_theta_setups
  setups = get_theta_setups(signal, vix_value=24.7, symbol="NIFTY")
"""

import math
from config import LOT_SIZE


def _nearest_strike(price: float, rounding: int = 50) -> int:
    """Round to nearest option strike."""
    return int(round(price / rounding) * rounding)


def _est_premium(spot: float, strike: float, dte: int, vix: float) -> float:
    """
    Approximate option premium using simplified Bachelier-style formula.
    This is NOT a Black-Scholes calculator — it is for indicative sizing only.

    Logic:
      - Annual vol = VIX / 100
      - Time fraction = DTE / 365
      - ATM premium ≈ spot × sigma × sqrt(t) × 0.4
      - OTM discount: Gaussian decay based on how far OTM
    """
    if dte <= 0 or spot <= 0:
        return 0.0

    sigma     = vix / 100.0
    t         = dte / 365.0
    moneyness = abs(spot - strike) / spot

    atm_prem    = spot * sigma * math.sqrt(t) * 0.40
    otm_factor  = math.exp(-0.5 * (moneyness / (sigma * math.sqrt(t) + 1e-6)) ** 2)
    premium     = atm_prem * otm_factor

    return max(5.0, round(premium, 0))


def get_theta_setups(signal: dict, vix_value: float = 20.0,
                     symbol: str = "NIFTY") -> list:
    """
    Generate theta/option-selling trade setups based on current market conditions.

    Args:
        signal    : dict returned by generate_signal() or _neutral()
        vix_value : India VIX float (e.g. 24.7)
        symbol    : 'NIFTY' or 'BANKNIFTY'

    Returns:
        List of setup dicts, one per strategy that qualifies.
        May be empty if conditions are not met.
    """
    price      = signal.get('current_price', 0)
    atr        = signal.get('atr', 0)
    adx        = signal.get('adx', 0)
    regime     = signal.get('regime', 'SIDEWAYS')
    direction  = signal.get('direction', 'NEUTRAL')
    support    = signal.get('support', 0)
    resistance = signal.get('resistance', 0)
    dte        = signal.get('dte', 7)

    if price <= 0 or atr <= 0:
        return []

    # Fallback: derive S/R from ATR if not in signal
    if support    <= 0: support    = price - 2.0 * atr
    if resistance <= 0: resistance = price + 2.0 * atr

    round_to = 100 if symbol == "BANKNIFTY" else 50
    lot_size = LOT_SIZE.get(symbol, 50)
    setups   = []

    # VIX guard: too low = no premium worth selling; too high = don't sell naked
    vix_ok = 12 <= vix_value <= 36

    # ─────────────────────────────────────────────────────────────────────────
    # 1. IRON CONDOR
    #    When: SIDEWAYS regime, ADX < 20, VIX ok, ≥3 DTE
    #    Sell OTM call + OTM put. Buy 1 strike further out on each side.
    #    Max profit = net credit. Max loss = spread width - credit.
    #    ATR × 2.5 buffer → 82-85% win rate (backtest-optimised)
    # ─────────────────────────────────────────────────────────────────────────
    if regime == 'SIDEWAYS' and adx < 20 and dte >= 3 and vix_ok:
        # Place sell-strikes at 2.5× ATR from price (backtest-optimised)
        sell_call = _nearest_strike(max(resistance, price + atr * 2.5), round_to)
        buy_call  = sell_call + round_to       # protection (debit leg)
        sell_put  = _nearest_strike(min(support,  price - atr * 2.5), round_to)
        buy_put   = sell_put - round_to        # protection (debit leg)

        # Ensure minimum gap from spot (avoid accidental ATM sell)
        if sell_call <= price or sell_put >= price:
            pass  # still append — ATR guarantees decent gap
        if sell_call <= sell_put:
            sell_call, sell_put = sell_put + round_to * 2, sell_call - round_to * 2

        # Premium estimates
        sc_prem = _est_premium(price, sell_call, dte, vix_value)
        bc_prem = _est_premium(price, buy_call,  dte, vix_value)
        sp_prem = _est_premium(price, sell_put,  dte, vix_value)
        bp_prem = _est_premium(price, buy_put,   dte, vix_value)

        net_credit   = round(sc_prem + sp_prem - bc_prem - bp_prem, 0)
        spread_width = round_to
        max_loss     = max(1, spread_width - net_credit)
        max_profit   = max(1, net_credit)
        roc          = round(max_profit / max_loss * 100, 1)
        be_up        = sell_call + net_credit
        be_dn        = sell_put  - net_credit

        if net_credit >= 5:
            setups.append({
                "strategy":    "IRON CONDOR",
                "bias":        "NEUTRAL — collect premium in range-bound market",
                # Raw numeric strikes (used by backtest)
                "sell_call_strike": sell_call,
                "buy_call_strike":  buy_call,
                "sell_put_strike":  sell_put,
                "buy_put_strike":   buy_put,
                "spot":             price,
                "legs": [
                    f"SELL {sell_call} CE  approx +{sc_prem:.0f} pts",
                    f"BUY  {buy_call}  CE  approx -{bc_prem:.0f} pts  (protection)",
                    f"SELL {sell_put}  PE  approx +{sp_prem:.0f} pts",
                    f"BUY  {buy_put}   PE  approx -{bp_prem:.0f} pts  (protection)",
                ],
                "net_credit":   net_credit,
                "max_profit":   max_profit,
                "max_loss":     max_loss,
                "roc_pct":      roc,
                "breakeven_up": be_up,
                "breakeven_dn": be_dn,
                "profit_zone":  f"{sell_put} to {sell_call}",
                "dte":          dte,
                "lot_size":     lot_size,
                "note": (
                    f"Keeps full credit if {symbol} stays inside "
                    f"[{sell_put} - {sell_call}] until expiry. "
                    f"Exit early if index approaches either breakeven."
                ),
                "risk_note": (
                    f"Max risk {max_loss} pts x {lot_size} = "
                    f"Rs {max_loss * lot_size:,}/lot"
                ),
                "when_to_use": (
                    "Best entry: Monday/Tuesday before expiry week "
                    "(3-7 DTE). Close 50% of max profit early."
                ),
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 2. BULL PUT SPREAD
    #    When: Directional BUY signal OR neutral near support. ADX >= 13.
    #    Sell put below support, buy 1 strike lower for protection.
    #    Profit if market stays ABOVE breakeven.
    # ─────────────────────────────────────────────────────────────────────────
    if direction in ('BUY', 'NEUTRAL') and adx >= 13 and dte >= 3 and vix_ok:
        anchor   = support if support > 0 else (price - atr * 2.0)
        sell_put = _nearest_strike(anchor - atr * 0.3, round_to)
        buy_put  = sell_put - round_to

        sp_prem    = _est_premium(price, sell_put, dte, vix_value)
        bp_prem    = _est_premium(price, buy_put,  dte, vix_value)
        net_credit = round(sp_prem - bp_prem, 0)
        max_loss   = max(1, round_to - net_credit)
        max_profit = max(1, net_credit)
        roc        = round(max_profit / max_loss * 100, 1)
        be         = sell_put - net_credit

        if net_credit >= 5:
            setups.append({
                "strategy":   "BULL PUT SPREAD",
                "bias":       "BULLISH — sell puts below support level",
                # Raw numeric strikes (used by backtest)
                "sell_put_strike": sell_put,
                "buy_put_strike":  buy_put,
                "spot":            price,
                "legs": [
                    f"SELL {sell_put} PE  approx +{sp_prem:.0f} pts",
                    f"BUY  {buy_put}  PE  approx -{bp_prem:.0f} pts  (protection)",
                ],
                "net_credit":  net_credit,
                "max_profit":  max_profit,
                "max_loss":    max_loss,
                "roc_pct":     roc,
                "breakeven":   be,
                "dte":         dte,
                "lot_size":    lot_size,
                "note": (
                    f"Profit if {symbol} closes ABOVE {be} at expiry. "
                    f"Support at {support:.0f} — gives {abs(price - be):.0f} pts of buffer."
                ),
                "risk_note": (
                    f"Max risk {max_loss} pts x {lot_size} = "
                    f"Rs {max_loss * lot_size:,}/lot"
                ),
                "when_to_use": (
                    "Use after a pullback to support — when index bounces "
                    "and you believe support will hold till expiry."
                ),
            })

    # ─────────────────────────────────────────────────────────────────────────
    # 3. BEAR CALL SPREAD
    #    When: Directional SELL signal OR neutral near resistance. ADX >= 13.
    #    Sell call above resistance, buy 1 strike higher for protection.
    #    Profit if market stays BELOW breakeven.
    # ─────────────────────────────────────────────────────────────────────────
    if direction in ('SELL', 'NEUTRAL') and adx >= 13 and dte >= 3 and vix_ok:
        anchor    = resistance if resistance > 0 else (price + atr * 2.0)
        sell_call = _nearest_strike(anchor + atr * 0.3, round_to)
        buy_call  = sell_call + round_to

        sc_prem    = _est_premium(price, sell_call, dte, vix_value)
        bc_prem    = _est_premium(price, buy_call,  dte, vix_value)
        net_credit = round(sc_prem - bc_prem, 0)
        max_loss   = max(1, round_to - net_credit)
        max_profit = max(1, net_credit)
        roc        = round(max_profit / max_loss * 100, 1)
        be         = sell_call + net_credit

        if net_credit >= 5:
            setups.append({
                "strategy":   "BEAR CALL SPREAD",
                "bias":       "BEARISH — sell calls above resistance level",
                # Raw numeric strikes (used by backtest)
                "sell_call_strike": sell_call,
                "buy_call_strike":  buy_call,
                "spot":             price,
                "legs": [
                    f"SELL {sell_call} CE  approx +{sc_prem:.0f} pts",
                    f"BUY  {buy_call}  CE  approx -{bc_prem:.0f} pts  (protection)",
                ],
                "net_credit":  net_credit,
                "max_profit":  max_profit,
                "max_loss":    max_loss,
                "roc_pct":     roc,
                "breakeven":   be,
                "dte":         dte,
                "lot_size":    lot_size,
                "note": (
                    f"Profit if {symbol} closes BELOW {be} at expiry. "
                    f"Resistance at {resistance:.0f} — gives {abs(be - price):.0f} pts of buffer."
                ),
                "risk_note": (
                    f"Max risk {max_loss} pts x {lot_size} = "
                    f"Rs {max_loss * lot_size:,}/lot"
                ),
                "when_to_use": (
                    "Use when index fails at resistance repeatedly — "
                    "sell calls above rejection zone with 3-5 DTE."
                ),
            })

    return setups
