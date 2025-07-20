# ملف koko.pro - النسخة المستقرة لمراقبة عملات Bitvavo

import os
import time
import threading
from datetime import datetime, timedelta
import requests
from flask import Flask, request
import redis

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))

BITVAVO_API = "https://api.bitvavo.com/v2"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
r = redis.from_url(REDIS_URL)

eur_markets = []

def send_message(text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
    except:
        print("فشل إرسال رسالة تيليغرام.")

def load_eur_markets():
    try:
        res = requests.get(f"{BITVAVO_API}/markets")
        data = res.json()
        return [item["market"] for item in data if item["market"].endswith("-EUR")]
    except:
        return []

def get_current_price(symbol):
    try:
        res = requests.get(f"{BITVAVO_API}/{symbol}/price")
        return float(res.json()["price"])
    except:
        return None

def get_price_5m_ago(symbol):
    try:
        now = int(time.time() * 1000)
        five_min_ago = now - 5 * 60 * 1000
        url = f"{BITVAVO_API}/{symbol}/candles?interval=1m&start={five_min_ago}&end={now}"
        res = requests.get(url)
        candles = res.json()
        if candles and isinstance(candles, list) and len(candles[0]) >= 2:
            return float(candles[0][1])
    except:
        pass
    return None

def get_top_4_gainers():
    gainers = []
    for symbol in eur_markets:
        old = get_price_5m_ago(symbol)
        current = get_current_price(symbol)
        if old and current and old > 0:
            change = ((current - old) / old) * 100
            gainers.append((symbol, change))
        time.sleep(0.2)
    gainers = sorted(gainers, key=lambda x: x[1], reverse=True)
    return gainers[:4]

def monitor(symbol, start_price):
    start_time = datetime.now()
    r.set(f"monitoring:{symbol}", start_time.isoformat(), ex=300)
    short_symbol = symbol.split("-")[0].lower()
    r.incr(f"counter:{short_symbol}")
    try:
        while (datetime.now() - start_time).total_seconds() < 300:
            current = get_current_price(symbol)
            if current and ((current - start_price) / start_price) >= 0.015:
                send_message(f"🚨 اشترِ {symbol} الآن! ارتفع بنسبة 1.5% خلال المراقبة.")
                break
            time.sleep(60)
    except:
        pass
    r.delete(f"monitoring:{symbol}")

def scanner():
    first_run = True
    while True:
        try:
            top = get_top_4_gainers()
            for symbol, change in top:
                if r.exists(f"monitoring:{symbol}"):
                    continue
                current_price = get_current_price(symbol)
                if current_price:
                    threading.Thread(target=monitor, args=(symbol, current_price)).start()
        except Exception as e:
            print("خطأ أثناء المسح:", e)
        time.sleep(5 if first_run else 300)
        first_run = False

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").strip().lower()
        chat_id = str(data["message"]["chat"]["id"])

        if chat_id != CHAT_ID:
            return "ok"

        if text == "شو عم تعمل":
            keys = r.keys("monitoring:*")
            if not keys:
                send_message("لا تتم مراقبة أي عملة حالياً 👀")
            else:
                lines = ["⌛️ تتم الآن مراقبة:"]
                now = datetime.now()
                for key in keys:
                    symbol = key.decode().split(":")[1]
                    start_str = r.get(key).decode()
                    start_time = datetime.fromisoformat(start_str)
                    mins = int((now - start_time).total_seconds() // 60)
                    short = symbol.split("-")[0].lower()
                    count = r.get(f"counter:{short}")
                    count_str = f"*{int(count)}" if count else ""
                    lines.append(f"• {symbol} منذ {mins} دقيقة {count_str}")
                send_message("\n".join(lines))

        elif text == "الملخص":
            keys = r.keys("counter:*")
            if not keys:
                send_message("لا يوجد سجل مراقبة بعد.")
            else:
                lines = ["📊 سجل المراقبة:"]
                for key in keys:
                    symbol = key.decode().split(":")[1].upper()
                    count = int(r.get(key))
                    lines.append(f"{symbol}: {count} مرة")
                send_message("\n".join(lines))

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot is running ✅", 200

def start_bot():
    global eur_markets
    eur_markets = load_eur_markets()
    send_message("✅ البوت بدأ باستخدام Bitvavo فقط 🔍")
    threading.Thread(target=scanner).start()

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=PORT)