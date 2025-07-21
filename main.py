import os
import time
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, request
import redis
import threading

# === إعداد التطبيق ===
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
r = redis.from_url(REDIS_URL)

# === الإرسال إلى تيليغرام ===
def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# === جلب رموز EUR من Bitvavo ===
def get_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return [item["market"] for item in res.json() if item["market"].endswith("-EUR")]
    except:
        return []

# === جلب بيانات العملة ===
def get_ticker(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol}/ticker/24h"
        res = requests.get(url)
        data = res.json()
        return {
            "symbol": symbol,
            "price": float(data["last"]),
            "volume": float(data["volume"]),
            "time": datetime.utcnow().isoformat()
        }
    except:
        return None

# === تخزين البيانات الزمنية لكل عملة ===
def store_data(symbol, data):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 20)

# === التحليل الذكي على نمط صقر ===
def analyze(symbol):
    key = f"history:{symbol}"
    raw = r.lrange(key, 0, 5)
    if len(raw) < 4:
        return None

    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    volumes = [e["volume"] for e in entries]

    # إشارة ارتداد بعد هبوط
    change = ((prices[0] - prices[-1]) / prices[-1]) * 100
    stable = max(prices[-3:]) - min(prices[-3:]) < 0.003
    vol_jump = (volumes[0] - volumes[-1]) / volumes[-1] * 100 if volumes[-1] else 0

    if change > 5 and stable and vol_jump > 10:
        return f"📉 إشارة من صقر:\nعملة {symbol} هبطت {change:.2f}٪ ثم استقرت.\nحجم التداول ارتفع {vol_jump:.2f}٪.\nقد يبدأ الارتداد الآن."

    # إشارة انفجار صعود مفاجئ
    growth = ((prices[0] - prices[3]) / prices[3]) * 100
    if growth >= 5:
        return f"🚀 توتو يوصي:\nعملة {symbol} صعدت {growth:.2f}٪ خلال 3 دقائق!\nاحتمال استمرار الصعود."

    return None

# === فحص شامل كل دقيقة ===
def monitor_loop():
    symbols = get_symbols()
    send_message(f"🚀 بدأ المسح الذكي على {len(symbols)} عملة...")

    while True:
        signals = []
        for symbol in symbols:
            data = get_ticker(symbol)
            if data:
                store_data(symbol, data)
                signal = analyze(symbol)
                if signal:
                    signals.append(signal)
        if signals:
            for s in signals:
                send_message(s)
        else:
            print(datetime.utcnow().strftime("%H:%M:%S"), "- لا إشارات حالياً.")
        time.sleep(60)

# === Webhook للتفاعل مع البوت ===
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])

        if chat_id != CHAT_ID:
            return "ok"

        if text == "شو عم تعمل":
            active = r.keys("history:*")
            msg = f"📊 تتم المراقبة على {len(active)} عملة حالياً."
            send_message(msg)

        elif text == "الملخص":
            counters = r.keys("history:*")
            msg = "📁 الملخص:\n"
            for key in counters:
                sym = key.decode().split(":")[1]
                count = r.llen(key)
                msg += f"{sym} = {count} سجل\n"
            send_message(msg)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot is running 🚀", 200

# === تشغيل البوت ===
def start():
    send_message("🧠 توتو الهجين بدأ التشغيل!\nكل دقيقة يتم تحليل السوق...")
    threading.Thread(target=monitor_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)