import os
import requests
from flask import Flask, request

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8108480049:AAGNBsq-LTMWVlJyUiBk2PKj8e7fJfChL_E"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = Flask(__name__)

def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    data = {"chat_id": chat_id, "text": text}
    requests.post(url, data=data)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("📬 Webhook received:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if "شو عم تعمل" in text:
            send_message(chat_id, "🚀 بوت صقر شغّال وعم يراقب العملات 🔍")
        elif "اختبر" in text or "test" in text:
            send_message(chat_id, "✅ تم الاستلام بنجاح من Webhook")

    return "Received", 200

@app.route("/")
def home():
    return "✅ SaqrWatchBot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)