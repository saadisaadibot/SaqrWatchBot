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

# إعدادات
check_interval = 30  # كل كم ثانية يتم التحقق من العملات تحت المراقبة
collect_interval = 180  # كل كم ثانية يتم جمع العملات الجديدة
watch_duration = 30  # مدة المراقبة بالدقائق

# تنظيف عند التشغيل
for key in r.keys("*"):
    r.delete(key)

def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

def get_top_symbols(limit=100):
    try:
        url = "https://api.bitvavo.com/v2/ticker/24h"
        res = requests.get(url).json()
        sorted_by_vol = sorted(res, key=lambda x: float(x["volume"]), reverse=True)
        return [item["market"] for item in sorted_by_vol if item["market"].endswith("-EUR")][:limit]
    except:
        return []

def get_price(symbol):
    try:
        res = requests.get(f"https://api.bitvavo.com/v2/ticker/price?market={symbol}").json()
        return float(res["price"])
    except:
        return None

def store_data(symbol, price):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps({"price": price, "time": datetime.utcnow().isoformat()}))
    r.ltrim(key, 0, 10)

def detect_conditions(symbol):
    data = r.lrange(f"history:{symbol}", 0, 2)
    if len(data) < 2:
        return False
    try:
        entries = [json.loads(d.decode()) for d in data]
        p0 = entries[0]["price"]
        p1 = entries[1]["price"]
        if p0 > p1:
            return True
    except: pass

    # حركة ≥1.5٪ خلال 3 دقائق
    data = r.lrange(f"history:{symbol}", 0, 3)
    if len(data) >= 2:
        try:
            entries = [json.loads(d.decode()) for d in data]
            oldest = entries[-1]["price"]
            newest = entries[0]["price"]
            change = ((newest - oldest) / oldest) * 100
            if change >= 1.5:
                return True
        except: pass
    return False

def monitor(symbol):
    if not r.hexists("watching", symbol):
        entry_price = get_price(symbol)
        if entry_price:
            r.hset("watching", symbol, json.dumps({
                "start": datetime.utcnow().isoformat(),
                "entry": entry_price
            }))

def collect_loop():
    while True:
        symbols = get_top_symbols()
        for symbol in symbols:
            price = get_price(symbol)
            if price:
                store_data(symbol, price)
                if detect_conditions(symbol) and not r.hexists("watching", symbol):
                    monitor(symbol)
        time.sleep(collect_interval)

def checker_loop():
    while True:
        now = datetime.utcnow()
        for symbol_b, info_b in r.hgetall("watching").items():
            symbol = symbol_b.decode()
            try:
                info = json.loads(info_b.decode())
                start_time = datetime.fromisoformat(info["start"])
                entry = info["entry"]
                current = get_price(symbol)
                if not current:
                    continue
                change = ((current - entry) / entry) * 100
                minutes = (now - start_time).total_seconds() / 60

                if change >= 2:
                    send_buy_to_toto(symbol.split("-")[0].upper())
                    r.hdel("watching", symbol)
                elif minutes >= watch_duration:
                    r.hdel("watching", symbol)
            except:
                r.hdel("watching", symbol)
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
            watching = r.hgetall("watching")
            lines = []
            for symbol_b, info_b in watching.items():
                symbol = symbol_b.decode()
                info = json.loads(info_b.decode())
                rem = int(watch_duration - (now - datetime.fromisoformat(info["start"])).total_seconds() / 60)
                lines.append(f"• {symbol.split('-')[0]}، باقي {rem} دقيقة")
            send_message("\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة")
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "👁️ سكربت كوكو الهجين شغّال", 200

def start():
    send_message("🚀 تم تشغيل كوكو الهجين...")
    threading.Thread(target=collect_loop).start()
    threading.Thread(target=checker_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)