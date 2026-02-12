import requests
import time
import os

TOKEN = os.getenv("TOKEN")
URL = f"https://api.telegram.org/bot{TOKEN}"


last_update_id = None

def kirim_pesan(chat_id, text):
    requests.get(f"{URL}/sendMessage?chat_id={chat_id}&text={text}")

def ambil_update(offset=None):
    if offset:
        return requests.get(f"{URL}/getUpdates?offset={offset}").json()
    return requests.get(f"{URL}/getUpdates").json()

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

            if text == "/start":
                kirim_pesan(chat_id,
"""Selamat datang 🤖

Saya bot analisa saham.

Perintah tersedia:
/halo
/help
""")

            elif text == "/halo":
                kirim_pesan(chat_id, "Halo juga 👋")

            elif text == "/help":
                kirim_pesan(chat_id,
"""Gunakan perintah:

/halo - test bot
/start - mulai bot
/help - bantuan
""")

    except Exception as e:
        print("Error:", e)

    time.sleep(1)
