import os
import time
import requests
import pandas as pd
from binance.client import Client

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = [
    "SOLUSDT",
    "WLDUSDT"
]

client = Client()

last_signal = {}

def send_telegram(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message
            },
            timeout=10
        )
        print("Telegram mesajı gönderildi")
    except Exception as e:
        print("Telegram hatası:", e)

def calculate_rsi(close_prices, period=14):
    delta = close_prices.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))

def check_symbol(symbol):
    try:
        print(f"Kontrol ediliyor: {symbol}")

        klines = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_15MINUTE,
            limit=100
        )

        closes = pd.Series(
            [float(k[4]) for k in klines]
        )

        rsi = calculate_rsi(closes)

        prev_rsi = rsi.iloc[-2]
        curr_rsi = rsi.iloc[-1]

        print(
            f"{symbol} RSI Önceki={prev_rsi:.2f} "
            f"Güncel={curr_rsi:.2f}"
        )

        signal = None

        if prev_rsi < 55 and curr_rsi >= 55:
            signal = "LONG"

        elif prev_rsi > 45 and curr_rsi <= 45:
            signal = "SHORT"

        if signal:
            if last_signal.get(symbol) != signal:

                text = (
                    f"🚨 {symbol}\n"
                    f"Sinyal: {signal}\n"
                    f"RSI: {curr_rsi:.2f}\n"
                    f"Periyot: 15 Dakika"
                )

                send_telegram(text)

                last_signal[symbol] = signal

    except Exception as e:
        print(f"{symbol} hata:", e)

print("Bot başlatıldı")

while True:
    try:
        for symbol in SYMBOLS:
            check_symbol(symbol)

        print("60 saniye bekleniyor...")
        time.sleep(60)

    except Exception as e:
        print("Genel hata:", e)
        time.sleep(60)
