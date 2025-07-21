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
bitvavo_symbols = set()
lock = threading.Lock()

# ========== إرسال رسالة ==========
def send_message(text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
    except:
        pass

# ========== تحميل رموز Bitvavo ==========
def load_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        return set(m["market"].split("-")[0].lower() for m in res.json() if m["market"].endswith("-EUR"))
    except:
        return set()

# ========== جلب شموع ==========
def get_candles(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol.upper()}-EUR/candles?interval=1m&limit=5"
        res = requests.get(url).json()
        return res if isinstance(res, list) else []
    except:
        return []

# ========== فحص الإشارات ==========
def has_signals(candles):
    if len(candles) < 3:
        return False

    # ثلاث شموع خضراء؟
    green = all(c[4] > c[1] for c in candles[-3:])

    # حجم آخر شمعة أكبر من وسط الحجم السابق؟
    volumes = [float(c[5]) for c in candles]
    vol_spike = volumes[-1] > (sum(volumes[:-1]) / max(1, len(volumes)-1)) * 1.5

    # تذبذب عالي بالشمعات الأخيرة؟
    volat = [abs(c[4] - c[1]) / c[1] for c in candles[-3:]]
    volatility = sum(volat) / len(volat) > 0.005  # 0.5%

    score = sum([green, vol_spike, volatility])
    return score >= 2

# ========== جلب سعر ==========
def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/{symbol.upper()}-EUR/price"
        return float(requests.get(url).json()["price"])
    except:
        return None

# ========== المراقبة الدقيقة ==========
def monitor(symbol):
    key = f"monitoring:{symbol}"
    if r.exists(key):
        return

    # عداد مرات المراقبة
    counter_key = f"counter:{symbol}"
    r.incr(counter_key)

    r.set(key, datetime.utcnow().isoformat(), ex=900)
    prices = []

    try:
        for _ in range(15):
            price = get_price(symbol)
            if price: prices.append(price)
            if len(prices) >= 3:
                p1, p2, p3 = prices[-3:]
                if (p3 - p1) / p1 >= 0.02:
                    send_message(f"🚨 اشترِ {symbol.upper()} الآن! +2% خلال 3 دقائق!")
                    break
            time.sleep(60)
    except:
        pass
    finally:
        r.delete(key)

# ========== الماسح الكبير كل 5 دقائق ==========
def scanner():
    while True:
        try:
            for symbol in bitvavo_symbols:
                if r.exists(f"monitoring:{symbol}"):
                    continue
                candles = get_candles(symbol)
                if has_signals(candles):
                    threading.Thread(target=monitor, args=(symbol,)).start()
        except Exception as e:
            print("خطأ:", e)
        time.sleep(300)

# ========== Webhook ==========
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])

        if chat_id != CHAT_ID:
            return "ok"

        if "شو عم تعمل" in text:
            keys = r.keys("monitoring:*")
            if not keys:
                send_message("لا تتم مراقبة أي عملة حالياً 👀")
            else:
                now = datetime.utcnow()
                msg = "🚨 تتم المراقبة:\n"
                for key in keys:
                    sym = key.decode().split(":")[1]
                    t0 = datetime.fromisoformat(r.get(key).decode())
                    mins = int((now - t0).total_seconds() // 60)
                    count = r.get(f"counter:{sym}")
                    msg += f"• {sym.upper()} منذ {mins} دقيقة *{int(count)}\n"
                send_message(msg)

        elif "الملخص" in text:
            keys = r.keys("counter:*")
            msg = "📊 سجل المراقبة:\n"
            for k in keys:
                sym = k.decode().split(":")[1]
                count = int(r.get(k).decode())
                msg += f"{sym.upper()} = {count} مرات\n"
            send_message(msg)

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🛸 البوت شغال ✅", 200

# ========== بدء التشغيل ==========
def start_bot():
    global bitvavo_symbols
    bitvavo_symbols = load_symbols()
    send_message("""
🛸🚀🚨
تم إطلاق المكوك الفضائي 🔥  
بوت المراقبة بدأ عملية الغزو 🤖  
جارٍ مسح أسواق Bitvavo بالكامل...  
استعد لاكتشاف العملات قبل أن تنفجر 💥
""")
    threading.Thread(target=scanner).start()

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=PORT)