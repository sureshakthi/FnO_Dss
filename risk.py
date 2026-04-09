from config import RISK_CONFIG, COST_CONFIG, LOT_SIZE


def _calc_brokerage(premium: float, lots: int, symbol: str) -> float:
    """Estimate total transaction cost for 1 option trade (buy + sell)."""
    lot_size   = LOT_SIZE.get(symbol, 50)
    qty        = lots * lot_size
    brkg       = COST_CONFIG['brokerage_per_lot'] * lots * 2   # buy + sell
    stt        = premium * qty * COST_CONFIG['stt_pct']         # sell side only
    exch       = premium * qty * COST_CONFIG['exchange_charges']
    gst        = (brkg + exch) * COST_CONFIG['gst_pct']
    return round(brkg + stt + exch + gst, 2)


def calculate_position(signal: dict, capital: float = None,
                       symbol: str = "NIFTY") -> dict:
    """
    Compute trade setup from signal:
      - ATR-based SL (1.5x ATR from entry)
      - R:R = 2:1 target
      - ATM option strike + estimated premium
      - Brokerage cost
    """
    if capital is None:
        capital = RISK_CONFIG['capital']

    direction = signal.get('direction', 'NEUTRAL')
    if direction == 'NEUTRAL':
        return {"direction": "NEUTRAL", "action": "WAIT",
                "reason": "No clear signal — stay out"}

    price = signal.get('current_price', 0)
    atr   = signal.get('atr', price * 0.01)
    if price == 0:
        return {"direction": "NEUTRAL", "action": "WAIT",
                "reason": "Price unavailable"}

    # SL = ATR * 1.5  (much wider than old 0.3% fixed)
    sl_distance     = round(atr * RISK_CONFIG['atr_sl_multiplier'], 2)
    target_distance = round(sl_distance * RISK_CONFIG['target_rr'], 2)
    risk_amount     = round(capital * RISK_CONFIG['risk_per_trade_pct'], 2)

    # ATM strikes
    atm_50  = round(price / 50)  * 50
    atm_100 = round(price / 100) * 100

    if direction == "BUY":
        entry       = round(price, 2)
        sl          = round(entry - sl_distance, 2)
        target      = round(entry + target_distance, 2)
        option_type = "CE"
    else:  # SELL signal → buy PE
        entry       = round(price, 2)
        sl          = round(entry + sl_distance, 2)
        target      = round(entry - target_distance, 2)
        option_type = "PE"

    # Estimate ATM premium (weekly ~1.2% of spot, more volatile = more premium)
    est_premium = round(price * 0.012, 0)
    brkg        = _calc_brokerage(est_premium, 1, symbol)

    return {
        "direction":       direction,
        "action":          f"BUY ATM {atm_50} {option_type}",
        "entry_index":     entry,
        "sl_index":        sl,
        "target_index":    target,
        "sl_distance":     sl_distance,
        "target_distance": target_distance,
        "rr_ratio":        RISK_CONFIG['target_rr'],
        "risk_amount_inr": risk_amount,
        "option_type":     option_type,
        "atm_strike_50":   atm_50,
        "atm_strike_100":  atm_100,
        "est_premium":     est_premium,
        "brokerage_cost":  brkg,
        "lots":            1,
        "lot_size":        LOT_SIZE.get(symbol, 50),
        "max_loss_pts":    sl_distance,
        "max_profit_pts":  target_distance,
    }
    """
    Given a signal dict, compute:
        - Entry, SL, Target index levels
        - ATM options action (CE/PE)
        - Risk/reward summary
    Returns a position dict, or NEUTRAL if no trade.
    """
    if capital is None:
        capital = RISK_CONFIG['capital']

    direction = signal.get('direction', 'NEUTRAL')
    if direction == 'NEUTRAL':
        return {"direction": "NEUTRAL", "action": "WAIT",
                "reason": "No clear signal — stay out"}

    price = signal.get('current_price', 0)
    atr = signal.get('atr', price * 0.01)
    if price == 0:
        return {"direction": "NEUTRAL", "action": "WAIT", "reason": "Price unavailable"}

    # SL: use ATR-based or fixed %, whichever is larger
    sl_by_pct = price * RISK_CONFIG['sl_pct']
    sl_by_atr = atr * 0.5
    sl_distance = round(max(sl_by_pct, sl_by_atr), 2)

    # Target based on R:R ratio
    target_distance = round(sl_distance * RISK_CONFIG['target_rr'], 2)

    # Capital risk
    risk_amount = round(capital * RISK_CONFIG['risk_per_trade_pct'], 2)

    # ATM strike (nearest 50 for Nifty, nearest 100 for BankNifty)
    atm_50 = round(price / 50) * 50
    atm_100 = round(price / 100) * 100

    if direction == "BUY":
        entry = round(price, 2)
        sl = round(entry - sl_distance, 2)
        target = round(entry + target_distance, 2)
        option_type = "CE"
    else:  # SELL
        entry = round(price, 2)
        sl = round(entry + sl_distance, 2)
        target = round(entry - target_distance, 2)
        option_type = "PE"

    # Approximate ATM option premium (~1–1.5% of spot for weekly expiry)
    est_premium = round(price * 0.012, 0)

    return {
        "direction": direction,
        "action": f"BUY ATM {atm_50} {option_type}",
        "entry_index": entry,
        "sl_index": sl,
        "target_index": target,
        "sl_distance": sl_distance,
        "target_distance": target_distance,
        "rr_ratio": RISK_CONFIG['target_rr'],
        "risk_amount_inr": risk_amount,
        "option_type": option_type,
        "atm_strike_50": atm_50,
        "atm_strike_100": atm_100,
        "est_premium": est_premium,
        "lots": 1,
        "max_loss_pts": sl_distance,
        "max_profit_pts": target_distance,
    }
