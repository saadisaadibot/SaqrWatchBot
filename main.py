import os, time, json, requests
from datetime import datetime, timedelta
from flask import Flask, request
import redis, threading

# إعداد البيئة
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
r = redis.from_url(REDIS_URL)

# إعدادات أساسية
watch_duration = 120  # دقائق (ساعتين)
check_interval = 30   # ثواني

# إرسال رسالة تيليغرام
def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

# إرسال أمر شراء لتوتو
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

# جلب كل العملات
def get_all_tickers():
    try:
        return requests.get("https://api.bitvavo.com/v2/ticker/24h").json()
    except: return []

# جلب السعر الحالي
def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except: return None

# بدء مراقبة عملة
def monitor(symbol, kind):
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat(),
        "kind": kind,
        "entry": get_price(symbol)
    }))

# تحقق من التغيير السعري
def check_movement():
    all_watch = r.hgetall("watching")
    now = datetime.utcnow()
    for symbol_b, data_b in all_watch.items():
        symbol = symbol_b.decode()
        try:
            data = json.loads(data_b.decode())
        except: r.hdel("watching", symbol); continue

        entry = data["entry"]
        price = get_price(symbol)
        if not price: continue
        change = ((price - entry) / entry) * 100
        minutes = (now - datetime.fromisoformat(data["start"])).total_seconds() / 60

        if change >= 2:
            send_buy_to_toto(symbol.split("-")[0].upper())
            r.hdel("watching", symbol)
        elif minutes >= watch_duration:
            r.hdel("watching", symbol)

# فلترة العملات المنهارة -7٪ وvol ≥ 5000
def filter_red(tickers):
    result = []
    for t in tickers:
        try:
            pct = float(t["priceChange24h"])
            vol = float(t["volume"])
            if pct <= -7 and vol >= 3000:
                result.append(t["market"])
        except: continue
    return result

# جمع العملات المنهارة + القائمة الذهبية
def red_collector_loop():
    time.sleep(10)  # مهلة بسيطة للبداية
    while True:
        tickers = get_all_tickers()
        reds = filter_red(tickers)

        # القائمة الذهبية
        gold = [s.decode() for s in r.smembers("manual_watchlist")]
        all_targets = list(set(reds + gold))

        for symbol in all_targets:
            if not r.hexists("watching", symbol):
                monitor(symbol, "red")

        time.sleep(900)  # كل 15 دقيقة

# التحقق الدوري من الحركة السعرية
def checker_loop():
    while True:
        check_movement()
        time.sleep(check_interval)

# تيليغرام - أوامر المستخدم
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
            for symbol_b, info_b in watching.items():
                symbol = symbol_b.decode()
                info = json.loads(info_b.decode())
                rem = int(watch_duration - (now - datetime.fromisoformat(info["start"])).total_seconds() / 60)
                lines.append(f"• تتم مراقبة {symbol.split('-')[0]}, باقي {rem} دقيقة")
            msg = "🔍 العملات تحت المراقبة:\n" + ("\n".join(lines) if lines else "لا شيء حاليًا")
            send_message(msg)

        elif text.startswith("اضف "):
            parts = text.split()
            if len(parts) >= 3:
                coin = parts[1].upper()
                full_symbol = f"{coin}-EUR"
                r.sadd("manual_watchlist", full_symbol)
                send_message(f"✨ تمت إضافة {coin} إلى القائمة الذهبية.")
                if not r.hexists("watching", full_symbol):
                    monitor(full_symbol, "gold")

        elif "امسح الذاكرة" in text:
            for key in r.keys("*"):
                r.delete(key)
            send_message("🧹 تم مسح الذاكرة وإعادة التشغيل.")

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "👁️ EyE.KoKo تعمل", 200

def start():
    send_message("🚀 تم تشغيل EyE.KoKo الذكي...")
    threading.Thread(target=red_collector_loop).start()
    threading.Thread(target=checker_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)