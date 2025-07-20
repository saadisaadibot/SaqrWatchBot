import os
import redis
import requests
from flask import Flask, request

app = Flask(__name__)

# المتغيرات البيئية
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")

print("🔧 Initializing...")
print("🔑 BOT_TOKEN:", BOT_TOKEN)
print("📡 CHAT_ID:", CHAT_ID)
print("🧠 REDIS_URL:", REDIS_URL)

# الاتصال بـ Redis
r = None
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print("❌ Redis Connection Failed:", str(e))

# إرسال رسالة إلى تيليغرام
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        print("📨 Telegram status:", res.status_code)
        if not res.ok:
            print("❌ Telegram Error:", res.text)
    except Exception as e:
        print("❌ Telegram Exception:", str(e))

@app.route("/")
def home():
    return "صقر مستعد للانقضاض 🦅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📥 Incoming Webhook Payload:", data)

        if not data or "message" not in data:
            print("⚠️ Webhook missing 'message' field!")
            send_message("⚠️ تم استلام طلب غير صالح عبر Webhook 🚫")
            return "", 200

        text = data["message"].get("text", "").strip().upper()
        print("📝 Received Text:", text)

        if "-EUR" in text and len(text) <= 10:
            if r:
                try:
                    r.hset("orders", text, "من صقر")
                    print("✅ Saved to Redis:", text)
                    send_message(f"📡 تم إرسال {text} إلى توتو ✅")
                except Exception as redis_error:
                    print("❌ Redis Set Error:", str(redis_error))
                    send_message(f"⚠️ فشل حفظ {text} في Redis: {redis_error}")
            else:
                print("⚠️ Redis غير متصل")
                send_message(f"⚠️ Redis غير متصل. لم يتم حفظ {text} ❌")
        else:
            send_message("✋ لساتني صاحي وبراقب السوق يا ورد 😎")

        return "", 200

    except Exception as e:
        print("💥 Webhook Processing Error:", str(e))
        send_message(f"💥 خطأ داخلي أثناء المعالجة: {e}")
        return "Internal Server Error", 500

if __name__ == "__main__":
    print("🚀 Starting Saqr Watch Bot...")
    send_message("🦅 صقر جاهز يراقب السوق عبر Webhook!")
    app.run(host="0.0.0.0", port=8080)