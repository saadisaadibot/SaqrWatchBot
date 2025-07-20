import os
from flask import Flask, request
import redis
import requests

# إعداد المتغيرات
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")

# إعداد Redis
r = redis.from_url(REDIS_URL)

# إعداد Flask
app = Flask(__name__)
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# دالة إرسال رسالة إلى تيليغرام
def send_message(text):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("❌ Telegram Send Error:", str(e))

# نقطة اختبار السيرفر /
@app.route("/", methods=["GET"])
def home():
    return "🦅 Saqr Bot is Alive", 200

# نقطة استقبال Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📨 Received Webhook:", data)

        if not data or "message" not in data:
            print("⚠️ No message in data")
            return "", 200

        text = data["message"].get("text", "")
        print("📄 Received Text:", text)

        if "-EUR" in text and len(text) <= 15:
            if r:
                r.hset("orders", text, "صقر")
                send_message(f"🦅 أرسل العملة: {text}")
            else:
                send_message("🧨 Redis غير متصل")
        else:
            send_message("🦅 صلّحلي أمر واضح فيه -EUR")

        return "", 200

    except Exception as e:
        print("💥 Webhook ERROR:", str(e))
        return "Internal Error", 500

# تشغيل التطبيق على Railway
if __name__ == "__main__":
    send_message("🦅 صقر اشتغل على Railway")
    app.run(host="0.0.0.0", port=8080)