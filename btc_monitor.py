import os
import requests
from datetime import datetime, timezone

BASE_URL = "https://api.sharkexchange.in"
PAIR = "BTCUSDT"

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def get_json(url, method="GET", payload=None):
    if method == "POST":
        response = requests.post(url, json=payload, timeout=20)
    else:
        response = requests.get(url, timeout=20)

    response.raise_for_status()
    return response.json()


def get_ticker():
    data = get_json(
        f"{BASE_URL}/v1/market/ticker24Hr/{PAIR}"
    )
    return data.get("data", data)


def get_depth():
    data = get_json(
        f"{BASE_URL}/v1/market/depth/{PAIR}"
    )
    return data.get("data", data)


def get_trades():
    data = get_json(
        f"{BASE_URL}/v1/market/aggTrade/{PAIR}"
    )
    return data.get("data", [])


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

    return data.get("data", data)


def calculate_trade_flow(trades):
    buy_volume = 0.0
    sell_volume = 0.0

    for trade in trades:
        quantity = float(trade.get("q", 0))

        # m=true means buyer is market maker.
        # Therefore aggressive seller volume is represented here.
        if trade.get("m") is True:
            sell_volume += quantity
        else:
            buy_volume += quantity

    delta = buy_volume - sell_volume

    return buy_volume, sell_volume, delta


def calculate_orderbook(depth):
    bids = depth.get("b", [])
    asks = depth.get("a", [])

    bid_volume = sum(float(x[1]) for x in bids)
    ask_volume = sum(float(x[1]) for x in asks)

    total = bid_volume + ask_volume

    if total > 0:
        imbalance = ((bid_volume - ask_volume) / total) * 100
    else:
        imbalance = 0

    return bid_volume, ask_volume, imbalance


def candle_trend(klines):
    if len(klines) < 2:
        return "UNKNOWN"

    previous = float(klines[-2]["close"])
    current = float(klines[-1]["close"])

    if current > previous:
        return "BULLISH"
    elif current < previous:
        return "BEARISH"
    else:
        return "FLAT"


def calculate_score(trend15, trend1h, delta, imbalance):
    score = 50

    if trend15 == "BULLISH":
        score += 15
    elif trend15 == "BEARISH":
        score -= 15

    if trend1h == "BULLISH":
        score += 15
    elif trend1h == "BEARISH":
        score -= 15

    if delta > 0:
        score += 10
    elif delta < 0:
        score -= 10

    if imbalance > 10:
        score += 10
    elif imbalance < -10:
        score -= 10

    return max(0, min(100, score))


def get_signal(score):
    if score >= 65:
        return "🟢 BUY"
    elif score <= 35:
        return "🔴 SELL"
    else:
        return "⚪ NO TRADE"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=20
    )

    response.raise_for_status()


def main():
    ticker = get_ticker()
    depth = get_depth()
    trades = get_trades()

    klines15 = get_klines("15m", 20)
    klines1h = get_klines("1h", 20)

    price = float(ticker.get("c", 0))

    buy_volume, sell_volume, delta = calculate_trade_flow(trades)

    bid_volume, ask_volume, imbalance = calculate_orderbook(depth)

    trend15 = candle_trend(klines15)
    trend1h = candle_trend(klines1h)

    score = calculate_score(
        trend15,
        trend1h,
        delta,
        imbalance
    )

    signal = get_signal(score)

    now = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    message = f"""
₿ BTC AI MONITOR V2

⏰ {now}

💰 BTCUSDT: ${price:,.2f}

📊 TRADE FLOW
🟢 Buy Volume: {buy_volume:.4f} BTC
🔴 Sell Volume: {sell_volume:.4f} BTC
⚖️ Delta: {delta:+.4f} BTC

📖 ORDER BOOK
🟢 Bid Liquidity: {bid_volume:.4f} BTC
🔴 Ask Liquidity: {ask_volume:.4f} BTC
⚖️ Imbalance: {imbalance:+.2f}%

📈 TREND
15M: {trend15}
1H: {trend1h}

🎯 AI SCORE: {score}/100

{signal}

⚠️ PAPER / ALERT MODE
No automatic trade execution.

ℹ️ Buy/Sell flow is calculated from the
recent aggregate-trade sample returned by
Shark's public API.
"""

    send_telegram(message)

    print(message)


if __name__ == "__main__":
    main()
