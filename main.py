import os
import redis
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")

print("🔧 Starting Debug Bot...")
print("🛰️ BOT_TOKEN:", BOT_TOKEN)
print("💬 CHAT_ID:", CHAT_ID)
print("🧠 REDIS_URL:", REDIS_URL)

# Redis
try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    print("✅ Connected to Redis")
except Exception as e:
    print("❌ Redis Connection Error:", e)

# Send Telegram message
def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        print("📨 Telegram Response:", res.status_code)
        if not res.ok:
            print("❌ Telegram Error:", res.text)
    except Exception as e:
        print("❌ Telegram Exception:", e)

@app.route("/")
def index():
    return "✅ Bot is running", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📥 Webhook received:", data)

        if not data or "message" not in data:
            print("⚠️ No 'message' in data:", data)
            return "", 200

        text = data["message"].get("text", "").strip().upper()
        print("📝 Message text:", text)

        if "-EUR" in text and len(text) <= 10:
            try:
                r.hset("orders", text, "من صقر")
                print("✅ Stored in Redis:", text)
                send_message(f"📡 صقر أرسل {text} وتم تخزينه في Redis ✅")
            except Exception as re:
                print("❌ Redis Store Error:", re)
                send_message("❌ فشل تخزين العملة في Redis!")
        else:
            send_message("🔎 أمر غير واضح، راقب العملة أولاً")

        return "ok", 200

    except Exception as e:
        print("💥 ERROR in /webhook route:")
        import traceback
        traceback.print_exc()  # طباعة مفصلة للخطأ
        send_message(f"🚨 خطأ داخلي: {str(e)}")
        return "Internal Error", 500

if __name__ == "__main__":
    print("🚀 Flask running...")
    send_message("🦅 صقر اشتغل وبيراقب 👁️")
    app.run(host="0.0.0.0", port=8080)