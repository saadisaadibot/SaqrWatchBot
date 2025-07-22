import os, time, json, requests
from datetime import datetime
from flask import Flask, request
import redis, threading

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

COLLECTION_INTERVAL = 180
MONITOR_DURATION = 15
MONITOR_INTERVAL = 30

def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا كوكو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

def get_all_tickers():
    try:
        return requests.get("https://api.bitvavo.com/v2/ticker/24h").json()
    except:
        return []

def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except:
        return None

def monitor(symbol):
    entry = get_price(symbol)
    if not entry:
        return
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat(),
        "entry": entry,
        "prices": [{"price": entry, "time": datetime.utcnow().isoformat()}]
    }))

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
                prices = data.get("prices", [])
            except:
                r.hdel("watching", symbol)
                continue

            current_price = get_price(symbol)
            if not current_price:
                continue

            # تحديث سجل الأسعار
            prices.append({"price": current_price, "time": now.isoformat()})
            prices = [p for p in prices if (now - datetime.fromisoformat(p["time"])).total_seconds() <= 120]

            # فحص الارتفاع خلال دقيقة أو دقيقتين
            for p in prices:
                diff = ((current_price - p["price"]) / p["price"]) * 100
                duration = (now - datetime.fromisoformat(p["time"])).total_seconds()
                if diff >= 1.5 and duration <= 120:
                    send_buy_to_toto(symbol.split("-")[0])
                    r.hdel("watching", symbol)
                    break

            minutes = (now - start).total_seconds() / 60
            if minutes >= MONITOR_DURATION:
                r.hdel("watching", symbol)
            else:
                data["prices"] = prices
                r.hset("watching", symbol, json.dumps(data))
        time.sleep(MONITOR_INTERVAL)

def collector():
    while True:
        tickers = get_all_tickers()
        for t in tickers:
            try:
                symbol = t["market"]
                vol = float(t["volume"])
                if not symbol.endswith("-EUR"):
                    continue
                if r.hexists("watching", symbol):
                    continue
                open_price = float(t["open"])
                last_price = float(t["last"])
                if vol >= 5000:
                    monitor(symbol)
            except:
                continue
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
            now = datetime.utcnow()
            watching = r.hgetall("watching")
            lines = []
            for symbol_b, data_b in watching.items():
                symbol = symbol_b.decode()
                data = json.loads(data_b.decode())
                mins = int((now - datetime.fromisoformat(data["start"])).total_seconds() // 60)
                lines.append(f"• {symbol.split('-')[0]} تحت المراقبة، باقي {MONITOR_DURATION - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة حالياً"
            send_message(msg)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🚀 كوكو الهجين يعمل بثقة...", 200

def start():
    r.flushall()
    send_message("🚀 تم تشغيل كوكو الهجين بثقة...")
    threading.Thread(target=collector).start()
    threading.Thread(target=watch_checker).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)