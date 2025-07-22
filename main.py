import os
import time
import json
import requests
from datetime import datetime
from flask import Flask, request
import redis
import threading

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# إعدادات المراقبة
watch_duration = 15   # بالدقائق
check_interval = 30   # ثواني
collect_interval = 180  # ثواني (كل 3 دقائق)

# تنظيف Redis عند التشغيل
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

def get_top100_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/ticker/24h")
        data = res.json()
        sorted_data = sorted(
            [x for x in data if x["market"].endswith("-EUR")],
            key=lambda x: float(x.get("volume", 0)),
            reverse=True
        )
        return [x["market"] for x in sorted_data[:100]]
    except:
        return []

def get_last_3_candles(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol}/candles?interval=1m&limit=3"
        res = requests.get(url)
        return res.json()
    except:
        return []

def has_3_green_candles(candles):
    try:
        if len(candles) < 3:
            return False
        for c in candles:
            if float(c[4]) <= float(c[1]):
                return False
        return True
    except:
        return False

def get_current_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol}/candles?interval=1m&limit=1"
        res = requests.get(url)
        candle = res.json()[0]
        return float(candle[4])
    except:
        return None

def monitor(symbol):
    entry_price = get_current_price(symbol)
    if entry_price:
        r.hset("watching", symbol, json.dumps({
            "start": datetime.utcnow().isoformat(),
            "entry": entry_price
        }))

def check_loop():
    while True:
        try:
            now = datetime.utcnow()
            watching = r.hgetall("watching")
            for symbol_b, data_b in watching.items():
                symbol = symbol_b.decode()
                data = json.loads(data_b.decode())
                start = datetime.fromisoformat(data["start"])
                entry = float(data["entry"])
                mins = (now - start).total_seconds() / 60

                current = get_current_price(symbol)
                if not current:
                    continue
                change = ((current - entry) / entry) * 100

                if change >= 2:
                    send_buy_to_toto(symbol.split("-")[0].upper())
                    r.hdel("watching", symbol)
                elif mins >= watch_duration:
                    r.hdel("watching", symbol)
        except Exception as e:
            print("check_loop error:", str(e))
        time.sleep(check_interval)

def collector_loop():
    while True:
        try:
            symbols = get_top100_symbols()
            for symbol in symbols:
                if r.hexists("watching", symbol):
                    continue
                candles = get_last_3_candles(symbol)
                if has_3_green_candles(candles):
                    monitor(symbol)
        except Exception as e:
            print("collector_loop error:", str(e))
        time.sleep(collect_interval)

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
                mins = int((now - datetime.fromisoformat(data["start"])).total_seconds() / 60)
                lines.append(f"• تتم مراقبة {symbol.split('-')[0]}، باقي {watch_duration - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة"
            send_message(msg)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🧠 KoKo Hybrid يعمل بثقة", 200

def start():
    send_message("🚀 تم تشغيل كوكو الهجين بذكاء عالي.")
    threading.Thread(target=collector_loop).start()
    threading.Thread(target=check_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)