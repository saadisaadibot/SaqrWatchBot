import os
import time
import threading
from datetime import datetime
import requests
from flask import Flask, request
from pycoingecko import CoinGeckoAPI
import redis

app = Flask(__name__)

# ========== المتغيرات ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ========== الإعدادات العامة ==========
cg = CoinGeckoAPI()
r = redis.from_url(REDIS_URL)
bitvavo_coins = set()
lock = threading.Lock()

# ========== إرسال تيليغرام ==========
def send_message(text):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": text})
    except Exception as e:
        print("❌ فشل الإرسال:", e)

# ========== تحميل عملات Bitvavo ==========
def load_bitvavo_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/markets")
        if res.status_code == 200:
            return set(entry["market"].split("-")[0].lower() for entry in res.json())
    except:
        pass
    return set()

# ========== اختيار العملات ==========
def get_top_4_gainers():
    coins = cg.get_coins_markets(vs_currency="eur", per_page=250, page=1)
    results = []
    for coin in coins:
        if coin["symbol"].lower() in bitvavo_coins and coin.get("price_change_percentage_1h_in_currency") is not None:
            change_5m = coin["price_change_percentage_1h_in_currency"] / 12
            results.append({
                "symbol": coin["symbol"].upper(),
                "id": coin["id"],
                "change": change_5m
            })
    results = sorted(results, key=lambda x: x["change"], reverse=True)
    return results[:4]

# ========== المراقبة ==========
def monitor_coin(symbol, coin_id, initial_price):
    key = f"monitoring:{symbol}"
    r.set(key, datetime.now().isoformat(), ex=900)
    count_key = f"count:{symbol}"
    r.incr(count_key)

    try:
        while True:
            elapsed = (datetime.now() - datetime.fromisoformat(r.get(key).decode())).total_seconds()
            if elapsed > 900:
                break
            price = cg.get_price(ids=coin_id, vs_currencies="eur")[coin_id]["eur"]
            if (price - initial_price) / initial_price >= 0.015:
                send_message(f"🚨 اشترِ {symbol} الآن! ارتفعت بنسبة +1.5% خلال المراقبة.")
                break
            time.sleep(60)
    except Exception as e:
        print("خطأ في المراقبة:", e)
    r.delete(key)

# ========== الفحص والمراقبة كل 5 دقائق ==========
def scan_and_monitor():
    while True:
        try:
            top_coins = get_top_4_gainers()
            for coin in top_coins:
                symbol = coin["symbol"]
                monitor_key = f"monitoring:{symbol}"
                if r.exists(monitor_key):
                    continue
                price = cg.get_price(ids=coin["id"], vs_currencies="eur")[coin["id"]]["eur"]
                threading.Thread(target=monitor_coin, args=(symbol, coin["id"], price)).start()
        except Exception as e:
            print("❌ خطأ أثناء الفحص:", e)
        time.sleep(300)

# ========== Webhook ==========
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").strip().lower()
        chat_id = str(data["message"]["chat"]["id"])

        if chat_id == CHAT_ID:
            if text == "شو عم تعمل":
                keys = r.keys("monitoring:*")
                if not keys:
                    send_message("لا تتم مراقبة أي عملة حالياً 👀")
                else:
                    now = datetime.now()
                    lines = ["⌛️ تتم الآن مراقبة:"]
                    for key in keys:
                        symbol = key.decode().split(":")[1]
                        start = datetime.fromisoformat(r.get(key).decode())
                        mins = int((now - start).total_seconds() // 60)
                        count = r.get(f"count:{symbol}")
                        suffix = f" *{count.decode()}" if count else ""
                        lines.append(f"• {symbol}{suffix} منذ {mins} دقيقة")
                    send_message("\n".join(lines))

            elif text == "الملخص":
                all_counts = r.keys("count:*")
                if not all_counts:
                    send_message("لا يوجد أي سجل بعد 📭")
                else:
                    lines = ["📊 عدد مرات مراقبة العملات:"]
                    sorted_counts = sorted(
                        [(key.decode().split(":")[1], int(r.get(key).decode())) for key in all_counts],
                        key=lambda x: x[1],
                        reverse=True
                    )
                    for symbol, count in sorted_counts:
                        lines.append(f"{symbol}: {count} مرة")
                    send_message("\n".join(lines))

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "✅ البوت شغال", 200

# ========== بدء التشغيل ==========
def start_bot():
    global bitvavo_coins
    bitvavo_coins = load_bitvavo_symbols()
    send_message("✅ البوت بدأ باستخدام Bitvavo فقط 🔍")
    threading.Thread(target=scan_and_monitor).start()

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=PORT)