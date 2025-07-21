import os
import time
import json
import requests
from datetime import datetime
from flask import Flask
import redis
import threading

# === إعداد التطبيق ===
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
TOTO_WEBHOOK = os.getenv("TOTO_WEBHOOK")
r = redis.from_url(REDIS_URL)

# === إرسال أمر الشراء لتوتو فقط (بدون إشعار)
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except Exception as e:
        print(f"❌ فشل إرسال الأمر إلى توتو: {e}")

# === جلب الرموز
def get_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return [m["market"] for m in res.json() if m["market"].endswith("-EUR")]
    except:
        return []

# === جلب بيانات السوق
def get_ticker(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/24h?market={symbol}"
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

# === حفظ بيانات العملة
def store_data(symbol, data):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 3)

# === تحقق من 3 شمعات خضراء
def is_three_green(symbol):
    raw = r.lrange(f"history:{symbol}", 0, 3)
    if len(raw) < 3:
        return False
    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    return prices[0] > prices[1] > prices[2]

# === حلقة التحليل والشراء
def monitor_loop():
    while True:
        symbols = get_symbols()
        for symbol in symbols:
            try:
                if r.sismember("bought", symbol):
                    continue

                data = get_ticker(symbol)
                if not data:
                    continue
                store_data(symbol, data)

                if is_three_green(symbol):
                    coin = symbol.split("-")[0].upper()
                    send_buy_to_toto(coin)
                    r.sadd("bought", symbol)
                    print(f"✅ تم إرسال شراء {symbol} بسبب 3 شمعات خضراء")

            except Exception as e:
                print(f"❌ {symbol} error: {e}")

        time.sleep(180)

# === نقطة البداية
@app.route("/", methods=["GET"])
def home():
    return "🚀 Koko Green Candles Bot Ready!", 200

def start():
    print("✅ كوكو يعمل بشرط 3 شمعات خضراء فقط...")
    threading.Thread(target=monitor_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)