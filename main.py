import os
import time
import requests
import pandas as pd
from datetime import datetime
from binance.client import Client

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = [
    "SOLUSDT",
    "WLDUSDT"
]

RSI_LEN = 10
ATR_LEN = 10
VOL_LEN = 40
SL_ATR = 0.8
RR = 2.5

client = Client()

last_signal = {}

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": msg
            },
            timeout=10
        )
        print("Telegram mesajı gönderildi")
    except Exception as e:
        print("Telegram hata:", e)

def rsi(series, period=14):
    delta = series.diff()

    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean()

def check_symbol(symbol):

    try:

        klines = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_15MINUTE,
            limit=250
        )

        df = pd.DataFrame(
            klines,
            columns=[
                "open_time","open","high","low","close","volume",
                "close_time","qav","num_trades",
                "taker_base","taker_quote","ignore"
            ]
        )

        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
            ema50 = df["close"].ewm(span=50).mean()
        ema200 = df["close"].ewm(span=200).mean()

        rsi_values = rsi(df["close"], RSI_LEN)

        atr_values = atr(df, ATR_LEN)

        vol_sma = df["volume"].rolling(VOL_LEN).mean()

        current_close = df["close"].iloc[-1]
        current_rsi = rsi_values.iloc[-1]
        prev_rsi = rsi_values.iloc[-2]

        current_atr = atr_values.iloc[-1]

        bull_trend = ema50.iloc[-1] > ema200.iloc[-1]
        bear_trend = ema50.iloc[-1] < ema200.iloc[-1]

        vol_filter = (
            df["volume"].iloc[-1]
            > vol_sma.iloc[-1]
        )

        vwap = (
            (df["close"] * df["volume"]).cumsum()
            / df["volume"].cumsum()
        )

        above_vwap = current_close > vwap.iloc[-1]
        below_vwap = current_close < vwap.iloc[-1]

        trend_text = (
            "BULL" if bull_trend
            else "BEAR" if bear_trend
            else "SIDE"
        )

        print(
    f"[{datetime.now().strftime('%H:%M:%S')}] "
    f"{symbol} | "
    f"Trend={trend_text} | "
    f"Close={current_close:.4f} | "
    f"VWAP={vwap.iloc[-1]:.4f} | "
    f"VOL={df['volume'].iloc[-1]:.0f}/{vol_sma.iloc[-1]:.0f} | "
    f"RSI={current_rsi:.2f}"
        )

        long_signal = (
            bull_trend
            and above_vwap
            and prev_rsi < 45
            and current_rsi >= 45
            and vol_filter
        )

        short_signal = (
            bear_trend
            and below_vwap
            and prev_rsi > 55
            and current_rsi <= 55
            and vol_filter
        )

        if long_signal:

            entry = current_close
            stop = entry - (current_atr * SL_ATR)

            risk = entry - stop

            tp = entry + (risk * RR)

            if last_signal.get(symbol) != "LONG":
                msg = (
                    f"🚀 LONG\n\n"
                    f"{symbol}\n\n"
                    f"Giriş: {entry:.4f}\n"
                    f"Stop: {stop:.4f}\n"
                    f"TP: {tp:.4f}\n\n"
                    f"RSI: {current_rsi:.2f}\n"
                    f"ATR: {current_atr:.4f}\n"
                    f"RR: {RR}"
                )

                send_telegram(msg)
                last_signal[symbol] = "LONG"

        elif short_signal:

            entry = current_close
            stop = entry + (current_atr * SL_ATR)

            risk = stop - entry

            tp = entry - (risk * RR)

            if last_signal.get(symbol) != "SHORT":

                msg = (
                    f"🔻 SHORT\n\n"
                    f"{symbol}\n\n"
                    f"Giriş: {entry:.4f}\n"
                    f"Stop: {stop:.4f}\n"
                    f"TP: {tp:.4f}\n\n"
                    f"RSI: {current_rsi:.2f}\n"
                    f"ATR: {current_atr:.4f}\n"
                    f"RR: {RR}"
                )

                send_telegram(msg)
                last_signal[symbol] = "SHORT"

    except Exception as e:
        print(f"{symbol} hata: {e}")

print("Yusuf Scalp V5 başlatıldı")

while True:
    try:

        for symbol in SYMBOLS:
            check_symbol(symbol)

        print(
            f"\n[{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}] "
            f"Tarama tamamlandı. "
            f"60 saniye sonra tekrar taranacak.\n"
        )

        time.sleep(60)

    except Exception as e:
        print(
            f"[{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}] "
            f"Genel hata: {e}"
        )
        time.sleep(60)
