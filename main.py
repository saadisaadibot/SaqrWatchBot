from flask import Flask, request
import os
import requests

app = Flask(__name__)

# إعدادات التوكن والشات
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# دالة إرسال رسالة تيليغرام (اختياري)
def send_message(text):
    if BOT_TOKEN and CHAT_ID:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = {"chat_id": CHAT_ID, "text": text}
        try:
            requests.post(url, data=data)
        except Exception as e:
            print("❌ Error sending message:", e)

@app.route("/")
def home():
    return "✅ SaqrWatchBot is running"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📬 Webhook received:", data)

        # رد تجريبي على أي رسالة (اختياري)
        send_message("📡 تم استلام الإشارة من صقر!")

        return "Received ✅", 200
    except Exception as e:
        print("❌ Webhook error:", e)
        return "Error", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)