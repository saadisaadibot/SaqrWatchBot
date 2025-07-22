import os, time, json, requests, hmac, hashlib
from datetime import datetime
from flask import Flask, request
import redis, threading

# إعداد Flask وبيئة التشغيل
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
REFRESH_INTERVAL = 1800  # كل نصف ساعة
MONITOR_INTERVAL = 30
MONITOR_DURATION = 15

### أدوات المساعد ###
def send_message(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
    except: pass

def send_buy_to_toto(symbol):
    msg = f"🚀 اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

def bitvavo_request(path):
    timestamp = str(int(time.time() * 1000))
    msg = timestamp + "GET" + path
    signature = hmac.new(BITVAVO_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {
        'Bitvavo-Access-Key': BITVAVO_API_KEY,
        'Bitvavo-Access-Signature': signature,
        'Bitvavo-Access-Timestamp': timestamp,
        'Bitvavo-Access-Window': '10000'
    }
    try:
        res = requests.get("https://api.bitvavo.com" + path, headers=headers)
        return res.json()
    except:
        return []

def get_last_candles(symbol):
    path = f"/v2/market/{symbol}/candles?interval=1m&limit=3"
    return bitvavo_request(path)

def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except:
        return None

### الذكاء الاصطناعي لاختيار العملات ###
def select_top_100():
    tickers = bitvavo_request("/v2/ticker/price")
    selected = []
    for t in tickers:
        try:
            symbol = t["market"]
            price = float(t["price"])
            if not symbol.endswith("-EUR") or price < 0.005:
                continue
            candles = get_last_candles(symbol)
            if not candles or len(candles) < 2:
                continue
            latest = candles[-1][4]
            past = candles[0][4]
            change = ((latest - past) / past) * 100
            score = change + (price * 100)  # نمط مبسط للتقييم
            selected.append((symbol, score))
        except:
            continue
    selected.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in selected[:100]]

### مراقبة العملات ###
def monitor(symbol):
    r.hset("watching", symbol, json.dumps({"start": datetime.utcnow().isoformat()}))

def watcher():
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
            current = candles[-1][4]
            for c in candles[:-1]:
                past = c[4]
                if past == 0: continue
                diff = ((current - past) / past) * 100
                if diff >= 1.5:
                    send_buy_to_toto(symbol.split("-")[0])
                    send_message(f"🚨 إشارة شراء لـ {symbol.split('-')[0]} - ارتفعت {diff:.2f}% خلال دقائق")
                    r.hdel("watching", symbol)
                    break

            minutes = (now - start).total_seconds() / 60
            if minutes >= MONITOR_DURATION:
                r.hdel("watching", symbol)
        time.sleep(MONITOR_INTERVAL)

### جامع العملات الذكي ###
def scheduler():
    while True:
        top = select_top_100()
        r.delete("watching")  # نمسح القائمة القديمة
        for symbol in top:
            monitor(symbol)
        time.sleep(REFRESH_INTERVAL)

### بوت تيليغرام ###
@app.route("/", methods=["POST"])
def telegram_webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])
        if chat_id != CHAT_ID:
            return "ok"
        if "شو عم تعمل" in text:
            watching = r.hgetall("watching")
            now = datetime.utcnow()
            lines = []
            for i, (symbol_b, data_b) in enumerate(watching.items(), start=1):
                symbol = symbol_b.decode()
                data = json.loads(data_b.decode())
                mins = int((now - datetime.fromisoformat(data["start"])).total_seconds() // 60)
                lines.append(f"{i}. {symbol.split('-')[0]} تحت المراقبة، باقي {MONITOR_DURATION - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة حالياً"
            send_message(msg)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🧠 KOKO INTEL MODE™ يعمل بلا رحمة", 200

### بدء التشغيل ###
def start():
    r.flushall()
    send_message("🤖 تم تشغيل KOKO INTEL MODE™ - تمت تصفية الذاكرة والانطلاق ✅")
    threading.Thread(target=watcher).start()
    threading.Thread(target=scheduler).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)