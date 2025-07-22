import os, time, json, requests
from datetime import datetime
from flask import Flask, request
import redis, threading

# إعدادات بيئية
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
PORT = int(os.getenv("PORT", 5000))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

# إعدادات زمنية
monitor_duration = 30   # دقائق
price_check_interval = 30  # ثانية
scan_interval = 60    # كل 30 دقيقة (جمع العملات)

### رسائل Telegram
def send_message(msg):
    try:
        requests.post(f"{BASE_URL}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except: pass

### إرسال أمر شراء لتوتو
def send_buy_to_toto(symbol):
    msg = f"اشتري {symbol} يا توتو"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except: pass

### جلب top 100 عملة حسب vol
def get_top_symbols():
    try:
        res = requests.get("https://api.bitvavo.com/v2/ticker/24h").json()
        filtered = [t for t in res if t["market"].endswith("-EUR")]
        sorted_vol = sorted(filtered, key=lambda x: float(x["volume"]), reverse=True)
        return [t["market"] for t in sorted_vol[:100]]
    except:
        return []

### جلب بيانات عملة واحدة
def get_price(symbol):
    try:
        res = requests.get(f"https://api.bitvavo.com/v2/ticker/price?market={symbol}").json()
        return float(res["price"])
    except:
        return None

### تخزين الأسعار لكل عملة (آخر 3 فقط)
def store_price(symbol, price):
    key = f"history:{symbol}"
    r.lpush(key, json.dumps({"price": price, "time": datetime.utcnow().isoformat()}))
    r.ltrim(key, 0, 2)

### شرط 3 شموع خضراء
def has_3_green(symbol):
    data = r.lrange(f"history:{symbol}", 0, 2)
    if len(data) < 3: return False
    prices = [json.loads(p.decode())["price"] for p in data]
    return prices[0] > prices[1] > prices[2]

### جمع العملات كل 30 دقيقة
def scan_top_100_loop():
    while True:
        symbols = get_top_symbols()
        for symbol in symbols:
            price = get_price(symbol)
            if not price: continue
            store_price(symbol, price)

            if r.hexists("watching", symbol): continue

            if has_3_green(symbol):
                r.hset("watching", symbol, datetime.utcnow().isoformat())
                r.set(f"entry:{symbol}", price)
                print(f"🟢 دخلت {symbol} المراقبة بعد 3 شموع خضراء")
        time.sleep(scan_interval)

### التحقق من الصعود ≥ 2% كل 30 ثانية
def watch_loop():
    while True:
        now = datetime.utcnow()
        watching = r.hgetall("watching")

        for symbol_b, start_b in watching.items():
            symbol = symbol_b.decode()
            start = datetime.fromisoformat(start_b.decode())
            elapsed = (now - start).total_seconds() / 60

            entry = float(r.get(f"entry:{symbol}") or 0)
            current = get_price(symbol)
            if not current or entry == 0: continue

            change = ((current - entry) / entry) * 100
            if change >= 2:
                send_buy_to_toto(symbol.split("-")[0].upper())
                r.hdel("watching", symbol)
                r.delete(f"entry:{symbol}")
                r.delete(f"history:{symbol}")
            elif elapsed >= monitor_duration:
                r.hdel("watching", symbol)
                r.delete(f"entry:{symbol}")
                r.delete(f"history:{symbol}")

        time.sleep(price_check_interval)

### أوامر Telegram
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json()
    if "message" in data:
        text = data["message"].get("text", "").lower()
        chat_id = str(data["message"]["chat"]["id"])
        if chat_id != CHAT_ID:
            return "ok"

        if "شو عم تعمل" in text:
            lines = []
            now = datetime.utcnow()
            for symbol_b, t_b in r.hgetall("watching").items():
                symbol = symbol_b.decode()
                t = datetime.fromisoformat(t_b.decode())
                mins = int((now - t).total_seconds() // 60)
                lines.append(f"• تتم مراقبة {symbol.split('-')[0]}، باقي {monitor_duration - mins} دقيقة")
            send_message("\n".join(lines) if lines else "🚫 لا شيء حاليًا")

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "🚀 Koko Pro يعمل", 200

### بدء السكربت
def start():
    send_message("🤖 بدأ Koko Pro العمل، تنظيف البيانات...")
    for key in r.keys("history:*"): r.delete(key)
    for key in r.keys("entry:*"): r.delete(key)
    r.delete("watching")

    threading.Thread(target=scan_top_100_loop).start()
    threading.Thread(target=watch_loop).start()

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)