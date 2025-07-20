from flask import Flask, request

app = Flask(__name__)

@app.route('/')
def home():
    return '✅ SaqrWatchBot is alive!'

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📬 Webhook received:", data)

        # رد اختياري للرد المباشر عبر Telegram (اختياري فقط للعرض)
        # chat_id = data['message']['chat']['id']
        # text = "✅ الرسالة وصلت"
        # send_message(chat_id, text)

        return 'OK', 200
    except Exception as e:
        print("❌ Webhook Error:", str(e))
        return 'ERROR', 500

# تقدر تضيف send_message إذا بدك رد مباشر
# import requests, os
# TOKEN = os.getenv("BOT_TOKEN")
# def send_message(chat_id, text):
#     url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
#     requests.post(url, data={"chat_id": chat_id, "text": text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)