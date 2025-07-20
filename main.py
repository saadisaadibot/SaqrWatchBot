from flask import Flask, request
import requests
import os

app = Flask(__name__)

# --- إعداد التوكن من البيئة ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- دالة إرسال رسالة تيليغرام ---
def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

# --- الصفحة الرئيسية ---
@app.route('/')
def home():
    return '✅ SaqrWatchBot is alive!'

# --- نقطة استلام Webhook ---
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Webhook received:", data)

        # جرب نستخرج chat_id والنص من عدة أنواع محتملة
        chat_id = None
        text = None

        if 'message' in data:
            chat_id = data['message']['chat']['id']
            text = data['message'].get('text')
        elif 'edited_message' in data:
            chat_id = data['edited_message']['chat']['id']
            text = data['edited_message'].get('text')
        elif 'callback_query' in data:
            chat_id = data['callback_query']['from']['id']
            text = data['callback_query'].get('data')

        if chat_id and text:
            print(f"💬 From {chat_id}: {text}")
            send_message(chat_id, "✅ تم استلام الرسالة!")

    except Exception as e:
        print("❌ Webhook Error:", str(e))

    return 'OK', 200

# --- تشغيل السيرفر ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)