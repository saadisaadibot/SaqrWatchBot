import os
import redis
import requests
from flask import Flask, request

# إعداد
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL)

# إرسال رسالة تيليغرام
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print("❌ Error sending Telegram message:", e)

# الصفحة الرئيسية
@app.route("/")
def home():
    return "Saqr is watching 👁️", 200

# استقبال الرسائل
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return "", 200

        text = data["message"].get("text", "").strip().upper()
        print("📩 Received:", text)

        if "-EUR" in text and len(text) <= 10:
            r.hset("orders", text, "من صقر")
            send_message(f"📡 تم إرسال {text} إلى توتو للشراء ✅")
        else:
            send_message("✋ لساتني صاحي وبراقب السوق يا ورد 😎")
    except Exception as e:
        print("❌ Error in webhook:", e)

    return "", 200

# تشغيل السيرفر عند استدعاء gunicorn
if __name__ == "__main__":
    send_message("🦅 صقر اشتغل وبراقب السوق!")
    app.run(host="0.0.0.0", port=8080)