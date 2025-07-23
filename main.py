import os, time, json, requests, hmac, hashlib
from flask import Flask

app = Flask(__name__)

# تحميل المفاتيح
BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")

# طباعة حالة المفاتيح
if not BITVAVO_API_KEY or not BITVAVO_API_SECRET:
    print("🚫 المفاتيح غير موجودة! تأكد من إضافتها إلى Railway Variables")
else:
    print("✅ تم تحميل مفاتيح Bitvavo")

# طلب API عام
def bitvavo_request(path):
    try:
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
        url = "https://api.bitvavo.com" + path
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ فشل طلب {path}: {e}")
        return None

# اختبار 1: سحب قائمة الأسواق
def test_markets():
    print("\n🔎 جلب قائمة الأسواق...")
    markets = bitvavo_request("/v2/markets")
    if not markets:
        print("🚫 فشل جلب الأسواق.")
        return

    print(f"✅ تم جلب {len(markets)} سوق.")
    print("🔹 أول 3 عناصر:")
    for m in markets[:3]:
        print(json.dumps(m, indent=2))

    supported = [m["market"] for m in markets if m.get("supportsCandles")]
    print(f"\n✅ عدد الأزواج التي تدعم الشموع: {len(supported)}")

# اختبار 2: شموع عملة BTC-EUR
def test_candles():
    print("\n🕯️ تجربة جلب شموع BTC-EUR...")
    result = bitvavo_request("/v2/market/BTC-EUR/candles?interval=1m&limit=3")
    if result:
        print("✅ الشموع:")
        for c in result:
            print(c)
    else:
        print("🚫 فشل في جلب الشموع لـ BTC-EUR.")

@app.route("/")
def index():
    return "🔍 Bitvavo Debug Running"

if __name__ == "__main__":
    test_markets()
    test_candles()
    app.run(host="0.0.0.0", port=8080)