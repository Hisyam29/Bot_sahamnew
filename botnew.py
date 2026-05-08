import yfinance as yf
import pandas as pd
import requests
import numpy as np

# =========================================================
# FINAL BANDAR CONTINUATION BOT
# MORA-TYPE SCANNER
# =========================================================

TOKEN = "8265694791:AAHElCfxfPoB40pZe5yv9tvVcQEIFIAQUAw"
CHAT_IDS = ["1280847575"]

# ==============================
# CONFIG
# ==============================
DAILY_PERIOD = "6mo"
H4_PERIOD = "90d"

MIN_AVG_VALUE = 2_000_000_000   # 2B
MAX_EXTEND = 1.12               # max 12% di atas EMA20

TOP_LIMIT = 10

# =========================================================
# TELEGRAM
# =========================================================
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    for chat_id in CHAT_IDS:
        data = {
            "chat_id": chat_id,
            "text": message
        }

        try:
            requests.post(url, data=data)
        except:
            pass

# =========================================================
# LOAD SAHAM
# =========================================================
def load_symbols():
    df = pd.read_excel(r"C:\Users\Hisyam\OneDrive\Documents\Coding\saham.xlsx")

    print("KOLOM TERDETEKSI:", df.columns)

    # ambil kolom "Kode"
    symbols = df["Kode"].tolist()

    # bersihkan
    symbols = [str(s).strip().upper() for s in symbols if str(s) != 'nan']

    # tambah .JK
    symbols = [s + ".JK" for s in symbols]

    print("TOTAL SAHAM:", len(symbols))
    print(symbols[:10])

    return symbols

# =========================================================
# GET DATA
# =========================================================
def get_data(symbol, interval, period):

    df = yf.download(
        symbol,
        interval=interval,
        period=period,
        progress=False,
        auto_adjust=False
    )

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df.dropna(inplace=True)

    return df

# =========================================================
# SUPER TREND 2,1
# =========================================================
def compute_supertrend(df, period=2, multiplier=1):

    df = df.copy()

    hl2 = (df['High'] + df['Low']) / 2

    df['TR'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift()),
            abs(df['Low'] - df['Close'].shift())
        )
    )

    df['ATR'] = df['TR'].rolling(period).mean()

    df['upperband'] = hl2 + (multiplier * df['ATR'])
    df['lowerband'] = hl2 - (multiplier * df['ATR'])

    trend = [True]

    for i in range(1, len(df)):

        close = df['Close'].iloc[i]

        prev_upper = df['upperband'].iloc[i - 1]
        prev_lower = df['lowerband'].iloc[i - 1]

        if close > prev_upper:
            trend.append(True)

        elif close < prev_lower:
            trend.append(False)

        else:
            trend.append(trend[i - 1])

    df['in_uptrend'] = trend

    return df

# =========================================================
# EMA
# =========================================================
def add_ema(df):

    df['EMA20'] = df['Close'].ewm(span=20).mean()
    df['EMA50'] = df['Close'].ewm(span=50).mean()

    return df

# =========================================================
# VOLUME ANALYSIS
# =========================================================
def add_volume(df):

    df['VOL20'] = df['Volume'].rolling(20).mean()

    return df

# =========================================================
# BASE DETECTION
# =========================================================
def detect_base(df):

    recent = df.tail(10)

    high = recent['High'].max()
    low = recent['Low'].min()

    range_pct = (high - low) / low

    # base rapat
    if range_pct < 0.12:
        return True

    return False

# =========================================================
# EARLY MARKUP DETECTION
# =========================================================
def early_markup(df):

    current = df['in_uptrend'].iloc[-1]
    previous = df['in_uptrend'].iloc[-2]

    # reversal baru
    if current and not previous:
        return True

    return False

# =========================================================
# CONTINUATION QUALITY
# =========================================================
def continuation_quality(df):

    close = df['Close'].iloc[-1]

    ema20 = df['EMA20'].iloc[-1]

    # jangan terlalu jauh
    if close > ema20 * MAX_EXTEND:
        return False

    return True

