import os, time, json, requests
from datetime import datetime, timedelta
from flask import Flask, request
import redis, threading

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
r = redis.from_url(REDIS_URL)

def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

def get_all_tickers():
    try:
        url = "https://api.bitvavo.com/v2/ticker/24h"
        return requests.get(url).json()
    except: return []

def monitor(symbol, kind):
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat(),
        "kind": kind,
        "entry": get_price(symbol)
    }))

def get_price(symbol):
    try:
        res = requests.get(f"https://api.bitvavo.com/v2/ticker/price?market={symbol}")
        return float(res.json()["price"])
    except: return None

def check_movement():
    all_watch = r.hgetall("watching")
    now = datetime.utcnow()
    for symbol_b, data_b in all_watch.items():
        symbol = symbol_b.decode()
        data = json.loads(data_b.decode())
        entry = data["entry"]
        price = get_price(symbol)
        if not price: continue
        change = ((price - entry) / entry) * 100
        minutes = (now - datetime.fromisoformat(data["start"])).total_seconds() / 60

        if change >= 2:
            send_buy_to_toto(symbol.split("-")[0].upper())
            r.hdel("watching", symbol)
        elif minutes >= 60:
            r.hdel("watching", symbol)

def top_green(tickers):
    result = []
    for t in tickers:
        try:
            pct = float(t["priceChangePercentage"])
            vol = float(t["volume"])
            if pct > 3 and vol > 10000 and t["market"].endswith("-EUR"):
                result.append((t["market"], pct))
        except: continue
    return sorted(result, key=lambda x: -x[1])[:7]

def top_red(tickers):
    result = []
    for t in tickers:
        try:
            pct = float(t["priceChangePercentage"])
            vol = float(t["volume"])
            if pct <= -15 and vol > 10000 and t["market"].endswith("-EUR"):
                result.append((t["market"], pct))
        except: continue
    return sorted(result, key=lambda x: x[1])[:7]

def green_loop():
    while True:
        tickers = get_all_tickers()
        top = top_green(tickers)
        for symbol, _ in top:
            if not r.hexists("watching", symbol):
                monitor(symbol, "green")
        time.sleep(300)

def red_loop():
    while True:
        tickers = get_all_tickers()
        top = top_red(tickers)
        for symbol, _ in top:
            if not r.hexists("watching", symbol):
                monitor(symbol, "red")
        time.sleep(600)

def checker_loop():
    while True:
        check_movement()
        time.sleep(30)

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])
        if chat_id != CHAT_ID:
            return "ok"

        if "شو عم تعمل" in text:
            w = r.hgetall("watching")
            now = datetime.utcnow()
            greens, reds = [], []
            for symbol_b, info_b in w.items():
                symbol = symbol_b.decode()
                info = json.loads(info_b.decode())
                t = datetime.fromisoformat(info["start"])
                rem = int(60 - (now - t).total_seconds() // 60)
                name = f"{symbol.split('-')[0]}"
                line = f"• تتم مراقبة {name}، باقي {rem} دقيقة"
                if info["kind"] == "green": greens.append(line)
                else: reds.append(line)
            msg = "🟩 العملات القوية:\n" + "\n".join(greens) if greens else "🟩 لا شيء"
            msg += "\n\n🔻 العملات المنهارة:\n" + "\n".join(reds) if reds else "\n🔻 لا شيء"
            send_message(msg)

        elif "امسح الذاكرة" in text:
            r.delete("watching")
            send_message("🧹 تم مسح المراقبة وإعادة التشغيل.")

    return "ok"

@app.route("/", methods=["GET"])
def home(): return "👁️ عين كوكو تعمل", 200

def start():
    send_message("🚀 تم تشغيل عين كوكو المطوّرة...")
    threading.Thread(target=green_loop).start()
    threading.Thread(target=red_loop).start()
    threading.Thread(target=checker_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)