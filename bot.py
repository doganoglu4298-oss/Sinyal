import os
import time
import requests
import pandas as pd
from datetime import datetime
from binance.client import Client

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = Client()

SYMBOLS = [
    "SOLUSDT",
    "WLDUSDT"
]

TIMEFRAME = Client.KLINE_INTERVAL_15MINUTE

RSI_LEN = 10
ATR_LEN = 10
VOL_LEN = 40

SL_ATR = 0.8
RR = 2.5

last_signal = {}
last_scan = "Başlatılmadı"
last_update_id = 0


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
        print("Telegram:", e)


def calc_rsi(series, period):
    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def calc_atr(df, period):
    h_l = df["high"] - df["low"]

    h_c = (
        df["high"] -
        df["close"].shift()
    ).abs()

    l_c = (
        df["low"] -
        df["close"].shift()
    ).abs()

    tr = pd.concat(
        [h_l, h_c, l_c],
        axis=1
    ).max(axis=1)

    return tr.rolling(period).mean()


def get_data(symbol):

    candles = client.get_klines(
        symbol=symbol,
        interval=TIMEFRAME,
        limit=250
    )

    df = pd.DataFrame(
        candles,
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "x1",
            "x2",
            "x3",
            "x4",
            "x5",
            "x6"
        ]
    )

    for c in [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]:
        df[c] = df[c].astype(float)

    return df


def signal_check(df):

    df["RSI"] = calc_rsi(
        df["close"],
        RSI_LEN
    )

    df["ATR"] = calc_atr(
        df,
        ATR_LEN
    )

    df["VOL"] = (
        df["volume"]
        .rolling(VOL_LEN)
        .mean()
    )


    last = df.iloc[-1]
    prev = df.iloc[-2]

    price = last["close"]
    atr = last["ATR"]


    volume_ok = (
        last["volume"] >
        last["VOL"]
    )


    signal = None


    if (
        prev["RSI"] < 30
        and last["RSI"] > 30
        and volume_ok
    ):
        signal = "LONG"


    elif (
        prev["RSI"] > 70
        and last["RSI"] < 70
        and volume_ok
    ):
        signal = "SHORT"


    if signal == "LONG":

        sl = price - (atr * SL_ATR)

        tp = price + ((price-sl) * RR)


    elif signal == "SHORT":

        sl = price + (atr * SL_ATR)

        tp = price - ((sl-price) * RR)


    else:
        return None


    return {
        "signal": signal,
        "price": price,
        "rsi": last["RSI"],
        "tp": tp,
        "sl": sl
    }


def scan_market():

    global last_scan

    last_scan = datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    )


    for symbol in SYMBOLS:

        try:

            df = get_data(symbol)

            result = signal_check(df)


            if result:

                key = (
                    symbol,
                    result["signal"]
                )


                if key in last_signal:
                    continue


                last_signal[key] = True


                send_telegram(
f"""
🚨 RSI ALARM

Coin:
{symbol}

Yön:
{result['signal']}

Fiyat:
{result['price']:.4f}

RSI:
{result['rsi']:.2f}

🎯 TP:
{result['tp']:.4f}

🛑 SL:
{result['sl']:.4f}

⏱ {last_scan}
"""
                )


        except Exception as e:

            print(symbol, e)



def telegram_check():

    global last_update_id

    try:

        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={
                "offset": last_update_id + 1,
                "timeout": 5
            },
            timeout=10
        ).json()


        for u in r.get("result", []):

            last_update_id = u["update_id"]

            text = (
                u.get("message", {})
                .get("text", "")
            )


            if text == "/durum":

                send_telegram(
f"""
🤖 BOT AKTİF

Son tarama:
{last_scan}

Coinler:
{', '.join(SYMBOLS)}
"""
                )


    except Exception as e:

        print("Telegram kontrol:", e)



send_telegram("✅ Bot başladı")


while True:

    try:

        scan_market()

        telegram_check()

        time.sleep(60)


    except Exception as e:

        print("Ana döngü:", e)

        time.sleep(10)
