"""
F&O DSS — Telegram Notifier
Sends daily F&O signal summaries to your Telegram.

SETUP (one-time, 2 minutes):
  1. Open Telegram → search @BotFather → send /newbot → follow prompts → copy the TOKEN
  2. Run:  python telegram_notifier.py --setup
  3. Follow the prompts — config is saved to telegram_config.json (keep private)

USAGE after setup:
  Automatic — signals are sent at the end of each  python main.py  run.
  Manual test:  python telegram_notifier.py --test
"""

import os
import sys
import json
import requests
from pathlib import Path

# ── Config paths ──────────────────────────────────────────────────────────────
_BASE      = Path(__file__).parent
CONFIG_FILE = _BASE / "telegram_config.json"

# ── Corporate proxy — only used when on office/VPN network ───────────────────
def _detect_proxies() -> dict:
    try:
        from config import PROXY as _PROXY_URL
        import requests as _r
        _r.get("https://finance.yahoo.com",
               proxies={"http": _PROXY_URL, "https": _PROXY_URL},
               timeout=3, verify=False)
        return {"http": _PROXY_URL, "https": _PROXY_URL}
    except Exception:
        return {}

_PROXIES = _detect_proxies()


# ─── Credential Helpers ───────────────────────────────────────────────────────

def _load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    print(f"  Config saved → {CONFIG_FILE}")


