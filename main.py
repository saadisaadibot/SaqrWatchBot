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

watch_duration = 60  # مدة المراقبة بالدقائق
check_interval = 30  # فترة التحقق بالثواني

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

def monitor(symbol, kind):
    r.hset("watching", symbol, json.dumps({
        "start": datetime.utcnow().isoformat(),
        "kind": kind,
        "entry": get_price(symbol)
    }))

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

def filter_green(tickers):
    result = []
    for t in tickers:
        try:
            open_price = float(t["open"])
            last_price = float(t["last"])
            pct = ((last_price - open_price) / open_price) * 100
            vol = float(t["volume"])
            if pct > 0.5 and vol > 3000:
                result.append(t["market"])
        except: continue
    return result

def filter_red(tickers):
    result = []
    for t in tickers:
        try:
            open_price = float(t["open"])
            last_price = float(t["last"])
            pct = ((last_price - open_price) / open_price) * 100
            vol = float(t["volume"])
            if pct <= -10 and vol > 3000:
                result.append(t["market"])
        except: continue
    return result

def green_collector_loop():
    while True:
        tickers = get_all_tickers()
        greens = filter_green(tickers)
        for symbol in greens:
            if not r.hexists("watching", symbol):
                monitor(symbol, "green")
        time.sleep(900)  # كل 15 دقيقة

def red_collector_loop():
    time.sleep(300)  # تأخير 5 دقائق عند البداية
    while True:
        tickers = get_all_tickers()
        reds = filter_red(tickers)
        for symbol in reds:
            if not r.hexists("watching", symbol):
                monitor(symbol, "red")
        time.sleep(900)  # كل 15 دقيقة

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
            greens, reds = [], []
            for symbol_b, info_b in r.hgetall("watching").items():
                symbol = symbol_b.decode()
                info = json.loads(info_b.decode())
                rem = int(watch_duration - (now - datetime.fromisoformat(info["start"])).total_seconds() / 60)
                line = f"• تتم مراقبة {symbol.split('-')[0]}, باقي {rem} دقيقة"
                if info["kind"] == "green": greens.append(line)
                else: reds.append(line)
            msg = "🟩 العملات القوية:\n" + "\n".join(greens) if greens else "🟩 لا شيء"
            msg += "\n\n🔻 العملات المنهارة:\n" + "\n".join(reds) if reds else "\n🔻 لا شيء"
            send_message(msg)

        elif "امسح الذاكرة" in text:
            for key in r.keys("*"): r.delete(key)
            send_message("🧹 تم مسح الذاكرة وإعادة التشغيل.")

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "👁️ EyE.KoKo تعمل", 200

def start():
    send_message("🚀 تم تشغيل EyE.KoKo الذكي...")
    threading.Thread(target=green_collector_loop).start()
    threading.Thread(target=red_collector_loop).start()
    threading.Thread(target=checker_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)