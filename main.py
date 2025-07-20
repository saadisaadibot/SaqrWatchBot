import os
import redis
import requests
from flask import Flask, request

# إعداد البوت و Redis
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ضيف هاد المفتاح بالمتغيرات على Railway
CHAT_ID = os.getenv("CHAT_ID")      # ضيف الشات آيدي كمان
REDIS_URL = os.getenv("REDIS_URL")
r = redis.Redis.from_url(REDIS_URL)

app = Flask(__name__)

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=data)
    except Exception as e:
        print("❌ Failed to send Telegram message:", str(e))

@app.route("/")
def home():
    return "✅ SaqrWatchBot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📬 Webhook Received:", data)

        if not data or "message" not in data:
            print("⚠️ No valid message in payload")
            return "", 200

        text = data["message"].get("text", "")
        print("📝 Message Text:", text)

        if "-EUR" in text and len(text) <= 12:
            r.hset("orders", text, "من صقر")
            send_message(f"🦅 تم تسجيل العملة: {text}")
        else:
            send_message("🪶 أرسل أمر واضح فيه عملة بصيغة مثل ADA-EUR")

        return "", 200

    except Exception as e:
        print("💥 Webhook ERROR:", str(e))
        return "Internal Error", 500

if __name__ == "__main__":
    send_message("🦅 صقر اشتغل على Railway بنجاح")
    app.run(host="0.0.0.0", port=8080)