import os
import time
import requests
import pandas as pd
import csv
from datetime import datetime
from binance.client import Client

# ======================
# ENV
# ======================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = Client()

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "AVAXUSDT",
    "LINKUSDT",
    "SUIUSDT",
    "ARBUSDT"
]

TIMEFRAME = Client.KLINE_INTERVAL_15MINUTE

RSI_LEN = 10
ATR_LEN = 10
VOL_LEN = 40

SL_ATR = 1.5
RR = 2.5

JOURNAL_FILE = "journal.csv"

positions = {}
last_signal = {}

positions = {}
last_signal = {}

last_update_id = 0

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
# JOURNAL INIT
# ======================

def init_journal():
    if not os.path.exists(JOURNAL_FILE):
        with open(JOURNAL_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time", "symbol", "side",
                "entry", "exit", "pnl", "result"
            ])


# ======================
# LOG TRADE
# ======================

def log_trade(symbol, side, entry, exit_price, result):

    pnl = ((exit_price - entry) / entry) * 100 if side == "LONG" else ((entry - exit_price) / entry) * 100

    with open(JOURNAL_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now(),
            symbol,
            side,
            entry,
            exit_price,
            round(pnl, 2),
            result
        ])


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
# POSITION TRACKER
# ======================

def update_positions(symbol, price):

    if symbol not in positions:
        return

    pos = positions[symbol]

    if pos["side"] == "LONG":

        if price >= pos["tp"]:
            log_trade(symbol, "LONG", pos["entry"], price, "WIN")
            send(f"✅ WIN LONG {symbol} | Exit: {price}")
            del positions[symbol]

        elif price <= pos["sl"]:
            log_trade(symbol, "LONG", pos["entry"], price, "LOSS")
            send(f"❌ LOSS LONG {symbol} | Exit: {price}")
            del positions[symbol]

    elif pos["side"] == "SHORT":

        if price <= pos["tp"]:
            log_trade(symbol, "SHORT", pos["entry"], price, "WIN")
            send(f"✅ WIN SHORT {symbol} | Exit: {price}")
            del positions[symbol]

        elif price >= pos["sl"]:
            log_trade(symbol, "SHORT", pos["entry"], price, "LOSS")
            send(f"❌ LOSS SHORT {symbol} | Exit: {price}")
            del positions[symbol]


# ======================
# STRATEGY
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

        price = last["close"]

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
            and prev_rsi < 50
            and current_rsi >= 50
        )

        short_signal = (
            bear
            and below_vwap
            and vol_ok
            and atr_filter
            and rsi_momentum
            and prev_rsi > 50
            and current_rsi <= 50
        )

        # ======================
        # LONG
        # ======================

        if long_signal and symbol not in positions:

            entry = price
            sl = entry - (current_atr * SL_ATR)
            tp = entry + ((entry - sl) * RR)

            positions[symbol] = {
                "side": "LONG",
                "entry": entry,
                "sl": sl,
                "tp": tp
            }

            send(f"""
🚀 PAPER LONG

{symbol}
Entry: {entry}
SL: {sl}
TP: {tp}
""")

        # ======================
        # SHORT
        # ======================

        elif short_signal and symbol not in positions:

            entry = price
            sl = entry + (current_atr * SL_ATR)
            tp = entry - ((sl - entry) * RR)

            positions[symbol] = {
                "side": "SHORT",
                "entry": entry,
                "sl": sl,
                "tp": tp
            }

            send(f"""
🔻 PAPER SHORT

{symbol}
Entry: {entry}
SL: {sl}
TP: {tp}
""")

        # POSITION UPDATE
        update_positions(symbol, price)

    except Exception as e:
        print(symbol, "error:", e)


# ======================
# JOURNAL STATS
# ======================

def journal_stats():

    wins = 0
    losses = 0

    if not os.path.exists(JOURNAL_FILE):
        return

    with open(JOURNAL_FILE, "r") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if row["result"] == "WIN":
                wins += 1
            else:
                losses += 1

    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0

    send(f"""
📊 JOURNAL

Total: {total}
Wins: {wins}
Loss: {losses}
Winrate: %{winrate:.2f}
""")


# ======================
# TELEGRAM POLL
# ======================

def telegram_poll():

    global last_update_id

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            timeout=10
        ).json()

        for u in r.get("result", []):

            update_id = u["update_id"]

            if update_id <= last_update_id:
                continue

            last_update_id = update_id

            text = u.get("message", {}).get("text", "")

            if text == "/journal":
                journal_stats()

    except:
        pass


# ======================
# START
# ======================

init_journal()
send("✅ V5+ JOURNAL BOT STARTED")

print("running...")

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
