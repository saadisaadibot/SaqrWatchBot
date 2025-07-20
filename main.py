import os
import redis
import requests
from flask import Flask, request

app = Flask(__name__)

# جلب المتغيرات البيئية
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")

print("🔧 Initializing...")
print("🔑 BOT_TOKEN:", BOT_TOKEN)
print("📡 CHAT_ID:", CHAT_ID)
print("🧠 REDIS_URL:", REDIS_URL)

# الاتصال بـ Redis
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print("❌ Redis Connection Failed:", str(e))

# إرسال رسالة تيليغرام
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        print("📨 Telegram status:", res.status_code)
        if not res.ok:
            print("❌ Telegram Error:", res.text)
    except Exception as e:
        print("❌ Telegram Send Exception:", str(e))

@app.route("/")
def home():
    return "Saqr is watching 👁️", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📥 Incoming Webhook:", data)

        if not data or "message" not in data:
            print("⚠️ Missing message in data:", data)
            return "", 200

        text = data["message"].get("text", "").strip().upper()
        print("📝 Text Received:", text)

        if "-EUR" in text and len(text) <= 10:
            r.hset("orders", text, "من صقر")
            send_message(f"📡 تم إرسال {text} إلى توتو للشراء ✅")
        else:
            send_message("✋ لساتني صاحي وبراقب السوق يا ورد 😎")

        return "", 200

    except Exception as e:
        print("💥 ERROR in /webhook:", str(e))
        return "Internal Error", 500

# بدء التشغيل
if __name__ == "__main__":
    print("🚀 Starting Saqr...")
    send_message("🦅 صقر اشتغل وبراقب السوق!")
    app.run(host="0.0.0.0", port=8080)