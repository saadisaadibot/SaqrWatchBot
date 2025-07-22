import os, time, json, requests, hmac, hashlib
from datetime import datetime
from flask import Flask, request
import redis, threading

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")
PORT = int(os.getenv("PORT", 5000))
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

COLLECTION_INTERVAL = 1800  # كل 30 دقيقة
MONITOR_DURATION = 15
MONITOR_INTERVAL = 30

def send_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

# توقيع طلب Bitvavo
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
        res = requests.get("https://api.bitvavo.com" + path, headers=headers)
        return res.json()
    except:
        return []

# بيانات آخر 3 شموع
def get_last_3m_candles(symbol):
    return bitvavo_request(f"/v2/market/{symbol}/candles?interval=1m&limit=3")

def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except:
        return None

# التقييم الذكي للعملات
def evaluate_symbol(symbol):
    candles = get_last_3m_candles(symbol)
    if not candles or len(candles) < 3:
        return 0

    score = 0
    vol_jump = False
    prev_close = candles[0][4]
    for i in range(1, len(candles)):
        close = candles[i][4]
        vol = candles[i][5]
        if prev_close == 0:
            continue
        change = ((close - prev_close) / prev_close) * 100
        if change > 0.4:
            score += change
        if vol > 1000:
            score += 1
        prev_close = close
    return score

# تحديث قائمة المراقبة
def refresh_top_symbols():
    r.delete("watching")
    tickers = bitvavo_request("/v2/ticker/price")
    candidates = []
    for t in tickers:
        try:
            symbol = t["market"]
            price = float(t["price"])
            if not symbol.endswith("-EUR") or price < 0.005:
                continue
            score = evaluate_symbol(symbol)
            if score > 0:
                candidates.append((symbol, score))
        except:
            continue
    candidates.sort(key=lambda x: x[1], reverse=True)
    top = candidates[:100]
    for symbol, score in top:
        r.hset("watching", symbol, json.dumps({
            "start": datetime.utcnow().isoformat(),
            "score": score
        }))

# مراقبة العملات المختارة
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

            candles = get_last_3m_candles(symbol)
            if not candles or len(candles) < 2:
                continue
            current_price = candles[-1][4]
            for c in candles[:-1]:
                prev_price = c[4]
                if prev_price == 0:
                    continue
                diff = ((current_price - prev_price) / prev_price) * 100
                if diff >= 1.5:
                    send_buy_to_toto(symbol.split("-")[0])
                    send_message(f"🚀 انفجار {symbol.split('-')[0]} بنسبة {diff:.2f}% خلال دقائق")
                    r.hdel("watching", symbol)
                    break

            if (now - start).total_seconds() / 60 >= MONITOR_DURATION:
                r.hdel("watching", symbol)
        time.sleep(MONITOR_INTERVAL)

# التحديث الدوري كل 30 دقيقة
def scheduler():
    while True:
        refresh_top_symbols()
        time.sleep(COLLECTION_INTERVAL)

@app.route("/", methods=["POST"])
def webhook():
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
                mins = int((now - datetime.fromisoformat(data["start"])).total_seconds() / 60)
                lines.append(f"{i}. {symbol.split('-')[0]} تحت المراقبة، باقي {MONITOR_DURATION - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة حالياً"
            send_message(msg)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🧠 KOKO INTEL MODE™ يعمل بثقة مطلقة", 200

def start():
    r.flushall()
    send_message("🤖 تم تشغيل KOKO INTEL MODE™ - تمت تصفية الذاكرة والانطلاق ✅")
    threading.Thread(target=watch_checker).start()
    threading.Thread(target=scheduler).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)