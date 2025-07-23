import os, requests, hmac, hashlib, time, json

# مفاتيح من المتغيرات البيئية
BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")

def create_signature(timestamp, method, path, body=""):
    msg = f"{timestamp}{method}{path}{body}"
    return hmac.new(BITVAVO_API_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()

def diagnose_bitvavo_request(path, method="GET"):
    url = "https://api.bitvavo.com" + path
    timestamp = str(int(time.time() * 1000))
    signature = create_signature(timestamp, method, path)
    
    headers = {
        'Bitvavo-Access-Key': BITVAVO_API_KEY,
        'Bitvavo-Access-Signature': signature,
        'Bitvavo-Access-Timestamp': timestamp,
        'Bitvavo-Access-Window': '10000'
    }

    print(f"\n🚀 تجربة الاتصال بـ Bitvavo: {path}")
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print("✅ الاتصال ناجح! الرد:\n", json.dumps(response.json(), indent=2))
    except requests.exceptions.HTTPError as err:
        code = err.response.status_code
        text = err.response.text
        print(f"❌ فشل الاتصال - رمز الحالة {code}")
        print(f"📩 الرد من Bitvavo:\n{text}")

        # تشخيص حسب رمز الخطأ
        if code == 404:
            print("🔍 التشخيص: ربما هذا الزوج غير موجود أو لا يدعم الشموع.")
        elif code == 429:
            print("🚦 التشخيص: تم تجاوز الحد المسموح به من الطلبات. أعد المحاولة لاحقًا.")
        elif code == 400:
            print("⚠️ التشخيص: هناك مشكلة في صيغة الطلب (ربما باراميتر خطأ أو زوج غير صالح).")
        elif code == 403:
            print("⛔ التشخيص: ربما المفاتيح غير مفعلة لهذه العملية أو خاطئة.")
        elif code == 401:
            print("🔐 التشخيص: المصادقة فشلت - تحقق من المفاتيح.")
        elif code == 409:
            print("⏸️ التشخيص: السوق متوقف أو في حالة مزاد حالياً.")
        else:
            print("🤷‍♂️ غير معروف - تحقق من التوكن أو اتصل بالدعم.")
    except Exception as e:
        print("💣 خطأ غير متوقع:", e)

# مثال: جرب فحص شموع زوج BTC-EUR
if __name__ == "__main__":
    test_path = "/v2/market/BTC-EUR/candles?interval=1m&limit=3"
    diagnose_bitvavo_request(test_path)