def _get_credentials() -> tuple[str, str]:
    """Return (bot_token, chat_id) — env vars take priority over config file."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        cfg     = _load_config()
        token   = token   or cfg.get("bot_token",  "")
        chat_id = chat_id or cfg.get("chat_id",    "")
    return token, chat_id


def is_configured() -> bool:
    token, chat_id = _get_credentials()
    return bool(token and chat_id)


# ─── Core Send ────────────────────────────────────────────────────────────────

def send_message(text: str) -> bool:
    """
    Send an HTML-formatted text message to the configured Telegram chat.
    Returns True on success, False on failure (never raises).
    """
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=15,
            proxies=_PROXIES,
        )
        return resp.ok
    except Exception:
        return False


# ─── Signal Formatter ─────────────────────────────────────────────────────────

def send_signal_summary(data: dict) -> bool:
    """
    Formats the signals dict (from _build_signals() in web_app.py or
    collect_signals() appended to main.py) and sends to Telegram.
    """
    if not is_configured():
        return False

    lines = [
        "🇮🇳 <b>F&amp;O DSS — Signal Update</b>",
        f"📅 {data.get('timestamp', '')}",
    ]

    vix = data.get("vix", {})
    v   = vix.get("value", 0)
    chg = vix.get("change_pct", 0)
    lvl = vix.get("level", "")
    arr = "▲" if chg >= 0 else "▼"
    vix_color_tag = "🔴" if v >= 30 else "🟡" if v >= 20 else "🟢"
    lines.append(f"\n🌡️ India VIX: <b>{v:.1f}</b>  {arr} {chg:+.2f}%  {vix_color_tag} {lvl}")

    for sym, sd in data.get("symbols", {}).items():
        lines.append(f"\n{'━'*6} {sym} {'━'*6}")

        if "error" in sd:
            lines.append(f"⚠️ Data unavailable")
            continue

        price = sd.get("price", 0)
        chg_p = sd.get("change", 0)
        pct   = sd.get("change_pct", 0)
        arrow = "▲" if chg_p >= 0 else "▼"
        sign  = "+" if chg_p >= 0 else ""
        lines.append(f"💰 <b>{price:,.0f}</b>  {arrow} {sign}{chg_p:.0f} ({sign}{pct:.1f}%)")

        regime = sd.get("regime", "")
        r_icon = {"TRENDING": "📈", "SIDEWAYS": "📊", "VOLATILE": "⚡"}.get(regime, "?")
        lines.append(f"{r_icon} Regime: <b>{regime}</b>")

        ind = sd.get("indicators", {})
        lines.append(
            f"📉 ADX: {ind.get('adx', 0):.1f}  "
            f"RSI: {ind.get('rsi', 0):.1f}  "
            f"DTE: {ind.get('dte', 0)} days"
        )

        direction = sd.get("direction", "NEUTRAL")
        strength  = sd.get("strength", 0)
        stars     = "⭐" * strength if strength else ""
        d_icon    = {"BUY": "🟢", "SELL": "🔴", "NEUTRAL": "⚪"}.get(direction, "⚪")
        lines.append(f"\n{d_icon} Signal: <b>{direction}</b> {stars}")

        if regime == "TRENDING":
            ts = sd.get("trade_setup")
            if ts:
                lines.append(f"🎯 Entry: {int(ts.get('entry', 0)):,}")
                lines.append(
                    f"✅ Target: {int(ts.get('target', 0)):,}  |  "
                    f"❌ SL: {int(ts.get('sl', 0)):,}"
                )
                lines.append(f"📐 R:R {ts.get('rr', 0)}:1  |  Est. ₹{ts.get('est_premium', 0):.0f} premium")

        elif regime == "SIDEWAYS":
            ss = sd.get("sweet_spot", {})
            if ss:
                score  = ss.get("score", 0)
                mx     = ss.get("max_score", 5)
                sweet  = ss.get("is_sweet", False)
                badge  = "🟢 ENTER THETA TRADE" if sweet else "🔴 SKIP TODAY"
                lines.append(f"\n{badge}  ({score}/{mx})")

                if sweet:
                    for setup in sd.get("theta_setups", [])[:1]:
                        lines.append(f"📋 {setup.get('strategy', '')}")
                        lines.append(f"   Net Credit: +{setup.get('net_credit', 0)} pts")
                        if setup.get("profit_zone"):
                            lines.append(f"   Profit Zone: {setup['profit_zone']}")
                        lines.append(f"   Max Loss: –{setup.get('max_loss', 0)} pts")

        elif regime == "VOLATILE":
            lines.append("⚡ STAND ASIDE — Preserve capital today")

        # 0-DTE IC (Thursdays)
        z = sd.get("zero_dte")
        if z:
            if z.get("status") == "ACTIVE":
                lines.append(f"\n🕐 <b>0-DTE IC (Thursday)</b>  — 100% WR backtest")
                lines.append(f"   SELL {z['sell_call']} CE / BUY {z['buy_call']} CE")
                lines.append(f"   SELL {z['sell_put']} PE / BUY {z['buy_put']} PE")
                lines.append(f"   Net Credit: +{z['net_credit']:.0f} pts")
                lines.append(f"   Profit Zone: {z['profit_zone']}")
                lines.append(f"   ₹{z['profit_inr']:,.0f} max profit / lot")
            else:
                lines.append(
                    f"\n⚠️ 0-DTE IC SKIPPED  (ADX {z.get('adx', 0):.1f} > 35 — too trending)"
                )

    lines.append("\n<i>Paper Trading Only — Not Financial Advice</i>")
    return send_message("\n".join(lines))


# ─── Setup Wizard ─────────────────────────────────────────────────────────────

def setup():
    print("\n📱  Telegram Bot Setup for F&O DSS\n")
    print("Step 1 — Create your bot")
    print("  Open Telegram → search @BotFather → send /newbot → follow prompts")
    print("  Copy the TOKEN that BotFather gives you.\n")

    token = input("Paste your Bot Token here: ").strip()
    if not token:
        print("❌  No token entered.  Aborting.")
        return

    print("\nStep 2 — Get your Chat ID")
    print("  Send any message to your new bot in Telegram first,")
    print("  then press Enter below and we will auto-detect your Chat ID.\n")
    input("Press Enter after you have sent a message to your bot... ")

    chat_id = ""
    try:
        url  = f"https://api.telegram.org/bot{token}/getUpdates"
        resp = requests.get(url, timeout=15, proxies=_PROXIES)
        updates = resp.json().get("result", [])
        if updates:
            chat_id    = str(updates[-1]["message"]["chat"]["id"])
            first_name = updates[-1]["message"]["chat"].get("first_name", "User")
            print(f"✅  Chat ID detected: {chat_id}  (Name: {first_name})")
        else:
            print("⚠️  No messages found in bot. Make sure you sent a message to your bot first.")
    except Exception as e:
        print(f"⚠️  Auto-detect failed: {e}")

    if not chat_id:
        chat_id = input("Enter Chat ID manually (or press Enter to abort): ").strip()
    if not chat_id:
        print("❌  No Chat ID.  Aborting.")
        return

    _save_config({"bot_token": token, "chat_id": chat_id})

    print("\n  Sending test message…")
    if send_message(
        "🇮🇳 <b>F&amp;O DSS Bot Connected!</b>\n\n"
        "You'll receive daily F&amp;O signals here.\n"
        "Run <code>python main.py</code> to generate today's signal."
    ):
        print("✅  Test message sent!  Check your Telegram.")
    else:
        print("❌  Failed to send.  Double-check your token and that you messaged the bot.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup()
    elif "--test" in sys.argv:
        if not is_configured():
            print("❌  Not configured yet.  Run:  python telegram_notifier.py --setup")
        else:
            ok = send_message(
                "🇮🇳 <b>F&amp;O DSS — Test Message</b>\n\n"
                "✅ Bot is working correctly.\n"
                "Run <code>python main.py</code> to get today's live signals."
            )
            print("✅  Message sent!" if ok else "❌  Failed to send. Check config.")
    else:
        print("Usage:")
        print("  python telegram_notifier.py --setup   (first-time setup)")
        print("  python telegram_notifier.py --test    (send a test message)")
