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
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# === إرسال رسالة تيليغرام
def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# === إرسال أمر الشراء لتوتو
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
        send_message(f"📤 {msg}")
    except Exception as e:
        print(f"❌ فشل إرسال الأمر إلى توتو: {e}")

# === جلب كل رموز -EUR
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

# === تخزين التاريخ
def store_data(symbol, data):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 20)
    r.incr(f"counter:{symbol.split('-')[0]}", amount=1)

# === تحليل سريع
def analyze(symbol):
    raw = r.lrange(f"history:{symbol}", 0, 5)
    if len(raw) < 4:
        return None
    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    volumes = [e["volume"] for e in entries]
    p_now, p1, p2, p3 = prices[0], prices[1], prices[2], prices[3]

    if ((p_now - p3) / p3) * 100 >= 2:
        return "🚀 صعود 2% خلال 3 دقائق"
    if ((p_now - p1) / p1) * 100 >= 0.8:
        return "📈 صعود 0.8% بدقيقة"
    if p_now > p1 > p2 > p3:
        return "🟩 3 شمعات خضراء"
    if volumes[0] > volumes[1] * 1.5:
        return "💥 تضخم بالحجم"
    return None

# === المراقبة الذكية
def monitor_loop():
    symbols = get_symbols()
    send_message(f"🤖 كوكو يراقب {len(symbols)} عملة 🔍")

    while True:
        for symbol in symbols:
            try:
                data = get_ticker(symbol)
                if not data:
                    continue
                store_data(symbol, data)

                # لا تحليل إذا العملة تحت المراقبة حاليًا
                if r.exists(f"watch:{symbol}"):
                    continue

                signal = analyze(symbol)
                if signal:
                    # راقب العملة سرًا لـ15 دقيقة
                    r.hset("watching", symbol, datetime.utcnow().isoformat())
                    r.set(f"entry:{symbol}", data["price"])
                    r.expire(f"watching:{symbol}", 1000)
                    print(f"🕵️‍♂️ بدأنا نراقب {symbol}: {signal}")

            except Exception as e:
                print(f"❌ {symbol} failed: {e}")
        time.sleep(180)

# === فحص العملات المراقبة
def watch_checker():
    while True:
        try:
            watching = r.hgetall("watching")
            now = datetime.utcnow()

            for symbol_b, start_time_b in watching.items():
                symbol = symbol_b.decode()
                start_time = datetime.fromisoformat(start_time_b.decode())
                minutes_passed = (now - start_time).total_seconds() // 60

                if minutes_passed >= 15:
                    entry = float(r.get(f"entry:{symbol}") or 0)
                    current = get_ticker(symbol)
                    if not current:
                        continue
                    change = ((current["price"] - entry) / entry) * 100
                    coin = symbol.split("-")[0].upper()
                    if change >= 2:
                        send_buy_to_toto(coin)
                    r.hdel("watching", symbol)
                    r.delete(f"entry:{symbol}")

        except Exception as e:
            print("❌ watch_checker error:", str(e))

        time.sleep(60)

# === Webhook تيليغرام
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])

        if chat_id != CHAT_ID:
            return "ok"

        if text == "شو عم تعمل":
            watching = r.hgetall("watching")
            lines = []
            now = datetime.utcnow()
            for symbol_b, time_b in watching.items():
                symbol = symbol_b.decode()
                t = datetime.fromisoformat(time_b.decode())
                mins = int((now - t).total_seconds() // 60)
                lines.append(f"• تتم مراقبة {symbol.split('-')[0]}، باقي {15 - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة"
            send_message(msg)

        elif text == "الملخص":
            keys = r.keys("counter:*")
            lines = [f"{k.decode().split(':')[1]} = {int(r.get(k))} مرة" for k in keys]
            msg = "📊 عدد مرات المراقبة:\n" + "\n".join(lines) if lines else "🚫 لا يوجد أي سجل."
            send_message(msg)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🚀 Koko is alive", 200

# === التشغيل
def start():
    send_message("✅ كوكو بدأ التشغيل... استعد يا توتو!")
    threading.Thread(target=monitor_loop).start()
    threading.Thread(target=watch_checker).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)