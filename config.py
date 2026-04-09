# ============================================================
# F&O Decision Support System V2 — Configuration
# ============================================================

SYMBOLS = {
    "NIFTY":     "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}

# Lot sizes (NSE standard)
LOT_SIZE = {
    "NIFTY":     75,
    "BANKNIFTY": 35,
}

MARKET_HOURS = {
    "open":     "09:15",
    "close":    "15:30",
    "timezone": "Asia/Kolkata",
}

STRATEGY_CONFIG = {
    # ── Indicators ──────────────────────────────
    "breakout_days":      10,    # Donchian channel period for breakout
    "rsi_period":         14,
    "rsi_buy_min":        45,    # RSI must be above this for BUY
    "rsi_buy_max":        68,    # RSI must be below this for BUY (not overbought)
    "rsi_sell_min":       32,    # RSI must be below rsi_sell_max for SELL
    "rsi_sell_max":       55,    # RSI must be below this for SELL (not oversold)
    "adx_trending":       20,    # ADX above this = trending market
    "adx_exhausted":      50,    # ADX above this = trend exhausted, skip trade
    "volume_multiplier":  1.3,   # Min volume ratio to confirm move
    "supertrend_period":  10,
    "supertrend_mult":    2.0,

    # ── Weekly trend filter ──────────────────────
    "weekly_ma_period":   10,    # Weekly MA to determine big trend

    # ── Signal strength ──────────────────────────
    "min_signal_points":  5,     # Need at least 5 out of 7 points (raised — Score 4 had 80% loss rate)
}

RISK_CONFIG = {
    "capital":              100000,   # paper capital ₹1,00,000
    "risk_per_trade_pct":   0.01,     # 1% risk per trade = ₹1,000
    "target_rr":            2.0,      # Reward:Risk = 2:1 (improved from 1.5)
    "atr_sl_multiplier":    1.5,      # SL = entry ± ATR * 1.5
    "max_trades_per_day":   1,        # max 1 trade per day (quality > quantity)
    "max_daily_loss_pct":   0.02,     # 2% max daily loss = kill switch
    "kill_switch_losses":   3,        # Stop after 3 consecutive losses
}

# Transaction costs (India F&O)
COST_CONFIG = {
    "brokerage_per_lot":  40,    # Rs 20 buy + Rs 20 sell
    "stt_pct":            0.0005,# STT on sell side (index options)
    "exchange_charges":   0.0005,# ~0.05% NSE charges + SEBI
    "gst_pct":            0.18,  # 18% GST on brokerage + exchange
}

# Corporate proxy — used automatically when on office/VPN network.
# On cloud or home WiFi the system skips this and connects directly.
PROXY = "http://proxy.cat.com"
