import os, time, json, requests
from datetime import datetime
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

watch_duration = 60  # بالدقائق
check_interval = 30  # بالثواني

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
        return requests.get("https://api.bitvavo.com/v2/ticker/24h").json()
    except: return []

def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except: return None

def monitor(symbol):
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat(),
        "entry": get_price(symbol)
    }))

def filter_top_red(tickers):
    result = []
    for t in tickers:
        try:
            open_price = float(t["open"])
            last_price = float(t["last"])
            vol = float(t["volume"])
            pct = ((last_price - open_price) / open_price) * 100
            if pct <= -10 and vol >= 5000:
                result.append((t["market"], pct))
        except:
            continue
    return sorted(result, key=lambda x: x[1])[:7]

def red_collector_loop():
    time.sleep(5)  # انتظار مبدئي
    while True:
        tickers = get_all_tickers()
        reds = filter_top_red(tickers)
        for symbol, _ in reds:
            if not r.hexists("watching", symbol):
                monitor(symbol)
        time.sleep(900)  # كل 15 دقيقة

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
            send_buy_to_toto(symbol.split('-')[0].upper())
            r.hdel("watching", symbol)
        elif minutes >= watch_duration:
            r.hdel("watching", symbol)

def checker_loop():
    while True:
        check_movement()
        time.sleep(check_interval)

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
            reds = []
            for symbol_b, info_b in r.hgetall("watching").items():
                symbol = symbol_b.decode()
                info = json.loads(info_b.decode())
                rem = int(watch_duration - (now - datetime.fromisoformat(info["start"])).total_seconds() / 60)
                line = f"• تتم مراقبة {symbol.split('-')[0]}, باقي {rem} دقيقة"
                reds.append(line)
            msg = "🔻 العملات المنهارة:\n" + "\n".join(reds) if reds else "🔻 لا شيء"
            send_message(msg)

        elif "امسح الذاكرة" in text:
            for key in r.keys("*"): r.delete(key)
            send_message("🧹 تم مسح الذاكرة.")

    return "ok"

@app.route("/", methods=["GET"])
def home(): return "👁️ EyE.KoKo (نسخة الهبوط) تعمل", 200

def start():
    send_message("🚀 تم تشغيل EyE.KoKo نسخة العملات المنهارة...")
    threading.Thread(target=red_collector_loop).start()
    threading.Thread(target=checker_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)