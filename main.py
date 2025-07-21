import os
import time
import json
import requests
from datetime import datetime
from flask import Flask, request
import redis
import threading

# === إعداد التطبيق ===
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# === إرسال تيليغرام
def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# === إرسال أمر الشراء لتوتو
def send_buy_to_toto(symbol):
    try:
        msg = f"اشتري {symbol} يا توتو"
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
        send_message(f"📤 كوكو أعطى الإشارة:\n{msg}")
    except Exception as e:
        print(f"❌ فشل إرسال الأمر إلى توتو: {e}")

# === جلب كل رموز -EUR من Bitvavo
def get_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return [item["market"] for item in res.json() if item["market"].endswith("-EUR")]
    except:
        return []

# === جلب بيانات السوق للعملة
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
    except:
        return None

# === تخزين آخر البيانات في Redis
def store_data(symbol, data):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps(data))
    r.ltrim(key, 0, 20)
    r.incr(f"counter:{symbol.split('-')[0]}", amount=1)

# === تحليل سلوك السوق للعملة
def analyze(symbol):
    key = f"history:{symbol}"
    raw = r.lrange(key, 0, 5)
    if len(raw) < 4:
        return None

    entries = [json.loads(x.decode()) for x in raw]
    prices = [e["price"] for e in entries]
    volumes = [e["volume"] for e in entries]

    price_now = prices[0]
    price_3m_ago = prices[3]
    price_2m_ago = prices[2]
    price_1m_ago = prices[1]

    # صعود 2% خلال 3 دقائق
    growth_3m = ((price_now - price_3m_ago) / price_3m_ago) * 100
    if growth_3m >= 2:
        return f"🚀 {symbol} صعد {growth_3m:.2f}% خلال 3 دقائق!"

    # صعود 0.8% خلال دقيقة
    growth_1m = ((price_now - price_1m_ago) / price_1m_ago) * 100
    if growth_1m >= 0.8:
        return f"📈 {symbol} ارتفع {growth_1m:.2f}% خلال دقيقة!"

    # 3 شمعات خضراء
    if price_now > price_1m_ago > price_2m_ago > price_3m_ago:
        return f"🟩 3 شمعات خضراء متتالية في {symbol}"

    # تضخم بالحجم
    vol_now = volumes[0]
    vol_1m_ago = volumes[1]
    if vol_now > vol_1m_ago * 1.5:
        return f"💥 تضخم مفاجئ بالحجم في {symbol}"

    return None

# === حلقة المراقبة كل دقيقة
def monitor_loop():
    symbols = get_symbols()
    send_message(f"🤖 كوكو بدأ يراقب {len(symbols)} عملة 🔍")

    while True:
        for symbol in symbols:
            try:
                data = get_ticker(symbol)
                if not data:
                    continue

                store_data(symbol, data)
                signal = analyze(symbol)

                if signal and not r.exists(f"alerted:{symbol}"):
                    r.set(f"alerted:{symbol}", "1", ex=900)
                    coin = symbol.split("-")[0].upper()
                    send_message(signal)
                    send_buy_to_toto(coin)

            except Exception as e:
                print(f"❌ {symbol}: {e}")
        time.sleep(60)

# === Webhook تيليغرام
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

# === التشغيل
def start():
    send_message("✅ كوكو بدأ التشغيل... استعد يا توتو!")
    threading.Thread(target=monitor_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)