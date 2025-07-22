import os, time, json, requests
from datetime import datetime
from flask import Flask, request
import redis, threading

# إعداد بيئة التشغيل
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# إعدادات التوقيت
COLLECTION_INTERVAL = 180  # جمع العملات كل 3 دقائق
MONITOR_DURATION = 15      # دقائق
MONITOR_INTERVAL = 30      # تحقق من الصعود كل 30 ثانية

# إرسال رسالة تيليغرام
def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

# إرسال إشارة شراء لتوتو
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا كوكو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

# جلب بيانات كل العملات
def get_all_tickers():
    try:
        return requests.get("https://api.bitvavo.com/v2/ticker/24h").json()
    except:
        return []

# جلب السعر الحالي لعملة
def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except:
        return None

# بدء مراقبة عملة
def monitor(symbol):
    entry = get_price(symbol)
    if not entry:
        return
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat(),
        "entry": entry
    }))

# فحص العملات تحت المراقبة
def watch_checker():
    while True:
        now = datetime.utcnow()
        watching = r.hgetall("watching")
        for symbol_b, data_b in watching.items():
            symbol = symbol_b.decode()
            try:
                data = json.loads(data_b.decode())
                start = datetime.fromisoformat(data["start"])
                entry = data["entry"]
            except:
                r.hdel("watching", symbol)
                continue

            price = get_price(symbol)
            if not price:
                continue

            change = ((price - entry) / entry) * 100
            minutes = (now - start).total_seconds() / 60

            if change >= 2:
                send_buy_to_toto(symbol.split("-")[0])
                r.hdel("watching", symbol)
            elif minutes >= MONITOR_DURATION:
                r.hdel("watching", symbol)
        time.sleep(MONITOR_INTERVAL)

# جمع العملات المؤهلة كل 3 دقائق
def collector():
    while True:
        tickers = get_all_tickers()
        for t in tickers:
            try:
                symbol = t["market"]
                vol = float(t["volume"])
                change = float(t.get("priceChangePercentage", 0))
                if not symbol.endswith("-EUR"):
                    continue
                if r.hexists("watching", symbol):
                    continue
                if vol >= 5000 and change >= 1.2:
                    monitor(symbol)
            except:
                continue
        time.sleep(COLLECTION_INTERVAL)

# عرض العملات تحت المراقبة
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])
        if chat_id != CHAT_ID:
            return "ok"
        if "شو عم تعمل" in text:
            now = datetime.utcnow()
            watching = r.hgetall("watching")
            lines = []
            for symbol_b, data_b in watching.items():
                symbol = symbol_b.decode()
                try:
                    data = json.loads(data_b.decode())
                    start = datetime.fromisoformat(data["start"])
                    mins = int((now - start).total_seconds() // 60)
                    remaining = max(MONITOR_DURATION - mins, 0)
                    lines.append(f"• {symbol.split('-')[0]} تحت المراقبة، باقي {remaining} دقيقة")
                except:
                    continue
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة حالياً"
            send_message(msg)
    return "ok"

# نقطة الدخول
@app.route("/", methods=["GET"])
def home():
    return "🚀 كوكو الهجين يعمل بثقة...", 200

def start():
    r.flushall()  # تنظيف البيانات السابقة
    send_message("🚀 تم تشغيل كوكو الهجين بثقة...")
    threading.Thread(target=collector).start()
    threading.Thread(target=watch_checker).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)