import os
import requests
import time
import hmac
import hashlib
import json
import redis
from datetime import datetime
from flask import Flask, request
from threading import Thread

# إعداد
app = Flask(__name__)
BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL)

# إرسال رسالة إلى تيليغرام
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

# دالة طباعة الأخطاء
def log_error(error):
    print(f"❌ ERROR: {error}")

# دالة طلب من Bitvavo
def bitvavo_request(path):
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    msg = timestamp + method + path
    signature = hmac.new(BITVAVO_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {
        'Bitvavo-Access-Key': BITVAVO_API_KEY,
        'Bitvavo-Access-Signature': signature,
        'Bitvavo-Access-Timestamp': timestamp,
        'Bitvavo-Access-Window': '10000'
    }

    try:
        response = requests.get("https://api.bitvavo.com" + path, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"فشل طلب Bitvavo: {e}")
        return []

# الحصول على قائمة الأسواق المتاحة
def get_allowed_markets():
    try:
        markets = bitvavo_request("/v2/markets")
        allowed = [m["market"] for m in markets if m.get("status") == "trading"]
        print(f"✅ تم تحديث قائمة الأسواق ({len(allowed)} زوج)")
        return allowed
    except Exception as e:
        log_error(f"فشل في جلب الأسواق: {e}")
        return []

# الحصول على آخر 3 شمعات
def get_last_3m_candles(symbol):
    try:
        return bitvavo_request(f"/v2/markets/{symbol}/candles?interval=1m&limit=3")
    except Exception as e:
        log_error(f"{symbol} فشل في جلب الشموع لـ: {e}")
        return []

# نقطة البداية
def main_loop():
    allowed_markets = get_allowed_markets()
    if not allowed_markets:
        print("⛔ لا توجد أسواق متاحة حاليًا.")
        return

    # فقط لاختبار أول عملة من السوق
    for symbol in allowed_markets[:1]:
        candles = get_last_3m_candles(symbol)
        if candles:
            print(f"✅ {symbol}: تم جلب الشموع بنجاح")
        else:
            print(f"❌ {symbol}: لا يوجد شموع")

@app.route("/")
def home():
    return "🤖 Koko Intel Mode is Running."

# تشغيل البوت بخيط مستقل
def start_bot():
    send_message("🤖 تم تشغيل KOKO INTEL MODE - ™️ تمت ✅ تصفية الذاكرة والانطلاق")
    r.flushall()
    main_loop()

if __name__ == "__main__":
    Thread(target=start_bot).start()
    app.run(host="0.0.0.0", port=8080)