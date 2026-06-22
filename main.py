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
last_update_id = 0
last_scan_time = "Henüz tarama yapılmadı"

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

    high_close = (
        df["high"] - df["close"].shift()
    ).abs()

    low_close = (
        df["low"] - df["close"].shift()
    ).abs()

    tr = pd.concat(
        [high_low, high_close, low_close],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean()

def get_market_data(symbol):

    klines = client.get_klines(
        symbol=symbol,
        interval=Client.KLINE_INTERVAL_15MINUTE,
        limit=250
    )

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time","open","high","low",
            "close","volume",
            "close_time","qav",
            "num_trades",
            "taker_base",
            "taker_quote",
            "ignore"
        ]
    )

    for col in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:
        df[col] = df[col].astype(float)

    return df
def analyze_coin(symbol):

    try:

        symbol = symbol.upper()

        df = get_market_data(symbol)

        ema50 = df["close"].ewm(span=50).mean()
        ema200 = df["close"].ewm(span=200).mean()

        rsi_values = rsi(df["close"], RSI_LEN)

        vol_sma = df["volume"].rolling(VOL_LEN).mean()

        current_close = df["close"].iloc[-1]
        current_rsi = rsi_values.iloc[-1]

        bull_trend = ema50.iloc[-1] > ema200.iloc[-1]

        vwap = (
            (df["close"] * df["volume"]).cumsum()
            / df["volume"].cumsum()
        )

        above_vwap = current_close > vwap.iloc[-1]

        vol_filter = (
            df["volume"].iloc[-1]
            > vol_sma.iloc[-1]
        )

        msg = (
            f"📊 {symbol}\n\n"
            f"Fiyat: {current_close:.4f}\n"
            f"RSI: {current_rsi:.2f}\n\n"
            f"Trend: {'BULL ✅' if bull_trend else 'BEAR ❌'}\n"
            f"VWAP: {'✅' if above_vwap else '❌'}\n"
            f"Hacim: {'✅' if vol_filter else '❌'}\n\n"
            f"Son Tarama:\n{last_scan_time}"
        )

        send_telegram(msg)

    except Exception as e:
        send_telegram(f"❌ Hata: {e}")

def handle_command(text):

    if text.startswith("/coin"):

        parts = text.split()

        if len(parts) < 2:

            send_telegram(
                "Kullanım:\n/coin SOLUSDT"
            )

            return

        analyze_coin(parts[1])

    elif text == "/status":

        send_telegram(
            f"🤖 Yusuf Scalp V5 AKTİF\n\n"
            f"Takip Edilen Coinler:\n"
            f"{', '.join(SYMBOLS)}\n\n"
            f"Son Tarama:\n"
            f"{last_scan_time}"
        )

def get_updates():

    global last_update_id

    try:

        url = (
            f"https://api.telegram.org/"
            f"bot{BOT_TOKEN}/getUpdates"
        )

        r = requests.get(
            url,
            params={
                "offset": last_update_id + 1,
                "timeout": 1
            },
            timeout=5
        )

        data = r.json()

        if not data.get("ok"):
            return

        for update in data["result"]:

            last_update_id = update["update_id"]

            if "message" not in update:
                continue

            text = update["message"].get(
                "text",
                ""
            )

            handle_command(text)

    except Exception as e:

        print(
            "Telegram komut hatası:",
            e
        )
        def check_symbol(symbol):

    try:

        df = get_market_data(symbol)

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

last_scan = 0

while True:

    try:

        now = time.time()

        # Telegram komutlarını her 5 saniyede kontrol et
        get_updates()

        # Coin taramasını her 60 saniyede yap
        if now - last_scan >= 60:

            for symbol in SYMBOLS:
                check_symbol(symbol)

            last_scan_time = datetime.now().strftime(
                "%d-%m-%Y %H:%M:%S"
            )

            print(
                f"\n[{last_scan_time}] "
                f"Tarama tamamlandı. "
                f"60 saniye sonra tekrar taranacak.\n"
            )

            last_scan = now

        time.sleep(5)

    except Exception as e:

        print(
            f"[{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}] "
            f"Genel hata: {e}"
        )

        time.sleep(5)
