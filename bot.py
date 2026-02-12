import os
import requests
import time
import pandas as pd
import yfinance as yf
from datetime import datetime

# ============================================================
# TELEGRAM CONFIG (RAILWAY VARIABLE)
# ============================================================

TOKEN = os.getenv("TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}"

last_update_id = None
EXCEL_FILE = "data.xlsx"

# ============================================================
# TELEGRAM FUNCTIONS
# ============================================================

def kirim_pesan(chat_id, text):
    requests.get(
        f"{URL}/sendMessage",
        params={
            "chat_id": chat_id,
            "text": f"<pre>{text}</pre>",
            "parse_mode": "HTML"
        }
    )

def ambil_update(offset=None):
    if offset:
        return requests.get(f"{URL}/getUpdates", params={"offset": offset}).json()
    return requests.get(f"{URL}/getUpdates").json()

# ============================================================
# MACRO ONLINE
# ============================================================

def get_gdp_indonesia_usd():
    url = "https://api.worldbank.org/v2/country/IDN/indicator/NY.GDP.MKTP.CD?format=json"
    r = requests.get(url, timeout=15)
    data = r.json()[1]
    for item in data:
        if item.get("value") is not None:
            return float(item["value"])
    return None

def get_marketcap_idx_usd():
    url = "https://api.worldbank.org/v2/country/IDN/indicator/CM.MKT.LCAP.CD?format=json"
    r = requests.get(url, timeout=15)
    data = r.json()[1]
    for item in data:
        if item.get("value") is not None:
            return float(item["value"])
    return None

# ============================================================
# HELPERS
# ============================================================

def to_float(val):
    if pd.isna(val):
        return 0.0
    if isinstance(val, str):
        val = val.replace(",", ".")
    return float(val)

def rupiah(x):
    return f"Rp {x:,.0f}".replace(",", ".")

def get_price(ticker, fallback=0):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        return float(data["Close"].iloc[-1])
    except:
        return fallback

def get_ihsg():
    try:
        data = yf.Ticker("^JKSE").history(period="5d")
        return float(data["Close"].dropna().iloc[-1])
    except:
        return 0.0

# ============================================================
# DASHBOARD ENGINE
# ============================================================

def build_dashboard():

    # ===== MACRO =====
    GDP_INDONESIA = get_gdp_indonesia_usd()
    MARKET_CAP_IDX = get_marketcap_idx_usd()

    # ===== LOAD PORTFOLIO =====
    saham_df = pd.read_excel(EXCEL_FILE, sheet_name="Saham")
    cash_df = pd.read_excel(EXCEL_FILE, sheet_name="Cash")
    cash = float(pd.to_numeric(cash_df.iloc[:,1], errors="coerce").dropna().iloc[-1])

    rows = []
    total_beli = 0
    total_now = 0

    for _, r in saham_df.iterrows():
        kode = r["Kode"]
        lot = int(r["Lot"])
        harga_beli = to_float(r["Harga Beli"])
        harga_now = get_price(f"{kode}.JK", fallback=harga_beli)

        nilai_beli = harga_beli * lot * 100
        nilai_now = harga_now * lot * 100
        gain = nilai_now - nilai_beli
        gain_pct = (gain / nilai_beli * 100) if nilai_beli else 0

        rows.append({
            "Kode": kode,
            "Lot": lot,
            "Harga Beli": harga_beli,
            "Harga Now": harga_now,
            "Nilai Now": nilai_now,
            "Gain": gain,
            "Gain %": gain_pct
        })

        total_beli += nilai_beli
        total_now += nilai_now

    df = pd.DataFrame(rows)
    df = df.sort_values("Nilai Now", ascending=False)

    # ===== SUMMARY =====
    total_porto = total_now + cash
    buffett = MARKET_CAP_IDX / GDP_INDONESIA * 100
    ihsg_last = get_ihsg()

    if buffett < 50:
        kondisi_pasar = "SANGAT MURAH"
    elif buffett < 60:
        kondisi_pasar = "MURAH"
    elif buffett < 80:
        kondisi_pasar = "WAJAR"
    elif buffett < 100:
        kondisi_pasar = "MAHAL"
    else:
        kondisi_pasar = "SANGAT MAHAL"

    # ===== OUTPUT =====
    now_str = datetime.now().strftime("%d %b %Y %H:%M")

    output = ""
    output += "~" * 50 + "\n"
    output += "GANDA DASHBOARD INVESTASI".center(50) + "\n"
    output += "~" * 50 + "\n\n"

    output += f"Analisa dijalankan  : {now_str}\n"
    output += "." * 50 + "\n"
    output += f"IHSG Terakhir       : {ihsg_last:>10,.2f}\n"
    output += f"GDP Indonesia       : ${GDP_INDONESIA/1e12:>5.2f} T\n"
    output += f"Market Cap IDX      : ${MARKET_CAP_IDX/1e12:>5.2f} T\n"
    output += f"Buffett Indicator   : {buffett:>6.2f} %\n"
    output += f"Pasar               : {kondisi_pasar}\n"

    output += "\n" + "." * 50 + "\n"
    output += f"Total Saham         : {rupiah(total_now)}\n"
    output += f"Cash                : {rupiah(cash)}\n"
    output += f"Total Equity        : {rupiah(total_porto)}\n"

    # ===== PORTFOLIO STYLE =====
    output += "\nPORTFOLIO SUMMARY\n"
    output += "==================\n\n"
    output += f"Cash Available : {rupiah(cash)}\n\n"
    output += "Holdings:\n"
    output += "--------------------------------\n\n"

    for _, r in df.iterrows():

        bobot = r["Nilai Now"] / total_now * 100 if total_now else 0
        sign = "+" if r["Gain"] >= 0 else "-"
        gain_pct = abs(r["Gain %"])

        output += f"{r['Kode']:<6}{r['Lot']:>5} lot   Avg {r['Harga Beli']:>7,.0f}\n"
        output += f"{'':11}Last {r['Harga Now']:>7,.0f}\n"
        output += f"{'':11}Value {rupiah(r['Nilai Now'])} ({bobot:.2f}%)\n"
        output += f"{'':11}Unrealized {sign}{rupiah(abs(r['Gain']))} ({sign}{gain_pct:.2f}%)\n\n"

    total_gain = total_now - total_beli
    total_gain_pct = total_gain / total_beli * 100 if total_beli else 0
    sign_total = "+" if total_gain >= 0 else "-"

    output += "--------------------------------\n"
    output += f"Total Market Value : {rupiah(total_now)}\n"
    output += f"Total Gain/Loss    : {sign_total}{rupiah(abs(total_gain))} ({sign_total}{abs(total_gain_pct):.2f}%)\n"
    output += f"Total Equity       : {rupiah(total_porto)}\n"

    return output

# ============================================================
# BOT LOOP
# ============================================================

print("Bot jalan...")

while True:
    try:
        data = ambil_update(last_update_id)

        if "result" in data and data["result"]:
            update = data["result"][-1]
            last_update_id = update["update_id"] + 1

            pesan = update["message"]
            chat_id = pesan["chat"]["id"]
            text = pesan.get("text", "").lower()

            if text == "/dashboard":
                hasil = build_dashboard()
                kirim_pesan(chat_id, hasil)

    except Exception as e:
        print("Error:", e)

    time.sleep(1)
