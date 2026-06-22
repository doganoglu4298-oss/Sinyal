import os
import time
import requests
import pandas as pd
from binance.client import Client

BOT_TOKEN = os.getenv("8844263738:AAFOWc2MH4BxEeXQoxm7LbIy1YPdQaY6wE8")
CHAT_ID = os.getenv("8560896518")

SYMBOLS = ["SOLUSDT", "WLDUSDT"]
INTERVAL = Client.KLINE_INTERVAL_15MINUTE

client = Client()

last_signal = {}

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": text
    })

def rsi(series, period=14):
    delta = series.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def check_symbol(symbol):
    klines = client.get_klines(
        symbol=symbol,
        interval=INTERVAL,
        limit=100
    )

    closes = pd.Series([float(k[4]) for k in klines])

    rsi_values = rsi(closes, 14)

    prev_rsi = rsi_values.iloc[-2]
    curr_rsi = rsi_values.iloc[-1]

    signal = None

    if prev_rsi < 55 and curr_rsi >= 55:
        signal = "LONG"

    elif prev_rsi > 45 and curr_rsi <= 45:
        signal = "SHORT"

    if signal:
        key = f"{symbol}_{signal}"

        if last_signal.get(symbol) != key:
            send_telegram(
                f"🚨 {symbol}\n"
                f"Sinyal: {signal}\n"
                f"RSI: {curr_rsi:.2f}\n"
                f"Zaman Dilimi: 15m"
            )
            last_signal[symbol] = key

while True:
    try:
        for symbol in SYMBOLS:
            check_symbol(symbol)

    except Exception as e:
        print(e)

    time.sleep(60)
