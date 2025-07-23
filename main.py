import os, time, json, requests, hmac, hashlib
from datetime import datetime
from flask import Flask, request
import redis, threading, traceback

app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")
BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")
PORT = int(os.getenv("PORT", 5000))
TOTO_WEBHOOK = "https://totozaghnot-production.up.railway.app/webhook"
r = redis.from_url(REDIS_URL)

COLLECTION_INTERVAL = 180
MONITOR_DURATION = 30
MONITOR_INTERVAL = 30
allowed_markets = set()

def log_error(error_text):
    print("❌ ERROR:", error_text)
    traceback.print_exc()

def send_message(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        log_error(f"فشل إرسال رسالة تيليغرام: {e}")

def send_buy_to_toto(symbol, source="INTEL"):
    msg = f"🚀 اشتري {symbol} يا كوكو ({source})" if source == "INTEL" else f"🍼 عملة جديدة: اشتري {symbol} يا كوكو (NEW)"
    try:
        requests.post(TOTO_WEBHOOK, json={"message": {"text": msg}})
    except Exception as e:
        log_error(f"فشل إرسال إشارة لتوتو: {e}")

def bitvavo_request(path):
    timestamp = str(int(time.time() * 1000))
    method = "GET"
    msg = timestamp + method + path
    signature = hmac.new(BITVAVO_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
    headers = {
        'Bitvavo-Access-Key': BITVAVO_API_KEY,
        'Bitvavo-Access-Signature': signature,
        'Bitvavo-Access-Timestamp': timestamp,
        'Bitvavo-Access-Window': '10000'
    }
    try:
        response = requests.get("https://api.bitvavo.com" + path, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        log_error(f"فشل طلب Bitvavo: {e}")
        return []

def update_allowed_markets():
    global allowed_markets
    try:
        markets = bitvavo_request("/v2/markets")
        allowed_markets = set(m["market"] for m in markets if m["market"].endswith("-EUR"))
        print(f"✅ تم تحديث قائمة الأسواق ({len(allowed_markets)} زوج)")
    except Exception as e:
        log_error(f"فشل تحديث قائمة الأسواق: {e}")
        allowed_markets = set()

def get_last_3m_candles(symbol):
    if symbol not in allowed_markets:
        return []
    try:
        return bitvavo_request(f"/v2/market/{symbol}/candles?interval=1m&limit=3")
    except Exception as e:
        log_error(f"فشل في جلب الشموع لـ {symbol}: {e}")
        return []

def get_price(symbol):
    try:
        url = f"https://api.bitvavo.com/v2/ticker/price?market={symbol}"
        return float(requests.get(url).json()["price"])
    except Exception as e:
        log_error(f"فشل في جلب السعر لـ {symbol}: {e}")
        return None

def compute_score(candles):
    try:
        if len(candles) < 3:
            return 0
        total_change = ((candles[-1][4] - candles[0][1]) / candles[0][1]) * 100
        avg_range = sum([(c[2] - c[3]) for c in candles]) / len(candles)
        avg_volume = sum([c[5] for c in candles]) / len(candles)
        return (total_change * 1.5) + (avg_range * 2) + (avg_volume * 0.01)
    except Exception as e:
        log_error(f"فشل حساب السكور: {e}")
        return 0

def monitor(symbol):
    try:
        price = get_price(symbol)
        if not price or price < 0.005:
            return
        r.hset("watching", symbol, json.dumps({"start": datetime.utcnow().isoformat()}))
    except Exception as e:
        log_error(f"فشل في مراقبة {symbol}: {e}")

def watch_checker():
    while True:
        try:
            now = datetime.utcnow()
            watching = r.hgetall("watching")
            for symbol_b, data_b in watching.items():
                symbol = symbol_b.decode()
                try:
                    data = json.loads(data_b.decode())
                    start = datetime.fromisoformat(data["start"])
                except:
                    r.hdel("watching", symbol)
                    continue

                candles = get_last_3m_candles(symbol)
                if not candles or len(candles) < 2:
                    continue

                current_price = candles[-1][4]
                found_signal = False
                for c in candles[:-1]:
                    old_price = c[4]
                    if old_price == 0:
                        continue
                    diff = ((current_price - old_price) / old_price) * 100
                    if diff >= 1.5:
                        send_buy_to_toto(symbol.split("-")[0], source="INTEL")
                        send_message(f"🚨 إشارة شراء لـ {symbol.split('-')[0]} - ارتفعت {diff:.2f}% خلال دقائق")
                        r.hdel("watching", symbol)
                        found_signal = True
                        break

                minutes = (now - start).total_seconds() / 60
                if not found_signal and minutes >= 7:
                    r.hdel("watching", symbol)
                elif minutes >= MONITOR_DURATION:
                    r.hdel("watching", symbol)
        except Exception as e:
            log_error(f"فشل في حلقة المراقبة: {e}")
        time.sleep(MONITOR_INTERVAL)

def collect_top_100():
    if not allowed_markets:
        update_allowed_markets()
    try:
        tickers = bitvavo_request("/v2/ticker/price")
        candidates = []
        for t in tickers:
            try:
                symbol = t["market"]
                if not symbol.endswith("-EUR") or symbol not in allowed_markets:
                    continue
                price = float(t["price"])
                if price < 0.005 or r.hexists("watching", symbol):
                    continue
                candles = get_last_3m_candles(symbol)
                score = compute_score(candles)
                candidates.append((symbol, score))
            except Exception as e:
                log_error(f"خطأ أثناء فحص {t}: {e}")

        top = sorted(candidates, key=lambda x: x[1], reverse=True)[:100]
        for symbol, score in top:
            monitor(symbol)
    except Exception as e:
        log_error(f"فشل جمع العملات: {e}")

def scheduler():
    while True:
        collect_top_100()
        time.sleep(1800)

@app.route("/", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        if "message" in data:
            text = data["message"].get("text", "").lower()
            chat_id = str(data["message"]["chat"]["id"])
            if chat_id != CHAT_ID:
                return "ok"
            if "شو عم تعمل" in text:
                now = datetime.utcnow()
                watching = r.hgetall("watching")
                lines = []
                for i, (symbol_b, data_b) in enumerate(watching.items(), start=1):
                    symbol = symbol_b.decode()
                    data = json.loads(data_b.decode())
                    mins = int((now - datetime.fromisoformat(data["start"])).total_seconds() // 60)
                    lines.append(f"{i}. {symbol.split('-')[0]} تحت المراقبة، باقي {MONITOR_DURATION - mins} دقيقة")
                msg = "\n".join(lines) if lines else "🚫 لا عملات تحت المراقبة حالياً"
                send_message(msg)
        return "ok"
    except Exception as e:
        log_error(f"فشل في webhook: {e}")
        return "error", 500

@app.route("/", methods=["GET"])
def home():
    return "🧠 KOKO INTEL MODE™ يعمل بثقة ودهاء", 200

def start():
    try:
        r.flushall()
        update_allowed_markets()  # ✅ تحديث السوق قبل أي شيء
        send_message("🤖 تم تشغيل KOKO INTEL MODE™ - تمت تصفية الذاكرة والانطلاق ✅")
        threading.Thread(target=scheduler).start()
        threading.Thread(target=watch_checker).start()
    except Exception as e:
        log_error(f"فشل في بدء التشغيل: {e}")

if __name__ == "__main__":
    start()
    app.run(host="0.0.0.0", port=PORT)