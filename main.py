import os
import time
import threading
from datetime import datetime
import requests
from flask import Flask, request
import redis

app = Flask(__name__)

# ========== متغيرات البيئة ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== إعدادات عامة ==========
r = redis.from_url(REDIS_URL)
bitvavo_coins = set()
lock = threading.Lock()

# ========== إرسال رسالة تيليغرام ==========
def send_message(text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
    except:
        pass

# ========== تحميل رموز Bitvavo ==========
def load_bitvavo_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return set(m["market"].split("-")[0].lower() for m in res.json() if m["market"].endswith("-EUR"))
    except:
        return set()

# ========== جلب سعر العملة ==========
def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol.upper()}-EUR/price"
        return float(requests.get(url).json()["price"])
    except:
        return None

# ========== مراقبة العملة ==========
def monitor_coin(symbol):
    monitoring_key = f"monitoring:{symbol}"
    if r.exists(monitoring_key):
        return

    # عداد عدد المرات
    counter_key = f"counter:{symbol}"
    r.incr(counter_key)

    r.set(monitoring_key, datetime.utcnow().isoformat(), ex=900)
    prices = []

    try:
        for _ in range(15):  # 15 دقيقة = 15 قراءة
            price = get_price(symbol)
            if price is None:
                time.sleep(60)
                continue

            prices.append(price)

            if len(prices) >= 3:
                p1, p2, p3 = prices[-3:]
                avg = sum([p1, p2, p3]) / 3
                if (p3 - p1) / p1 >= 0.02:
                    send_message(f"🚀 اشترِ {symbol.upper()} الآن! صعود نسبي +2% خلال 3 دقائق!")
                    break
            time.sleep(60)

    except:
        pass
    finally:
        r.delete(monitoring_key)

# ========== المسح كل 5 دقائق ==========
def scan_for_volatility():
    while True:
        try:
            coins_to_check = list(bitvavo_coins)
            for symbol in coins_to_check:
                p1 = get_price(symbol)
                time.sleep(1)
                p2 = get_price(symbol)
                if not p1 or not p2:
                    continue
                change = abs((p2 - p1) / p1)
                if change >= 0.003:  # أي تذبذب بسيط 0.3%
                    if not r.exists(f"monitoring:{symbol}"):
                        threading.Thread(target=monitor_coin, args=(symbol,)).start()
        except Exception as e:
            print("خطأ في المسح:", e)
        time.sleep(300)

# ========== Webhook ==========
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "")
        chat_id = str(data["message"]["chat"]["id"])

        if chat_id != CHAT_ID:
            return "ok"

        if text.strip().lower() == "شو عم تعمل":
            keys = r.keys("monitoring:*")
            if not keys:
                send_message("لا تتم مراقبة أي عملة حالياً 👀")
            else:
                msg = "⌛️ تتم الآن مراقبة:\n"
                now = datetime.utcnow()
                for key in keys:
                    symbol = key.decode().split(":")[1]
                    start_str = r.get(key).decode()
                    start_time = datetime.fromisoformat(start_str)
                    mins = int((now - start_time).total_seconds() // 60)
                    count = r.get(f"counter:{symbol}")
                    count = int(count.decode()) if count else 1
                    msg += f"• {symbol.upper()} منذ {mins} دقيقة *{count}\n"
                send_message(msg)

        elif text.strip().lower() == "الملخص":
            all_keys = [k.decode() for k in r.keys("counter:*")]
            if not all_keys:
                send_message("لا يوجد أي سجل حالياً.")
            else:
                msg = "📊 عدد مرات المراقبة:\n"
                for k in all_keys:
                    sym = k.split(":")[1]
                    count = int(r.get(k).decode())
                    msg += f"{sym.upper()} = {count} مرات\n"
                send_message(msg)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🚀 Bot is running!", 200

# ========== بدء التشغيل ==========
def start_bot():
    global bitvavo_coins
    bitvavo_coins = load_bitvavo_symbols()
    send_message("✅ البوت بدأ باستخدام Bitvavo فقط 🔍")
    threading.Thread(target=scan_for_volatility).start()

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=PORT)