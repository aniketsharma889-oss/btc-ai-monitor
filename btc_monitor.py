import os
import requests
from datetime import datetime, timezone


# =========================
# CONFIG
# =========================

BASE_URL = "https://api.sharkexchange.in"
PAIR = "BTCUSDT"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


# =========================
# API HELPER
# =========================

def get_json(url, method="GET", payload=None):
    if method == "POST":
        response = requests.post(
            url,
            json=payload,
            timeout=20
        )
    else:
        response = requests.get(
            url,
            timeout=20
        )

    response.raise_for_status()
    return response.json()


# =========================
# MARKET DATA
# =========================

def get_ticker():
    data = get_json(
        f"{BASE_URL}/v1/market/ticker24Hr/{PAIR}"
    )

    if isinstance(data, dict):
        return data.get("data", data)

    return {}


def get_depth():
    data = get_json(
        f"{BASE_URL}/v1/market/depth/{PAIR}"
    )

    if isinstance(data, dict):
        return data.get("data", data)

    return {}


def get_trades():
    data = get_json(
        f"{BASE_URL}/v1/market/aggTrade/{PAIR}"
    )

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        return data.get("data", [])

    return []


def get_klines(interval, limit=20):

    payload = {
        "pair": PAIR,
        "interval": interval,
        "limit": limit
    }

    data = get_json(
        f"{BASE_URL}/v1/market/klines?priceType=MARK_PRICE",
        method="POST",
        payload=payload
    )

    # Shark API may return a raw list
    if isinstance(data, list):
        return data

    # Or a dictionary containing data
    if isinstance(data, dict):
        return data.get("data", [])

    return []


# =========================
# TRADE FLOW
# =========================

def calculate_trade_flow(trades):

    buy_volume = 0.0
    sell_volume = 0.0

    for trade in trades:

        try:
            quantity = float(trade.get("q", 0))
        except (ValueError, TypeError):
            quantity = 0.0

        # m=True:
        # buyer is market maker
        # therefore aggressive side is seller
        if trade.get("m") is True:
            sell_volume += quantity
        else:
            buy_volume += quantity

    delta = buy_volume - sell_volume

    return buy_volume, sell_volume, delta


# =========================
# ORDER BOOK
# =========================

def calculate_orderbook(depth):

    if not isinstance(depth, dict):
        return 0.0, 0.0, 0.0

    bids = depth.get("b", [])
    asks = depth.get("a", [])

    bid_volume = 0.0
    ask_volume = 0.0

    for item in bids:

        try:
            bid_volume += float(item[1])
        except (ValueError, TypeError, IndexError):
            pass

    for item in asks:

        try:
            ask_volume += float(item[1])
        except (ValueError, TypeError, IndexError):
            pass

    total = bid_volume + ask_volume

    if total > 0:
        imbalance = (
            (bid_volume - ask_volume) / total
        ) * 100
    else:
        imbalance = 0.0

    return bid_volume, ask_volume, imbalance


# =========================
# TREND
# =========================

def candle_trend(klines):

    if not isinstance(klines, list):
        return "UNKNOWN"

    if len(klines) < 2:
        return "UNKNOWN"

    try:

        previous = float(
            klines[-2]["close"]
        )

        current = float(
            klines[-1]["close"]
        )

    except (KeyError, TypeError, ValueError):

        return "UNKNOWN"

    if current > previous:
        return "BULLISH"

    elif current < previous:
        return "BEARISH"

    return "FLAT"


# =========================
# AI-STYLE SCORE
# =========================

def calculate_score(
    trend15,
    trend1h,
    delta,
    imbalance
):

    score = 50

    # 15 minute trend
    if trend15 == "BULLISH":
        score += 15

    elif trend15 == "BEARISH":
        score -= 15

    # 1 hour trend
    if trend1h == "BULLISH":
        score += 15

    elif trend1h == "BEARISH":
        score -= 15

    # Trade flow
    if delta > 0:
        score += 10

    elif delta < 0:
        score -= 10

    # Order book
    if imbalance > 10:
        score += 10

    elif imbalance < -10:
        score -= 10

    return max(
        0,
        min(100, score)
    )


# =========================
# SIGNAL
# =========================

def get_signal(score):

    if score >= 65:
        return "🟢 BUY"

    elif score <= 35:
        return "🔴 SELL"

    return "⚪ NO TRADE"


# =========================
# TELEGRAM
# =========================

def send_telegram(message):

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


# =========================
# MAIN
# =========================

def main():

    # Get market data
    ticker = get_ticker()
    depth = get_depth()
    trades = get_trades()

    # Get candles
    klines15 = get_klines(
        "15m",
        20
    )

    klines1h = get_klines(
        "1h",
        20
    )

    # BTC price
    try:
        price = float(
            ticker.get("c", 0)
        )
    except (ValueError, TypeError):
        price = 0.0

    # Trade flow
    buy_volume, sell_volume, delta = (
        calculate_trade_flow(trades)
    )

    # Order book
    bid_volume, ask_volume, imbalance = (
        calculate_orderbook(depth)
    )

    # Trends
    trend15 = candle_trend(
        klines15
    )

    trend1h = candle_trend(
        klines1h
    )

    # Score
    score = calculate_score(
        trend15,
        trend1h,
        delta,
        imbalance
    )

    # Signal
    signal = get_signal(score)

    # Time
    now = datetime.now(
        timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    # Telegram message
    message = f"""
₿ BTC AI MONITOR V2

⏰ {now}

💰 BTCUSDT
${price:,.2f}

━━━━━━━━━━━━━━━━━━

📊 TRADE FLOW

🟢 Buy Volume
{buy_volume:.4f} BTC

🔴 Sell Volume
{sell_volume:.4f} BTC

⚖️ Net Delta
{delta:+.4f} BTC

━━━━━━━━━━━━━━━━━━

📖 ORDER BOOK

🟢 Bid Liquidity
{bid_volume:.4f} BTC

🔴 Ask Liquidity
{ask_volume:.4f} BTC

⚖️ Imbalance
{imbalance:+.2f}%

━━━━━━━━━━━━━━━━━━

📈 TREND

15M: {trend15}
1H: {trend1h}

━━━━━━━━━━━━━━━━━━

🎯 AI-STYLE SCORE

{score}/100

{signal}

━━━━━━━━━━━━━━━━━━

⚠️ PAPER / ALERT MODE

No automatic trade execution.

ℹ️ Trade flow represents the
recent aggregate-trade sample
returned by Shark's public API.
"""

    # Send Telegram
    send_telegram(message)

    # GitHub log
    print(message)


# =========================
# START
# =========================

if __name__ == "__main__":
    main()
