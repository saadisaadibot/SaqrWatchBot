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
    try:
        msg = f"اشتري {symbol} يا توتو"
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
        send_message(f"📤 كوكو أعطى الإشارة:\n{msg}")
    except Exception as e:
        print(f"❌ فشل إرسال الأمر إلى توتو: {e}")

def get_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        symbols = [item["market"] for item in res.json() if item["market"].endswith("-EUR")]
        print(f"📡 تم جلب {len(symbols)} عملة من Bitvavo.")
        return symbols
    except Exception as e:
        print(f"❌ فشل جلب الرموز: {e}")
        return []

def get_ticker(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol}/ticker/24h"
        res = requests.get(url)
        data = res.json()
        return {
            "symbol": symbol,
            "price": float(data["last"]),
            "volume": float(data["volume"]),
            "time": datetime.utcnow().isoformat()
        }
    except Exception as e:
        print(f"❌ فشل جلب بيانات {symbol}: {e}")
        return None

def store_data(symbol, data):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 20)
    r.incr(f"counter:{symbol.split('-')[0]}", amount=1)

def analyze(symbol):
    key = f"history:{symbol}"
    raw = r.lrange(key, 0, 5)
    if len(raw) < 4:
        print(f"🔍 {symbol}: بيانات غير كافية (عدد = {len(raw)})")
        return None

    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    volumes = [e["volume"] for e in entries]

    price_now = prices[0]
    price_3m_ago = prices[3]
    price_2m_ago = prices[2]
    price_1m_ago = prices[1]

    growth_3m = ((price_now - price_3m_ago) / price_3m_ago) * 100
    if growth_3m >= 2:
        print(f"📈 {symbol}: صعود 3 دقائق = {growth_3m:.2f}% ✅")
        return f"🚀 {symbol} صعد {growth_3m:.2f}% خلال 3 دقائق!"

    growth_1m = ((price_now - price_1m_ago) / price_1m_ago) * 100
    if growth_1m >= 0.8:
        print(f"📈 {symbol}: صعود 1 دقيقة = {growth_1m:.2f}% ✅")
        return f"📈 {symbol} ارتفع {growth_1m:.2f}% خلال دقيقة!"

    if price_now > price_1m_ago > price_2m_ago > price_3m_ago:
        print(f"🟩 {symbol}: 3 شمعات خضراء ✅")
        return f"🟩 3 شمعات خضراء متتالية في {symbol}"

    vol_now = volumes[0]
    vol_1m_ago = volumes[1]
    if vol_now > vol_1m_ago * 1.5:
        print(f"💥 {symbol}: تضخم حجم ✅")
        return f"💥 تضخم مفاجئ بالحجم في {symbol}"

    return None

def monitor_loop():
    symbols = get_symbols()
    if not symbols:
        send_message("🚫 فشل جلب العملات من Bitvavo!")
        return

    send_message(f"🤖 كوكو بدأ يراقب {len(symbols)} عملة 🔍")

    while True:
        for symbol in symbols:
            try:
                data = get_ticker(symbol)
                if not data:
                    print(f"⚠️ {symbol}: لا توجد بيانات حالية.")
                    continue

                store_data(symbol, data)
                signal = analyze(symbol)

                if signal and not r.exists(f"alerted:{symbol}"):
                    r.set(f"alerted:{symbol}", "1", ex=900)
                    coin = symbol.split("-")[0].upper()
                    send_message(signal)
                    send_buy_to_toto(coin)
                else:
                    print(f"⏳ {symbol}: لا إشارات حالياً.")

            except Exception as e:
                print(f"❌ خطأ في {symbol}: {e}")
        print("🔁 انتهاء جولة... استراحة دقيقة.\n")
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
            keys = r.keys("history:*")
            now = datetime.utcnow()
            lines = []
            for key in keys:
                sym = key.decode().split(":")[1]
                last_raw = r.lindex(key, 0)
                if not last_raw:
                    continue
                last = json.loads(last_raw.decode())
                minutes = int((now - datetime.fromisoformat(last["time"])).total_seconds() // 60)
                counter = r.get(f"counter:{sym.split('-')[0]}").decode()
                lines.append(f"• {sym} منذ {minutes} دقيقة *{counter}")

            msg = "👀 العملات تحت المراقبة:\n" + "\n".join(lines) if lines else "🚫 لا عملات الآن"
            send_message(msg)

        elif text == "الملخص":
            keys = r.keys("counter:*")
            lines = [f"{k.decode().split(':')[1]} = {int(r.get(k))} مرة" for k in keys]
            msg = "📊 عدد مرات المراقبة:\n" + "\n".join(lines) if lines else "🚫 لا يوجد أي سجل."
            send_message(msg)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🚀 Koko is alive", 200

def start():
    send_message("✅ كوكو بدأ التشغيل... استعد يا توتو!")
    threading.Thread(target=monitor_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)