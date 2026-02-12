import os
import requests
import time
import pandas as pd
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo  # WIB support

# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}"

last_update_id = None
EXCEL_FILE = "data.xlsx"

# ============================================================
# TELEGRAM
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
# MACRO DATA (WORLD BANK)
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

    # ===== WIB TIME =====
    now_str = datetime.now(ZoneInfo("Asia/Jakarta")).strftime("%d %b %Y %H:%M")

    # ===== MACRO =====
    GDP = get_gdp_indonesia_usd()
    MCAP = get_marketcap_idx_usd()
    ihsg = get_ihsg()

    buffett = MCAP / GDP * 100

    # ===== KONDISI PASAR + TARGET =====
    if buffett < 50:
        kondisi_pasar = "SANGAT MURAH"
        target_saham = 90
    elif buffett < 60:
        kondisi_pasar = "MURAH"
        target_saham = 85
    elif buffett < 80:
        kondisi_pasar = "WAJAR"
        target_saham = 75
    elif buffett < 100:
        kondisi_pasar = "MAHAL"
        target_saham = 65
    else:
        kondisi_pasar = "SANGAT MAHAL"
        target_saham = 60

    target_cash = 100 - target_saham

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
        avg = to_float(r["Harga Beli"])
        last = get_price(f"{kode}.JK", fallback=avg)

        nilai_beli = avg * lot * 100
        nilai_now = last * lot * 100
        gain = nilai_now - nilai_beli
        gain_pct = (gain / nilai_beli * 100) if nilai_beli else 0

        rows.append({
            "Kode": kode,
            "Lot": lot,
            "Avg": avg,
            "Last": last,
            "Nilai Now": nilai_now,
            "Gain": gain,
            "Gain %": gain_pct
        })

        total_beli += nilai_beli
        total_now += nilai_now

    df = pd.DataFrame(rows).sort_values("Nilai Now", ascending=False)

    total_equity = total_now + cash
    real_saham_pct = total_now / total_equity * 100 if total_equity else 0
    real_cash_pct = cash / total_equity * 100 if total_equity else 0

    deviasi = real_saham_pct - target_saham

    if deviasi > 2:
        rekomendasi = "REBALANCE / TRIM POSISI"
    elif deviasi < -2:
        rekomendasi = "TAMBAH SAHAM"
    else:
        rekomendasi = "TAHAN / REBALANCE RINGAN"

    # ===== OUTPUT =====
    output = ""
    output += "~" * 50 + "\n"
    output += "GANDA DASHBOARD INVESTASI".center(50) + "\n"
    output += "~" * 50 + "\n\n"

    output += f"Analisa dijalankan  : {now_str} WIB\n"
    output += "." * 50 + "\n"
    output += f"IHSG Terakhir       : {ihsg:>10,.2f}\n"
    output += f"GDP Indonesia       : ${GDP/1e12:>5.2f} T\n"
    output += f"Market Cap IDX      : ${MCAP/1e12:>5.2f} T\n"
    output += f"Buffett Indicator   : {buffett:>6.2f}%\n"
    output += f"Kondisi Pasar       : {kondisi_pasar}\n\n"

    output += f"Target Saham (Buffett) : {target_saham:.2f}%\n"
    output += f"Target Cash (Buffett)  : {target_cash:.2f}%\n\n"
    output += f"Real Saham             : {real_saham_pct:.2f}%\n"
    output += f"Real Cash              : {real_cash_pct:.2f}%\n"
    output += f"Deviasi vs Target      : {deviasi:+.2f}%\n"
    output += f"Rekomendasi Aksi       : {rekomendasi}\n"

    output += "\n" + "." * 50 + "\n"
    output += f"Total Saham         : {rupiah(total_now)}\n"
    output += f"Cash                : {rupiah(cash)}\n"
    output += f"Total Equity        : {rupiah(total_equity)}\n"

    output += "\nPORTFOLIO SUMMARY\n"
    output += "==================\n\n"

    for _, r in df.iterrows():

        bobot = r["Nilai Now"] / total_now * 100 if total_now else 0
        sign = "+" if r["Gain"] >= 0 else "-"
        gain_pct = abs(r["Gain %"])

        output += f"{r['Kode']:<6}{r['Lot']:>5} lot   Avg {r['Avg']:>7,.0f}\n"
        output += f"{'':11}Last {r['Last']:>7,.0f}\n"
        output += f"{'':11}Value {rupiah(r['Nilai Now'])} ({bobot:.2f}%)\n"
        output += f"{'':11}Unrealized {sign}{rupiah(abs(r['Gain']))} ({sign}{gain_pct:.2f}%)\n\n"

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
                kirim_pesan(chat_id, build_dashboard())

    except Exception as e:
        print("Error:", e)

    time.sleep(1)
