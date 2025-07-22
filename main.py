import os, time, json, requests, hmac, hashlib
from datetime import datetime
from flask import Flask, request
import redis, threading

# إعداد بيئة التشغيل
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")
PORT = int(os.getenv("PORT", 5000))
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# إعدادات التوقيت
COLLECTION_INTERVAL = 1800  # كل 30 دقيقة
MONITOR_DURATION = 30       # دقائق مراقبة
MONITOR_INTERVAL = 30       # كل 30 ثانية

# إرسال رسالة تيليغرام
def send_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

# إرسال إشارة شراء لتوتو
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

# توقيع طلبات Bitvavo
def bitvavo_request(path):
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    msg = timestamp + method + path
    signature = hmac.new(BITVAVO_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {
        'Bitvavo-Access-Key': BITVAVO_API_KEY,
        'Bitvavo-Access-Signature': signature,
        'Bitvavo-Access-Timestamp': timestamp,
        'Bitvavo-Access-Window': '10000'
    }
    try:
        response = requests.get("https://api.bitvavo.com" + path, headers=headers)
        return response.json()
    except:
        return []

# جلب الشموع لتحليل الحركة
def get_last_candles(symbol):
    return bitvavo_request(f"/v2/market/{symbol}/candles?interval=1m&limit=3")

# سكور ذكي للعملة
def get_score(symbol):
    candles = get_last_candles(symbol)
    if not candles or len(candles) < 3:
        return 0

    prices = [c[4] for c in candles]
    volumes = [c[5] for c in candles]

    try:
        change = ((prices[-1] - prices[0]) / prices[0]) * 100
        avg_range = sum([abs(c[2] - c[3]) for c in candles]) / 3
        avg_volume = sum(volumes) / 3
        score = (change * 2) + (avg_range * 100) + (avg_volume / 1000)
        return score
    except:
        return 0

# مراقبة عملة
def monitor(symbol):
    price = get_price(symbol)
    if not price or price < 0.005:
        return
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat()
    }))

# السعر الحالي
def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except:
        return None

# إعادة تقييم السوق واختيار top 100
def evaluate_market():
    tickers = bitvavo_request("/v2/ticker/price")
    scored = []

    for t in tickers:
        try:
            symbol = t["market"]
            if not symbol.endswith("-EUR"):
                continue
            score = get_score(symbol)
            if score > 0:
                scored.append((symbol, score))
        except:
            continue

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:100]

    r.delete("watching")
    for symbol, _ in top:
        monitor(symbol)

# مراقبة العملات
def watch_checker():
    while True:
        now = datetime.utcnow()
        watching = r.hgetall("watching")

        for symbol_b, data_b in watching.items():
            symbol = symbol_b.decode()
            try:
                data = json.loads(data_b.decode())
                start = datetime.fromisoformat(data["start"])
            except:
                r.hdel("watching", symbol)
                continue

            candles = get_last_candles(symbol)
            if not candles or len(candles) < 2:
                continue

            current_price = candles[-1][4]
            for c in candles[:-1]:
                old_price = c[4]
                if old_price == 0:
                    continue
                diff = ((current_price - old_price) / old_price) * 100
                if diff >= 1.5:
                    send_buy_to_toto(symbol.split("-")[0])
                    r.hdel("watching", symbol)
                    break

            minutes = (now - start).total_seconds() / 60
            if minutes >= MONITOR_DURATION:
                r.hdel("watching", symbol)

        time.sleep(MONITOR_INTERVAL)

# تكرار التقييم كل نصف ساعة
def scheduler():
    while True:
        evaluate_market()
        time.sleep(COLLECTION_INTERVAL)

# تيلغرام بوت
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
            for i, (symbol_b, data_b) in enumerate(watching.items(), 1):
                symbol = symbol_b.decode()
                data = json.loads(data_b.decode())
                mins = int((now - datetime.fromisoformat(data["start"])).total_seconds() // 60)
                lines.append(f"{i}. {symbol.split('-')[0]} تحت المراقبة، باقي {MONITOR_DURATION - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة حالياً"
            send_message(msg)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🧠 KOKO SNIPER MODE™ V3 يعمل بلا رحمة", 200

# بدء التشغيل
def start():
    r.flushall()
    threading.Thread(target=scheduler).start()
    threading.Thread(target=watch_checker).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)