# =========================================================
# FOLLOW THROUGH VOLUME
# =========================================================
def volume_progression(df):

    recent = df.tail(5)

    avg20 = df['VOL20'].iloc[-1]

    vol1 = recent['Volume'].iloc[-1]
    vol2 = recent['Volume'].iloc[-2]
    vol3 = recent['Volume'].iloc[-3]

    # volume bertahap naik
    if (
        vol1 > avg20 and
        (vol2 > avg20 * 0.8 or vol3 > avg20 * 0.8)
    ):
        return True

    return False

# =========================================================
# DAILY TREND
# =========================================================
def daily_trend(df):

    close = df['Close'].iloc[-1]

    ema20 = df['EMA20'].iloc[-1]
    ema50 = df['EMA50'].iloc[-1]

    # trend sehat
    if close > ema20 and ema20 > ema50:
        return True

    return False

# =========================================================
# SCORING
# =========================================================
def calculate_score(df_daily, df_h4):

    score = 0

    # ========================
    # DAILY TREND
    # ========================
    if daily_trend(df_daily):
        score += 25

    # ========================
    # H4 REVERSAL
    # ========================
    if early_markup(df_h4):
        score += 35

    # ========================
    # BASE
    # ========================
    if detect_base(df_daily):
        score += 15

    # ========================
    # VOLUME
    # ========================
    if volume_progression(df_daily):
        score += 15

    # ========================
    # CONTINUATION
    # ========================
    if continuation_quality(df_daily):
        score += 10

    return score

# =========================================================
# LABEL
# =========================================================
def get_label(score):

    if score >= 85:
        return "🔥 SUPER MOMENTUM"

    elif score >= 70:
        return "🟢 STRONG CONTINUATION"

    elif score >= 55:
        return "🟡 EARLY MOVE"

    return "⚪ WATCHLIST"

# =========================================================
# MAIN
# =========================================================
def run_bot():

    symbols = load_symbols()

    results = []

    send_telegram("🚀 BANDAR CONTINUATION BOT AKTIF")

    print("Scanning...")

    for symbol in symbols:

        try:

            # ==========================
            # DAILY
            # ==========================
            daily = get_data(symbol, "1d", DAILY_PERIOD)

            if len(daily) < 60:
                continue

            daily = compute_supertrend(daily)
            daily = add_ema(daily)
            daily = add_volume(daily)

            # ==========================
            # H4
            # ==========================
            h4 = get_data(symbol, "4h", H4_PERIOD)

            if len(h4) < 60:
                continue

            h4 = compute_supertrend(h4)
            h4 = add_ema(h4)
            h4 = add_volume(h4)

            # ==========================
            # VALUE
            # ==========================
            close = daily['Close'].iloc[-1]

            avg_value = (
                daily['Close'].tail(20).mean() *
                daily['Volume'].tail(20).mean()
            )

            if avg_value < MIN_AVG_VALUE:
                continue

            # ==========================
            # DAILY SUPER TREND WAJIB HIJAU
            # ==========================
            if not daily['in_uptrend'].iloc[-1]:
                continue

            # ==========================
            # DAILY WAJIB DIATAS EMA20
            # ==========================
            if close < daily['EMA20'].iloc[-1]:
                continue

            # ==========================
            # SCORE
            # ==========================
            score = calculate_score(daily, h4)

            # ==========================
            # FILTER FINAL
            # ==========================
            if score >= 55:

                label = get_label(score)

                results.append({
                    "symbol": symbol,
                    "score": score,
                    "price": int(close),
                    "label": label
                })

            print(symbol, score)

        except Exception as e:
            print(symbol, e)

    # =====================================================
    # SORT
    # =====================================================
    results = sorted(
        results,
        key=lambda x: x['score'],
        reverse=True
    )

    # =====================================================
    # OUTPUT
    # =====================================================
    if len(results) == 0:

        send_telegram("❌ Tidak ada setup bandar continuation")

    else:

        msg = "🚀 BANDAR CONTINUATION REPORT\n\n"

        for r in results[:TOP_LIMIT]:

            msg += (
                f"{r['label']}\n"
                f"{r['symbol']}\n"
                f"Score : {r['score']}\n"
                f"Price : {r['price']}\n\n"
            )

        send_telegram(msg)

    print("DONE")

# =========================================================
# RUN
# =========================================================
if __name__ == "__main__":
    run_bot()