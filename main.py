import os
import redis
import requests
from flask import Flask, request

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL)

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

@app.route("/")
def home():
    return "Saqr is watching 👁️", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return "", 200

    text = data["message"].get("text", "").strip()
    print("📩 Received:", text)

    if "-EUR" in text.upper() and len(text) <= 10:
        r.hset("orders", text.upper(), "من صقر")
        send_message(f"📡 تم إرسال {text.upper()} إلى توتو للشراء ✅")
    elif "كيفك" in text or "شو عم تعمل" in text:
        send_message("✋ لساتني صاحي وبراقب السوق يا ورد 😎")
    else:
        pass  # تجاهل باقي الرسائل

    return "", 200

if __name__ == "__main__":
    send_message("🦅 صقر اشتغل وبراقب السوق!")
    app.run(host="0.0.0.0", port=8080)