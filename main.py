import os
from flask import Flask, request
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8108480049:AAGNBsq-LTMWVlJyUiBk2PKj8e7fJfChL_E"

app = Flask(__name__)
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": chat_id, "text": text})

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    print("📬 Webhook received:", data)

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        message_text = data["message"].get("text", "")
        
        # الرد تلقائياً على أي رسالة
        reply = f"👋 أهلاً! وصلتني رسالتك: {message_text}"
        send_message(chat_id, reply)

    return "OK", 200

@app.route("/")
def home():
    return "✅ SaqrWatchBot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)