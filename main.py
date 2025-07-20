import os
import time
import threading
from datetime import datetime
import requests
from flask import Flask, request
from pycoingecko import CoinGeckoAPI
import redis

app = Flask(__name__)

# ========== متغيرات البيئة ==========
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

# ========== إرسال رسالة تيليغرام ==========
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
            return set(
                entry["market"].split("-")[0].lower()
                for entry in res.json()
                if entry["market"].endswith("-EUR")
            )
    except Exception as e:
        print("❌ فشل تحميل عملات Bitvavo:", e)
    return set()

# ========== اختيار العملات ==========
def get_top_4_gainers():
    try:
        coins = cg.get_coins_markets(vs_currency="eur", per_page=250, page=1)
        results = []
        for coin in coins:
            if coin["symbol"] in bitvavo_coins and coin.get("price_change_percentage_1h_in_currency") is not None:
                change_5m = coin["price_change_percentage_1h_in_currency"] / 12
                results.append({
                    "symbol": coin["symbol"].upper(),
                    "id": coin["id"],
                    "change": change_5m
                })
        results = sorted(results, key=lambda x: x["change"], reverse=True)
        print("🔍 Top gainers:", [c["symbol"] for c in results[:4]])
        return results[:4]
    except Exception as e:
        print("❌ خطأ أثناء جلب بيانات CoinGecko:", e)
        return []

# ========== مراقبة العملة ==========
def monitor_coin(symbol, initial_price):
    start_time = datetime.now()
    r.set(f"monitoring:{symbol}", start_time.isoformat(), ex=300)
    print(f"👁️ بدء مراقبة {symbol} عند سعر {initial_price}")
    try:
        while (datetime.now() - start_time).total_seconds() < 300:
            price = cg.get_price(ids=symbol.lower(), vs_currencies="eur")[symbol.lower()]["eur"]
            pct = (price - initial_price) / initial_price
            print(f"📈 {symbol}: {price:.4f} ({pct * 100:.2f}%)")
            if pct >= 0.015:
                send_message(f"🚨 اشترِ {symbol} الآن! ارتفعت بنسبة +1.5% خلال المراقبة.")
                break
            time.sleep(60)
    except Exception as e:
        print(f"❌ خطأ أثناء مراقبة {symbol}:", e)
    r.delete(f"monitoring:{symbol}")

# ========== المسح كل 5 دقائق ==========
def scan_and_monitor():
    print("🌀 بدء المسح التلقائي")
    first_run = True
    while True:
        try:
            top_coins = get_top_4_gainers()
            for coin in top_coins:
                symbol = coin["symbol"]
                if r.exists(f"monitoring:{symbol}"):
                    continue
                price = cg.get_price(ids=coin["id"], vs_currencies="eur")[coin["id"]]["eur"]
                threading.Thread(target=monitor_coin, args=(symbol, price)).start()
        except Exception as e:
            print("❌ خطأ أثناء المسح:", e)

        # تشغيل فوري لأول مرة
        if first_run:
            first_run = False
            time.sleep(5)
        else:
            time.sleep(300)

# ========== Webhook ==========
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "")
        chat_id = str(data["message"]["chat"]["id"])
        if text.strip().lower() == "شو عم تعمل" and chat_id == CHAT_ID:
            keys = r.keys("monitoring:*")
            if not keys:
                msg = "لا تتم مراقبة أي عملة حالياً 👀"
            else:
                lines = ["⌛️ تتم الآن مراقبة:"]
                now = datetime.now()
                for key in keys:
                    symbol = key.decode().split(":")[1]
                    start_str = r.get(key).decode()
                    start_time = datetime.fromisoformat(start_str)
                    mins = int((now - start_time).total_seconds() // 60)
                    lines.append(f"• {symbol} منذ {mins} دقيقة")
                msg = "\n".join(lines)
            send_message(msg)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Bot is running ✅", 200

# ========== بدء التشغيل ==========
def start_bot():
    global bitvavo_coins
    bitvavo_coins = load_bitvavo_symbols()
    print("✅ رموز Bitvavo المحصورة بـ EUR:", bitvavo_coins)
    send_message("✅ البوت اشتغل بنجاح!")
    threading.Thread(target=scan_and_monitor).start()

if __name__ == "__main__":
    start_bot()
    app.run(host="0.0.0.0", port=PORT)