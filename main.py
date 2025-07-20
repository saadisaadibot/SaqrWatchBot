import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")  # مؤقتًا نحتفظ فيه بس ما ضروري هون

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

@app.route("/")
def home():
    return "Saqer Bot is Alive! 🦅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return '', 200

    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "")

    # رد وهمي
    reply = f"📡 صقر استلم رسالتك: {text}"
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={
        "chat_id": chat_id,
        "text": reply
    })

    return '', 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
