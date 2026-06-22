import os
import time
import requests
import pandas as pd

from datetime import datetime
from binance.client import Client


# ======================
# TELEGRAM AYAR
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")



# ======================
# BINANCE AYAR
# ======================

client = Client()



# ======================
# COIN LİSTESİ
# ======================

SYMBOLS = [

    "SOLUSDT",
    "WLDUSDT"

]



# ======================
# STRATEJİ AYARLARI
# ======================

TIMEFRAME = Client.KLINE_INTERVAL_15MINUTE

RSI_LEN = 10

ATR_LEN = 10

VOL_LEN = 40


SL_ATR = 0.8

RR = 2.5



last_signal = {}

last_scan_time = "Başlatılmadı"

last_update_id = 0




# ======================
# TELEGRAM MESAJ
# ======================

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


    except Exception as e:

        print(
            "Telegram hata:",
            e
        )





# ======================
# RSI
# ======================

def calculate_rsi(series, period):


    delta = series.diff()


    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)



    avg_gain = (
        gain
        .rolling(period)
        .mean()
    )


    avg_loss = (
        loss
        .rolling(period)
        .mean()
    )



    rs = avg_gain / avg_loss



    return (
        100 -
        (100 / (1 + rs))
    )






# ======================
# ATR
# ======================

def calculate_atr(df, period):


    high_low = (
        df["high"]
        -
        df["low"]
    )



    high_close = (

        df["high"]
        -
        df["close"].shift()

    ).abs()



    low_close = (

        df["low"]
        -
        df["close"].shift()

    ).abs()



    tr = pd.concat(

        [

            high_low,

            high_close,

            low_close

        ],

        axis=1

    ).max(axis=1)



    return (

        tr
        .rolling(period)
        .mean()

    )





# ======================
# VERİ ÇEKME
# ======================

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

            "close_time",

            "qav",

            "trades",

            "tb",

            "tq",

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
    # ======================
# SİNYAL HESAPLAMA
# ======================

def check_signal(df):


    df["RSI"] = calculate_rsi(
        df["close"],
        RSI_LEN
    )


    df["ATR"] = calculate_atr(
        df,
        ATR_LEN
    )


    df["VOL_AVG"] = (

        df["volume"]
        .rolling(VOL_LEN)
        .mean()

    )



    last = df.iloc[-1]

    prev = df.iloc[-2]



    price = last["close"]

    rsi_now = last["RSI"]

    atr_now = last["ATR"]



    volume_ok = (

        last["volume"]

        >

        last["VOL_AVG"]

    )



    signal = None



    # LONG

    if (

        prev["RSI"] < 30

        and

        rsi_now > 30

        and

        volume_ok

    ):


        signal = "LONG"




    # SHORT

    elif (

        prev["RSI"] > 70

        and

        rsi_now < 70

        and

        volume_ok

    ):


        signal = "SHORT"




    if signal:


        if signal == "LONG":


            sl = (

                price

                -

                (atr_now * SL_ATR)

            )


            tp = (

                price

                +

                ((price-sl) * RR)

            )



        else:


            sl = (

                price

                +

                (atr_now * SL_ATR)

            )


            tp = (

                price

                -

                ((sl-price) * RR)

            )




        return {


            "signal": signal,

            "price": price,

            "rsi": rsi_now,

            "tp": tp,

            "sl": sl


        }



    return None






# ======================
# PİYASA TARAMA
# ======================


def scan():


    global last_scan_time



    last_scan_time = datetime.now().strftime(

        "%d-%m-%Y %H:%M:%S"

    )



    for symbol in SYMBOLS:


        try:


            df = get_data(symbol)


            result = check_signal(df)



            if result:


                key = (

                    symbol,

                    result["signal"]

                )



                if key in last_signal:

                    continue



                last_signal[key] = True




                msg = f"""

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


⏱
{last_scan_time}

"""



                send_telegram(msg)




        except Exception as e:


            print(

                symbol,

                "hata:",

                e

            )






# ======================
# TELEGRAM KOMUT
# ======================


def telegram_check():


    global last_update_id



    try:


        url = (

            f"https://api.telegram.org/"

            f"bot{BOT_TOKEN}/getUpdates"

        )



        data = requests.get(

            url,

            params={

                "offset":

                last_update_id + 1,

                "timeout":5

            },

            timeout=10

        ).json()



        for item in data.get(

            "result",

            []

        ):


            last_update_id = item["update_id"]



            text = (

                item

                .get("message",{})

                .get("text","")

            )



            if text == "/durum":



                send_telegram(

f"""

🤖 BOT AKTİF

Son tarama:

{last_scan_time}


Takip:

{', '.join(SYMBOLS)}

"""

                )



    except Exception as e:


        print(

            "Telegram kontrol hata:",

            e

        )





# ======================
# ANA DÖNGÜ
# ======================


while True:


    scan()


    telegram_check()


    time.sleep(60)
