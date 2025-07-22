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

def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except Exception as e:
        print(f"❌ فشل الإرسال إلى توتو: {e}")

def get_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return [m["market"] for m in res.json() if m["market"].endswith("-EUR")]
    except:
        return []

def get_ticker(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/24h?market={symbol}"
        res = requests.get(url)
        data = res.json()
        return {
            "price": float(data["last"]),
            "volume": float(data["volume"]),
            "time": datetime.utcnow().isoformat()
        }
    except:
        return None

def store_data(symbol, data):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 5)

def detect_3_green_candles(symbol):
    raw = r.lrange(f"history:{symbol}", 0, 3)
    if len(raw) < 3:
        return False
    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    return prices[0] > prices[1] > prices[2]

def monitor_loop():
    while True:
        symbols = get_symbols()
        for symbol in symbols:
            try:
                data = get_ticker(symbol)
                if not data:
                    continue
                store_data(symbol, data)

                if r.hexists("watching", symbol):
                    continue

                if detect_3_green_candles(symbol):
                    r.hset("watching", symbol, datetime.utcnow().isoformat())
                    r.set(f"entry:{symbol}", data["price"])
                    print(f"🕵️‍♂️ مراقبة {symbol} بدأت بعد 3 شمعات خضراء")

            except Exception as e:
                print(f"❌ {symbol} failed: {e}")
        time.sleep(180)

def watch_checker():
    while True:
        try:
            watching = r.hgetall("watching")
            now = datetime.utcnow()

            for symbol_b, time_b in watching.items():
                symbol = symbol_b.decode()
                t = datetime.fromisoformat(time_b.decode())
                minutes = (now - t).total_seconds() / 60

                entry = float(r.get(f"entry:{symbol}") or 0)
                current = get_ticker(symbol)
                if not current:
                    continue

                change = ((current["price"] - entry) / entry) * 100
                if change >= 2:
                    send_buy_to_toto(symbol.split("-")[0].upper())
                    r.hdel("watching", symbol)
                    r.delete(f"entry:{symbol}")
                elif minutes >= 15:
                    r.hdel("watching", symbol)
                    r.delete(f"entry:{symbol}")

        except Exception as e:
            print("❌ watch_checker error:", str(e))
        time.sleep(60)

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])
        if chat_id != CHAT_ID:
            return "ok"

        if text == "شو عم تعمل":
            watching = r.hgetall("watching")
            now = datetime.utcnow()
            lines = []
            for symbol_b, t_b in watching.items():
                symbol = symbol_b.decode()
                t = datetime.fromisoformat(t_b.decode())
                mins = int((now - t).total_seconds() // 60)
                lines.append(f"• تتم مراقبة {symbol.split('-')[0]}، باقي {15 - mins} دقيقة")
            msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة"
            send_message(msg)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🚀 Koko is alive", 200

def start():
    threading.Thread(target=monitor_loop).start()
    threading.Thread(target=watch_checker).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)