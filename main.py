import os
from flask import Flask, request
import requests
import redis

app = Flask(__name__)

# جلب المتغيرات
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")

# طباعة للتأكد
print("🚀 Booting...")
print("🤖 BOT_TOKEN:", BOT_TOKEN)
print("💬 CHAT_ID:", CHAT_ID)
print("🧠 REDIS_URL:", REDIS_URL)

# اتصال Redis
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    print("✅ Redis Connected")
except Exception as e:
    print("❌ Redis Failed:", str(e))
    r = None

# دالة إرسال رسالة تيليغرام
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        res = requests.post(url, data=payload)
        print("📤 Telegram status:", res.status_code)
    except Exception as e:
        print("❌ Telegram error:", str(e))

# نقطة التحقق
@app.route("/")
def index():
    return "✅ Bot is running", 200

# نقطة استقبال Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📥 Received Webhook:", data)

        if not data or "message" not in data:
            print("⚠️ No message in data")
            return "", 200

        text = data["message"].get("text", "").strip().upper()
        print("📝 Received Text:", text)

        if "-EUR" in text and len(text) <= 10:
            if r:
                r.hset("orders", text, "من صقر")
            send_message(f"📡 صقر أرسل العملة: {text}")
        else:
            send_message("🦅 أنا صقر وبراقب السوق، ما وصلني أمر واضح 🔍")

        return "", 200

    except Exception as e:
        print("💥 Webhook ERROR:", str(e))
        return "Internal Error", 500

# بدء التطبيق
if __name__ == "__main__":
    send_message("🦅 صقر اشتغل على Railway وبراقب السوق!")
    app.run(host="0.0.0.0", port=8080)