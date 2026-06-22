import os
import time
import requests
import pandas as pd
from datetime import datetime
from binance.client import Client

# ======================
# ENV
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = Client()

SYMBOLS = ["SOLUSDT", "WLDUSDT"]

TIMEFRAME = Client.KLINE_INTERVAL_15MINUTE

RSI_LEN = 10
ATR_LEN = 10
VOL_LEN = 40

SL_ATR = 0.8
RR = 2.5

# ======================
# TRACKER
# ======================

trade_stats = {
    "LONG": {"signal": 0, "win": 0},
    "SHORT": {"signal": 0, "win": 0}
}

last_signal = {}
last_update_id = 0
last_scan = "none"


# ======================
# TELEGRAM
# ======================

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg},
            timeout=10
        )
    except:
        pass


# ======================
# INDICATORS
# ======================

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()

    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ======================
# DATA
# ======================

def get_data(symbol):
    klines = client.get_klines(
        symbol=symbol,
        interval=TIMEFRAME,
        limit=250
    )

    df = pd.DataFrame(klines, columns=[
        "t","o","h","l","c","v",
        "x1","x2","x3","x4","x5","x6"
    ])

    for c in ["o","h","l","c","v"]:
        df[c] = df[c].astype(float)

    df.rename(columns={
        "o":"open",
        "h":"high",
        "l":"low",
        "c":"close",
        "v":"volume"
    }, inplace=True)

    return df


# ======================
# STRATEGY ENGINE
# ======================

def check(symbol):

    try:
        df = get_data(symbol)

        ema50 = df["close"].ewm(span=50).mean()
        ema200 = df["close"].ewm(span=200).mean()

        r = rsi(df["close"], RSI_LEN)
        a = atr(df, ATR_LEN)
        vol_ma = df["volume"].rolling(VOL_LEN).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]

        price = last["close"]

        if pd.isna(a.iloc[-1]) or pd.isna(r.iloc[-1]):
            return

        current_rsi = r.iloc[-1]
        prev_rsi = r.iloc[-2]
        current_atr = a.iloc[-1]

        bull = ema50.iloc[-1] > ema200.iloc[-1]
        bear = ema50.iloc[-1] < ema200.iloc[-1]

        vol_ok = last["volume"] > vol_ma.iloc[-1] * 1.2

        vwap = (df["close"] * df["volume"]).cumsum() / df["volume"].cumsum()

        above_vwap = price > vwap.iloc[-1]
        below_vwap = price < vwap.iloc[-1]

        trend_strength = abs(ema50.iloc[-1] - ema200.iloc[-1]) / price

        if trend_strength < 0.0005:
            return

        rsi_momentum = abs(current_rsi - prev_rsi) > 2

        atr_filter = current_atr > a.rolling(20).mean().iloc[-1]

        # ======================
        # SIGNALS
        # ======================

        long_signal = (
            bull
            and above_vwap
            and vol_ok
            and atr_filter
            and rsi_momentum
            and prev_rsi < 45
            and current_rsi >= 45
        )

        short_signal = (
            bear
            and below_vwap
            and vol_ok
            and atr_filter
            and rsi_momentum
            and prev_rsi > 55
            and current_rsi <= 55
        )

        # ======================
        # LONG
        # ======================

        if long_signal:

            trade_stats["LONG"]["signal"] += 1

            sl = price - (current_atr * SL_ATR)
            tp = price + ((price - sl) * RR)

            if last_signal.get(symbol) != "LONG":

                send(f"""
🚀 LONG V5+

{symbol}

Entry: {price:.4f}
SL: {sl:.4f}
TP: {tp:.4f}

RSI: {current_rsi:.2f}
""")

                last_signal[symbol] = "LONG"

        # ======================
        # SHORT
        # ======================

        elif short_signal:

            trade_stats["SHORT"]["signal"] += 1

            sl = price + (current_atr * SL_ATR)
            tp = price - ((sl - price) * RR)

            if last_signal.get(symbol) != "SHORT":

                send(f"""
🔻 SHORT V5+

{symbol}

Entry: {price:.4f}
SL: {sl:.4f}
TP: {tp:.4f}

RSI: {current_rsi:.2f}
""")

                last_signal[symbol] = "SHORT"

    except Exception as e:
        print(symbol, "error:", e)


# ======================
# TELEGRAM COMMANDS
# ======================

def telegram_commands(text):

    total = trade_stats["LONG"]["signal"] + trade_stats["SHORT"]["signal"]
    wins = trade_stats["LONG"]["win"] + trade_stats["SHORT"]["win"]

    winrate = (wins / total * 100) if total > 0 else 0

    if text == "/stats":

        send(f"""
📊 V5+ STATS

Total Signals: {total}
Wins: {wins}
Winrate: %{winrate:.2f}

LONG: {trade_stats['LONG']}
SHORT: {trade_stats['SHORT']}
""")

    if text == "/win LONG":
        trade_stats["LONG"]["win"] += 1
        send("LONG WIN +1")

    if text == "/win SHORT":
        trade_stats["SHORT"]["win"] += 1
        send("SHORT WIN +1")


# ======================
# TELEGRAM POLL
# ======================

def telegram_poll():

    global last_update_id

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": last_update_id + 1},
            timeout=10
        ).json()

        for u in r.get("result", []):

            last_update_id = u["update_id"]

            text = u.get("message", {}).get("text", "")

            telegram_commands(text)

    except:
        pass


# ======================
# START
# ======================

send("✅ V5+ Railway Bot Started")

print("V5+ running...")

while True:
    try:
        for s in SYMBOLS:
            check(s)

        telegram_poll()

        print(f"[{datetime.now()}] scan done")

        time.sleep(60)

    except Exception as e:
        print("MAIN ERROR:", e)
        time.sleep(10)
