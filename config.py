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
    "breakout_days":      10,
    "rsi_period":         14,
    "rsi_buy_min":        45,
    "rsi_buy_max":        68,
    "rsi_sell_min":       32,
    "rsi_sell_max":       55,
    "adx_trending":       20,
    "volume_multiplier":  1.3,
    "supertrend_period":  10,
    "supertrend_mult":    2.0,
    "weekly_ma_period":   10,
    "min_signal_points":  4,
}

RISK_CONFIG = {
    "capital":              100000,
    "risk_per_trade_pct":   0.01,
    "target_rr":            2.0,
    "atr_sl_multiplier":    1.5,
    "max_trades_per_day":   1,
    "max_daily_loss_pct":   0.02,
    "kill_switch_losses":   3,
}

COST_CONFIG = {
    "brokerage_per_lot":  40,
    "stt_pct":            0.0005,
    "exchange_charges":   0.0005,
    "gst_pct":            0.18,
}

PROXY = "http://proxy.cat.com"
