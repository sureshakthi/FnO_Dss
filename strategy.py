import pandas as pd
import numpy as np
from datetime import datetime

from config import STRATEGY_CONFIG


# ══════════════════════════════════════════════════════════════════════════════
#  TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════════════════════════════

def _rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    delta = prices.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - df['Close'].shift()).abs(),
        (df['Low']  - df['Close'].shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index — measures trend STRENGTH (not direction)."""
    high, low, close = df['High'], df['Low'], df['Close']
    plus_dm  = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Zero out where other DM is larger
    plus_dm  = plus_dm.where(plus_dm  > minus_dm, 0)
    minus_dm = minus_dm.where(minus_dm > plus_dm,  0)

    tr = _atr(df, period)
    plus_di  = 100 * plus_dm.rolling(period).mean()  / tr.replace(0, np.nan)
    minus_di = 100 * minus_dm.rolling(period).mean() / tr.replace(0, np.nan)
    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.rolling(period).mean()


def _supertrend(df: pd.DataFrame, period: int = 10, mult: float = 3.0) -> pd.Series:
    """
    Supertrend indicator — direction-conditional ratchet (Pine Script equivalent).
    Returns +1 (price above ST = bullish) or -1 (price below ST = bearish).
    """
    atr     = _atr(df, period).values
    hl2     = ((df['High'] + df['Low']) / 2).values
    close   = df['Close'].values
    n       = len(close)

    upper_raw = hl2 + mult * atr
    lower_raw = hl2 - mult * atr
    upper     = upper_raw.copy()
    lower     = lower_raw.copy()
    direction = np.full(n, np.nan)

    for i in range(1, n):
        if np.isnan(atr[i]):
            continue

        prev_dir = direction[i - 1] if not np.isnan(direction[i - 1]) else 1.0

        if prev_dir >= 0:                      # was bullish → ratchet lower band UP
            lower[i] = max(lower_raw[i], lower[i - 1] if not np.isnan(lower[i - 1]) else lower_raw[i])
            upper[i] = upper_raw[i]
            direction[i] = -1.0 if close[i] < lower[i] else 1.0
        else:                                  # was bearish → ratchet upper band DOWN
            upper[i] = min(upper_raw[i], upper[i - 1] if not np.isnan(upper[i - 1]) else upper_raw[i])
            lower[i] = lower_raw[i]
            direction[i] = 1.0 if close[i] > upper[i] else -1.0

    return pd.Series(direction, index=df.index)


def _stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3):
    """Stochastic %K and %D."""
    low_min  = df['Low'].rolling(k_period).min()
    high_max = df['High'].rolling(k_period).max()
    k = 100 * (df['Close'] - low_min) / (high_max - low_min).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    return k, d


def _weekly_trend(df: pd.DataFrame) -> str:
    """
    Resample daily data to weekly and check if weekly MA slope is up or down.
    Returns 'BULLISH', 'BEARISH', or 'NEUTRAL'.
    """
    weekly = df['Close'].resample('W').last().dropna()
    ma_period = STRATEGY_CONFIG['weekly_ma_period']
    if len(weekly) < ma_period + 2:
        return 'NEUTRAL'
    wma = weekly.rolling(ma_period).mean()
    last_wma  = float(wma.iloc[-1])
    prev_wma  = float(wma.iloc[-2])
    last_price = float(weekly.iloc[-1])
    if last_price > last_wma and last_wma > prev_wma:
        return 'BULLISH'
    elif last_price < last_wma and last_wma < prev_wma:
        return 'BEARISH'
    return 'NEUTRAL'


def _days_to_expiry() -> int:
    """
    Approximate days to next weekly Nifty/BankNifty expiry (every Thursday).
    """
    today = datetime.now()
    days_ahead = (3 - today.weekday()) % 7   # 3 = Thursday
    if days_ahead == 0:
        days_ahead = 7
    return days_ahead


# ══════════════════════════════════════════════════════════════════════════════
#  INDICATOR CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cfg = STRATEGY_CONFIG

    # Trend MAs
    df['MA20']  = df['Close'].rolling(20).mean()
    df['MA50']  = df['Close'].rolling(50).mean()
    df['EMA9']  = df['Close'].ewm(span=9).mean()
    df['EMA21'] = df['Close'].ewm(span=21).mean()

    # Momentum
    df['RSI']   = _rsi(df['Close'], cfg['rsi_period'])
    df['ATR']   = _atr(df)
    df['ADX']   = _adx(df)

    # Supertrend
    df['Supertrend_Dir'] = _supertrend(
        df, cfg['supertrend_period'], cfg['supertrend_mult'])

    # Stochastic
    df['Stoch_K'], df['Stoch_D'] = _stochastic(df)

    # Volume
    df['Vol_MA20']  = df['Volume'].rolling(20).mean()
    df['Vol_Ratio'] = df['Volume'] / df['Vol_MA20'].replace(0, np.nan)

    # Donchian Channel (breakout levels)
    n = cfg['breakout_days']
    df['Resistance'] = df['High'].rolling(n).max().shift(1)
    df['Support']    = df['Low'].rolling(n).min().shift(1)

    # MACD
    ema12 = df['Close'].ewm(span=12).mean()
    ema26 = df['Close'].ewm(span=26).mean()
    df['MACD']        = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    df['MACD_Hist']   = df['MACD'] - df['MACD_Signal']

    # Bollinger Bands (market regime)
    bb_mid = df['Close'].rolling(20).mean()
    bb_std = df['Close'].rolling(20).std()
    df['BB_Upper'] = bb_mid + 2 * bb_std
    df['BB_Lower'] = bb_mid - 2 * bb_std
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / bb_mid

    return df


# ══════════════════════════════════════════════════════════════════════════════
#  MARKET REGIME
# ══════════════════════════════════════════════════════════════════════════════

def get_market_regime(df_with_indicators: pd.DataFrame) -> str:
    """
    TRENDING  — ADX > 20 + clear MA alignment
    SIDEWAYS  — ADX low + price chopping inside BB
    VOLATILE  — BB width spike (sudden expansion)
    """
    latest = df_with_indicators.iloc[-1]
    adx = float(latest['ADX']) if not pd.isna(latest.get('ADX', np.nan)) else 0
    bb_width = float(latest['BB_Width']) if not pd.isna(latest.get('BB_Width', np.nan)) else 0

    # Historical avg BB width
    avg_bbw = float(df_with_indicators['BB_Width'].rolling(20).mean().iloc[-1]) \
              if 'BB_Width' in df_with_indicators else bb_width

    if bb_width > avg_bbw * 1.5:
        return 'VOLATILE'
    elif adx >= STRATEGY_CONFIG['adx_trending']:
        return 'TRENDING'
    else:
        return 'SIDEWAYS'


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL GENERATION  (the core brain)
# ══════════════════════════════════════════════════════════════════════════════

def generate_signal(df: pd.DataFrame) -> dict:
    """
    6-factor signal engine:
      1. Donchian breakout / breakdown  (2 pts — primary trigger)
      2. Weekly trend alignment         (1 pt — filter)
      3. Supertrend direction           (1 pt)
      4. Directional RSI                (1 pt)
      5. ADX regime filter              (removes trade in sideways)
      6. Volume confirmation            (1 pt)

    Minimum 3 points needed to fire a signal.
    """
    MIN_ROWS = 55
    if df.empty or len(df) < MIN_ROWS:
        return _neutral(["⚠ Insufficient data"])

    df = calculate_indicators(df)
    latest  = df.iloc[-1]
    prev    = df.iloc[-2]
    regime  = get_market_regime(df)
    weekly  = _weekly_trend(df)
    dte     = _days_to_expiry()

    # ── SIDEWAYS: don't run directional scoring — regime-based switch in main.py
    # We still return a full dict (with indicators) so the theta module has all data.
    adx = float(latest['ADX']) if not pd.isna(latest['ADX']) else 0
    if adx < STRATEGY_CONFIG['adx_trending'] and regime == 'SIDEWAYS':
        return _neutral([
            f"⚪ Market SIDEWAYS (ADX={adx:.1f}) — use Theta strategy, not directional",
        ], regime='SIDEWAYS', weekly=weekly, dte=dte, df=df)

    bullish = 0
    bearish = 0
    reasons = []

    close      = float(latest['Close'])
    resistance = float(latest['Resistance'])
    support    = float(latest['Support'])
    ma20       = float(latest['MA20'])
    ma50       = float(latest['MA50'])
    rsi        = float(latest['RSI'])
    st_dir     = int(latest['Supertrend_Dir']) if not pd.isna(latest['Supertrend_Dir']) else 0
    vol_ratio  = float(latest['Vol_Ratio'])    if not pd.isna(latest['Vol_Ratio'])    else 1.0
    macd_hist  = float(latest['MACD_Hist'])    if not pd.isna(latest['MACD_Hist'])    else 0
    prev_macd  = float(prev['MACD_Hist'])      if not pd.isna(prev['MACD_Hist'])      else 0
    stoch_k    = float(latest['Stoch_K'])      if not pd.isna(latest['Stoch_K'])      else 50
    atr        = float(latest['ATR'])          if not pd.isna(latest['ATR'])          else close * 0.01

    # ── 1. Donchian Breakout (PRIMARY — 2 points) ────────────────────────────
    if not pd.isna(resistance) and close > resistance:
        bullish += 2
        reasons.append(f"✅ [2pts] Donchian Breakout above {resistance:.0f} (10-day high)")
    elif not pd.isna(support) and close < support:
        bearish += 2
        reasons.append(f"✅ [2pts] Donchian Breakdown below {support:.0f} (10-day low)")
    else:
        reasons.append(f"⚪ [0pts] Inside range [{support:.0f} – {resistance:.0f}]")

    # ── 2. Weekly Trend Alignment (1 point) ──────────────────────────────────
    if weekly == 'BULLISH':
        bullish += 1
        reasons.append(f"✅ [1pt]  Weekly trend BULLISH — aligned for BUY")
    elif weekly == 'BEARISH':
        bearish += 1
        reasons.append(f"🔴 [1pt]  Weekly trend BEARISH — aligned for SELL")
    else:
        reasons.append(f"⚪ [0pts] Weekly trend NEUTRAL — no alignment bonus")

    # ── 3. Supertrend Direction (1 point) ────────────────────────────────────
    if st_dir == 1:
        bullish += 1
        reasons.append(f"✅ [1pt]  Supertrend BULLISH — price above supertrend line")
    elif st_dir == -1:
        bearish += 1
        reasons.append(f"🔴 [1pt]  Supertrend BEARISH — price below supertrend line")
    else:
        reasons.append(f"⚪ [0pts] Supertrend not calculated")

    # ── 4. Directional RSI (1 point) ─────────────────────────────────────────
    rsi_buy_ok  = STRATEGY_CONFIG['rsi_buy_min']  <= rsi <= STRATEGY_CONFIG['rsi_buy_max']
    rsi_sell_ok = STRATEGY_CONFIG['rsi_sell_min'] <= rsi <= STRATEGY_CONFIG['rsi_sell_max']
    if rsi_buy_ok:
        bullish += 1
        reasons.append(f"✅ [1pt]  RSI {rsi:.1f} — in BUY zone ({STRATEGY_CONFIG['rsi_buy_min']}–{STRATEGY_CONFIG['rsi_buy_max']})")
    elif rsi_sell_ok:
        bearish += 1
        reasons.append(f"🔴 [1pt]  RSI {rsi:.1f} — in SELL zone ({STRATEGY_CONFIG['rsi_sell_min']}–{STRATEGY_CONFIG['rsi_sell_max']})")
    elif rsi > 70:
        bearish += 1
        reasons.append(f"⚠ [1pt]  RSI {rsi:.1f} — Overbought, risk of reversal")
    elif rsi < 30:
        bullish += 1
        reasons.append(f"⚠ [1pt]  RSI {rsi:.1f} — Oversold, watch for bounce")
    else:
        reasons.append(f"⚪ [0pts] RSI {rsi:.1f} — neutral zone")

    # ── 5. Volume Confirmation (1 point) ─────────────────────────────────────
    if vol_ratio >= STRATEGY_CONFIG['volume_multiplier']:
        if close > float(prev['Close']):
            bullish += 1
            reasons.append(f"✅ [1pt]  Volume {vol_ratio:.1f}x avg — confirms up move")
        else:
            bearish += 1
            reasons.append(f"🔴 [1pt]  Volume {vol_ratio:.1f}x avg — confirms down move")
    else:
        reasons.append(f"⚪ [0pts] Volume {vol_ratio:.1f}x avg — no confirmation")

    # ── 6. MACD Momentum (1 point) ───────────────────────────────────────────
    if macd_hist > 0 and prev_macd <= 0:
        bullish += 1
        reasons.append(f"✅ [1pt]  MACD histogram crossed positive — fresh bullish momentum")
    elif macd_hist < 0 and prev_macd >= 0:
        bearish += 1
        reasons.append(f"🔴 [1pt]  MACD histogram crossed negative — fresh bearish momentum")
    elif macd_hist > 0:
        bullish += 1
        reasons.append(f"✅ [1pt]  MACD histogram positive — sustained bullish momentum")
    elif macd_hist < 0:
        bearish += 1
        reasons.append(f"🔴 [1pt]  MACD histogram negative — sustained bearish momentum")
    else:
        reasons.append(f"⚪ [0pts] MACD histogram flat — no momentum signal")

    # ── 7. Stochastic Extremes (1 point) ─────────────────────────────────────
    prev_stoch = float(prev['Stoch_K']) if not pd.isna(prev.get('Stoch_K', np.nan)) else 50
    if stoch_k < 25 and stoch_k > prev_stoch:
        bullish += 1
        reasons.append(f"✅ [1pt]  Stochastic {stoch_k:.1f} — oversold + turning up (bounce signal)")
    elif stoch_k > 75 and stoch_k < prev_stoch:
        bearish += 1
        reasons.append(f"🔴 [1pt]  Stochastic {stoch_k:.1f} — overbought + turning down (reversal risk)")
    else:
        reasons.append(f"⚪ [0pts] Stochastic {stoch_k:.1f} — not at actionable extreme")

    # ── Decision ─────────────────────────────────────────────────────────────
    min_pts = STRATEGY_CONFIG['min_signal_points']

    if bullish >= min_pts and bullish > bearish:
        direction = "BUY"
        strength  = min(bullish, 6)
    elif bearish >= min_pts and bearish > bullish:
        direction = "SELL"
        strength  = min(bearish, 6)
    else:
        direction = "NEUTRAL"
        strength  = 0
        reasons.append(f"⚪ Only {max(bullish, bearish)} points (need {min_pts}) — no trade")

    # ── Hard Quality Gates (applied after scoring) ────────────────────────────
    # Supertrend direction MUST match the signal — this is the only hard veto.
    # RSI and weekly trend are scoring factors, not blockers (oversold can
    # stay oversold for weeks in a real bear market).
    if direction == "BUY" and st_dir == -1:
        reasons.append("❌ BUY cancelled: Supertrend is BEARISH — no longs in downtrend")
        direction, strength = "NEUTRAL", 0
    elif direction == "SELL" and st_dir == 1:
        reasons.append("❌ SELL cancelled: Supertrend is BULLISH — no shorts in uptrend")
        direction, strength = "NEUTRAL", 0

    # ADX exhaustion filter — trend too stretched, likely to reverse
    adx_cap = STRATEGY_CONFIG.get('adx_exhausted', 50)
    if direction != "NEUTRAL" and adx > adx_cap:
        reasons.append(f"❌ {direction} cancelled: ADX {adx:.0f} > {adx_cap} — trend exhausted, reversal likely")
        direction, strength = "NEUTRAL", 0

    # Weekly trend counter-trade filter — SELL in bullish weekly = 0% win rate
    if direction == "SELL" and weekly == "BULLISH":
        reasons.append("❌ SELL cancelled: Weekly trend is BULLISH — counter-trend sells lose 100%")
        direction, strength = "NEUTRAL", 0

    # Panic volume filter — extreme volume spikes = 0% win rate
    if direction != "NEUTRAL" and vol_ratio > 2.0:
        reasons.append(f"❌ {direction} cancelled: Volume {vol_ratio:.1f}x — panic spike, unreliable signal")
        direction, strength = "NEUTRAL", 0

    return {
        "direction":     direction,
        "strength":      strength,
        "bullish_pts":   bullish,
        "bearish_pts":   bearish,
        "reasons":       reasons,
        "current_price": close,
        "resistance":    resistance,
        "support":       support,
        "rsi":           rsi,
        "atr":           atr,
        "adx":           adx,
        "regime":        regime,
        "weekly_trend":  weekly,
        "supertrend_dir": st_dir,
        "vol_ratio":     vol_ratio,
        "dte":           dte,
        "ma20":          ma20,
        "ma50":          ma50,
        "stoch_k":       stoch_k,
    }


def _neutral(reasons: list, regime: str = "SIDEWAYS",
             weekly: str = "NEUTRAL", dte: int = 0,
             df: pd.DataFrame = None) -> dict:
    price = 0.0
    atr   = 0.0
    adx   = 0.0
    ma20  = 0.0
    ma50  = 0.0
    resistance = 0.0
    support    = 0.0
    rsi_val    = 0.0
    stoch_val  = 50.0
    vol_ratio  = 0.0
    st_dir     = 0
    if df is not None and not df.empty:
        l = df.iloc[-1]
        price      = float(l.get('Close', 0))
        atr        = float(l['ATR'])        if not pd.isna(l.get('ATR',        np.nan)) else 0.0
        adx        = float(l['ADX'])        if not pd.isna(l.get('ADX',        np.nan)) else 0.0
        ma20       = float(l['MA20'])       if not pd.isna(l.get('MA20',       np.nan)) else 0.0
        ma50       = float(l['MA50'])       if not pd.isna(l.get('MA50',       np.nan)) else 0.0
        resistance = float(l['Resistance']) if not pd.isna(l.get('Resistance', np.nan)) else 0.0
        support    = float(l['Support'])    if not pd.isna(l.get('Support',    np.nan)) else 0.0
        rsi_val    = float(l['RSI'])        if not pd.isna(l.get('RSI',        np.nan)) else 0.0
        stoch_val  = float(l['Stoch_K'])    if not pd.isna(l.get('Stoch_K',    np.nan)) else 50.0
        vol_ratio  = float(l['Vol_Ratio'])  if not pd.isna(l.get('Vol_Ratio',  np.nan)) else 0.0
        st_dir_raw = l.get('Supertrend_Dir', np.nan)
        st_dir     = int(st_dir_raw) if not pd.isna(st_dir_raw) else 0
    return {
        "direction": "NEUTRAL", "strength": 0,
        "bullish_pts": 0, "bearish_pts": 0,
        "reasons": reasons,
        "current_price": price,
        "resistance": resistance, "support": support,
        "rsi": rsi_val, "atr": atr, "adx": adx,
        "regime": regime, "weekly_trend": weekly,
        "supertrend_dir": st_dir, "vol_ratio": vol_ratio,
        "dte": dte, "ma20": ma20, "ma50": ma50,
        "stoch_k": stoch_val,
    }

