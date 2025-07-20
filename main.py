from flask import Flask, request
import redis
import os

# إعداد Redis
REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL)

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    if data and "message" in data:
        text = data["message"].get("text", "").strip().upper()

        # نتأكد إنها عملة بصيغة XXX-EUR
        if text.endswith("-EUR") and "-" in text and len(text.split("-")[0]) >= 2:
            coin = text
            r.sadd("watchlist", coin)
            print(f"✅ تم تسجيل العملة: {coin}")
            return f"تمت إضافة {coin} إلى المراقبة", 200

    return "No valid coin", 200

if __name__ == "__main__":
    app.run(port=8000)