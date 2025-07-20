import os
from flask import Flask, request
import requests

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")  # حط التوكن بمتغيرات Railway
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if not data or "message" not in data:
        return "No message", 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    print("📥 رسالة وصلت من:", message.get("from", {}).get("username", "مجهول"))
    print("📢 Chat ID:", chat_id)
    print("📝 الرسالة:", text)

    if "شو عم تعمل" in text:
        reply = "عم راقب السوق يا ورد 😎"
        requests.post(BASE_URL, data={"chat_id": chat_id, "text": reply})

    return "OK", 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)