import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

print("🔧 Starting Debug Bot...")
print("🛰️ BOT_TOKEN:", BOT_TOKEN)
print("💬 CHAT_ID:", CHAT_ID)

def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        res = requests.post(url, data={"chat_id": CHAT_ID, "text": text})
        print("📨 Telegram Response:", res.status_code)
        if not res.ok:
            print("❌ Error Sending Message:", res.text)
    except Exception as e:
        print("💥 Telegram Send Exception:", str(e))

@app.route("/")
def home():
    return "Debug Bot is alive ✅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Received Data:", data)

        if not data or "message" not in data:
            print("⚠️ No message found.")
            return "No message", 200

        text = data["message"].get("text", "").strip()
        print("✉️ Message Text:", text)

        send_message(f"📡 Debug Received: {text}")
        return "OK", 200

    except Exception as e:
        error_text = f"🔥 Webhook Exception: {str(e)}"
        print(error_text)
        send_message(error_text)
        return "ERROR", 500

if __name__ == "__main__":
    print("🚀 Flask running...")
    send_message("🧪 بوت التجربة اشتغل بنجاح!")
    app.run(host="0.0.0.0", port=8080)