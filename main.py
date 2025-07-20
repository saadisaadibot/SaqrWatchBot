import os
import requests
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(chat_id, text):
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, data=payload)


@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is running!", 200


@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "").lower()

        if text == "كيفك":
            send_message(chat_id, "تمام الحمد لله، إنت كيفك؟ 😄")

    return "ok", 200


# لما يشتغل Railway ويبعت أول رسالة
if __name__ == "__main__":
    send_message(CHAT_ID, "✅ البوت اشتغل بنجاح!")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))