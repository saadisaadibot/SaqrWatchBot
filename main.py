import os
import time
import json
import requests
import redis
from datetime import datetime
from flask import Flask, request
import threading

# إعداد التطبيق
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# إرسال رسالة لتوتو فقط
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except:
        pass

# جلب كل رموز EUR
def get_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return [m["market"] for m in res.json() if m["market"].endswith("-EUR")]
    except:
        return []

# جلب بيانات السوق
def get_ticker(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/24h?market={symbol}"
        res = requests.get(url)
        data = res.json()
        return {
            "price": float(data["last"]),
            "volume": float(data["volume"]),
            "symbol": symbol,
            "time": datetime.utcnow().isoformat()
        }
    except:
        return None

# حفظ التاريخ
def store(symbol, data):
    key = f"hist:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 3)

# تحليل إشارات 3 شمعات خضراء فقط
def is_three_green(symbol):
    raw = r.lrange(f"hist:{symbol}", 0, 3)
    if len(raw) < 3:
        return False
    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    return prices[0] > prices[1] > prices[2]

# المراقبة
def monitor_loop():
    while True:
        symbols = get_symbols()
        for symbol in symbols:
            try:
                data = get_ticker(symbol)
                if not data:
                    continue
                store(symbol, data)
                if r.hexists("watching", symbol):
                    continue
                if is_three_green(symbol):
                    r.hset("watching", symbol, datetime.utcnow().isoformat())
                    r.set(f"entry:{symbol}", data["price"])
            except:
                continue
        time.sleep(180)  # كل 3 دقائق

# التحقق من الشراء
def watch_checker():
    while True:
        try:
            now = datetime.utcnow()
            watching = r.hgetall("watching")
            for symbol_b, time_b in watching.items():
                symbol = symbol_b.decode()
                t0 = datetime.fromisoformat(time_b.decode())
                mins = (now - t0).total_seconds() / 60
                entry = float(r.get(f"entry:{symbol}") or 0)
                current = get_ticker(symbol)
                if not current:
                    continue
                price_now = current["price"]
                change = ((price_now - entry) / entry) * 100
                coin = symbol.split("-")[0].upper()
                if change >= 2:
                    send_buy_to_toto(coin)
                    r.hdel("watching", symbol)
                    r.delete(f"entry:{symbol}")
                elif mins >= 15:
                    r.hdel("watching", symbol)
                    r.delete(f"entry:{symbol}")
        except:
            pass
        time.sleep(60)

# Webhook
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])
        if chat_id != CHAT_ID:
            return "ok"

        if text == "شو عم تعمل":
            lines = []
            now = datetime.utcnow()
            watching = r.hgetall("watching")
            for symbol_b, time_b in watching.items():
                symbol = symbol_b.decode()
                t0 = datetime.fromisoformat(time_b.decode())
                left = 15 - int((now - t0).total_seconds() // 60)
                lines.append(f"• تتم مراقبة {symbol.split('-')[0]}، باقي {left} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة"
            try:
                requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
            except:
                pass
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "✅ Koko يعمل بهدوء", 200

# بدء التشغيل
def start():
    threading.Thread(target=monitor_loop).start()
    threading.Thread(target=watch_checker).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)