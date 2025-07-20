from flask import Flask, request
import os

app = Flask(__name__)

@app.route('/')
def home():
    return '✅ SaqrWatchBot is online'

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📩 Received Webhook Data:", data)
        return "OK", 200
    except Exception as e:
        print("🔥 ERROR in /webhook:", str(e))
        return "Error", 500

if __name__ == "__main__":
    print("🚀 SaqrWatchBot is running...")
    app.run(host="0.0.0.0", port=8080)