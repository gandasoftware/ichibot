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
# MACRO ONLINE (WORLD BANK)
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
            "Nilai Beli": nilai_beli,
            "Harga Now": harga_now,
            "Nilai Now": nilai_now,
            "Gain": gain,
            "Gain %": gain_pct
        })

        total_beli += nilai_beli
        total_now += nilai_now

    df = pd.DataFrame(rows)
    df["Bobot"] = df["Nilai Now"] / total_now * 100 if total_now else 0

    # ===== SUMMARY =====
    total_porto = total_now + cash
    porsi_saham = total_now / total_porto * 100 if total_porto else 0
    porsi_cash = 100 - porsi_saham

    buffett = MARKET_CAP_IDX / GDP_INDONESIA * 100

    if buffett < 50:
        kondisi_pasar = "SANGAT MURAH"
        target_buffett = 90
        cash_powder = 10
    elif buffett < 60:
        kondisi_pasar = "MURAH"
        target_buffett = 85
        cash_powder = 15
    elif buffett < 80:
        kondisi_pasar = "WAJAR"
        target_buffett = 75
        cash_powder = 25
    elif buffett < 100:
        kondisi_pasar = "MAHAL"
        target_buffett = 65
        cash_powder = 35
    else:
        kondisi_pasar = "SANGAT MAHAL"
        target_buffett = 60
        cash_powder = 40

    if porsi_saham > target_buffett + 2:
        status_vs = "OVERWEIGHT vs BUFFETT"
    elif porsi_saham < target_buffett - 2:
        status_vs = "UNDERWEIGHT vs BUFFETT"
    else:
        status_vs = "SESUAI TARGET"

    aksi = "TAMBAH SAHAM" if porsi_saham < target_buffett - 2 else "TAHAN / REBALANCE"
    ihsg_last = get_ihsg()

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

    output += "." * 50 + "\n"
    output += f"Saham Anda          : {porsi_saham:>6.2f} %\n"
    output += f"Target Buffett      : {target_buffett:>6} %\n"
    output += f"Cash Powder Buffett : {cash_powder:>6} %\n"
    output += f"Status vs Buffett   : {status_vs}\n"

    output += "." * 50 + "\n"
    output += f"Total Saham         : {rupiah(total_now)}\n"
    output += f"Cash                : {rupiah(cash)}\n"
    output += f"Total               : {rupiah(total_porto)}\n"

    output += "." * 50 + "\n"
    output += f"Porsi Cash          : {porsi_cash:>6.2f} %\n"
    output += f"REKOMENDASI AKSI    : {aksi}\n"

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
