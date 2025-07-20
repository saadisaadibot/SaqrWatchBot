import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("🔧 Starting Debug Bot...")
print("📡 BOT_TOKEN:", BOT_TOKEN)
print("💬 CHAT_ID:", CHAT_ID)

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        print("📨 Telegram status:", res.status_code)
        if not res.ok:
            print("❌ Telegram Error:", res.text)
    except Exception as e:
        print("❌ Send Failed:", e)

@app.route("/")
def index():
    return "Saqr Debug Bot Running ✅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Webhook Received:", data)

        if not data or "message" not in data:
            print("⚠️ Missing message block!")
            return "No message", 200

        msg = data["message"]
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")

        print(f"📥 Text: {text} | From Chat ID: {chat_id}")
        send_message(f"📨 استلمت: {text}")

        return "OK", 200

    except Exception as e:
        print("💥 ERROR in webhook():", str(e))
        send_message("💥 مشكلة داخل /webhook: " + str(e))
        return "Webhook Error", 500

if __name__ == "__main__":
    print("🚀 Flask running...")
    app.run(host="0.0.0.0", port=8080)