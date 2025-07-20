import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("SAQR_BOT_TOKEN")
CHAT_ID = os.getenv("SAQR_CHAT_ID")

def send_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

@app.route("/")
def home():
    return "Saqr is flying 🦅", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    if not data or "message" not in data:
        return '', 200

    msg = data["message"].get("text", "")
    if "صقر" in msg:
        send_message("🦅 حاضر يا باشا! أنا صقر وجاهز للإقلاع")
    return '', 200

if __name__ == "__main__":
    send_message("🚀 تم تشغيل صقر!")
    app.run(host="0.0.0.0", port=8080)