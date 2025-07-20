import os
from flask import Flask, request
import traceback

app = Flask(__name__)

@app.route('/')
def index():
    return '👋 Bot is running!'

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        print("✅ Webhook received!")
        print("📦 Data:", data)

        return 'OK', 200
    except Exception as e:
        print("❌ Error occurred in /webhook:")
        print("🔻 Exception:", str(e))
        print("🔻 Traceback:")
        traceback.print_exc()
        return 'Internal Server Error', 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)