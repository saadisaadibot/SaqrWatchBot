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

MONITOR_DURATION = 15
MONITOR_INTERVAL = 30
REFRESH_INTERVAL = 1800  # كل 30 دقيقة إعادة تقييم

def send_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg})
    except: pass

def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

def bitvavo_request(path):
    ts = str(int(time.time() * 1000))
    msg = ts + "GET" + path
    sig = hmac.new(BITVAVO_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {
        'Bitvavo-Access-Key': BITVAVO_API_KEY,
        'Bitvavo-Access-Signature': sig,
        'Bitvavo-Access-Timestamp': ts,
        'Bitvavo-Access-Window': '10000'
    }
    try:
        res = requests.get("https://api.bitvavo.com" + path, headers=headers)
        return res.json()
    except:
        return []

def get_candles(symbol):
    return bitvavo_request(f"/v2/market/{symbol}/candles?interval=1m&limit=3")

def evaluate_symbol(symbol):
    candles = get_candles(symbol)
    if not candles or len(candles) < 2:
        return 0
    score = 0
    vols = []
    bodies = []
    for c in candles[:-1]:
        o, h, l, close, vol = map(float, c)
        vols.append(vol)
        bodies.append(abs(close - o))

    avg_vol = sum(vols) / len(vols) if vols else 0.0001
    avg_body = sum(bodies) / len(bodies) if bodies else 0.0001

    last = candles[-1]
    o, h, l, close, vol = map(float, last)

    if close > o * 1.003: score += 1  # momentum
    if abs(close - o) > avg_body: score += 1  # candle body
    if vol > avg_vol * 1.5: score += 1  # volume spike

    return score

def monitor(symbol):
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat()
    }))

def refresh_top_symbols():
    tickers = bitvavo_request("/v2/ticker/price")
    scores = []
    for t in tickers:
        try:
            symbol = t["market"]
            price = float(t["price"])
            if not symbol.endswith("-EUR") or price < 0.005:
                continue
            score = evaluate_symbol(symbol)
            if score > 0:
                scores.append((symbol, score))
        except:
            continue
    scores.sort(key=lambda x: x[1], reverse=True)
    top = scores[:100]
    r.delete("watching")
    for sym, _ in top:
        monitor(sym)

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

            candles = get_candles(symbol)
            if not candles or len(candles) < 2:
                continue
            current = float(candles[-1][4])
            for c in candles[:-1]:
                prev = float(c[4])
                if prev == 0: continue
                change = ((current - prev) / prev) * 100
                if change >= 1.5:
                    send_buy_to_toto(symbol.split("-")[0])
                    r.hdel("watching", symbol)
                    break

            minutes = (now - start).total_seconds() / 60
            if minutes >= MONITOR_DURATION:
                r.hdel("watching", symbol)
        time.sleep(MONITOR_INTERVAL)

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
    return "🤖 KOKO INTEL MODE™ جاهز للصيد", 200

def scheduler():
    while True:
        refresh_top_symbols()
        time.sleep(REFRESH_INTERVAL)

def start():
    r.flushall()
    threading.Thread(target=watch_checker).start()
    threading.Thread(target=scheduler).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)