import os
import json
import time
import hmac
import hashlib
import requests

BITVAVO_API_KEY = os.getenv("BITVAVO_API_KEY")
BITVAVO_API_SECRET = os.getenv("BITVAVO_API_SECRET")

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
        print(f"❌ {path} => فشل: {e}")
        return []

def get_markets():
    raw = bitvavo_request("/v2/markets")
    return [m["market"] for m in raw if m.get("status") == "trading"]

def check_candle_support():
    valid = []
    all_markets = get_markets()
    print(f"🔍 فحص {len(all_markets)} زوج...")
    for market in all_markets:
        data = bitvavo_request(f"/v2/market/{market}/candles?interval=1m&limit=1")
        if data:
            print(f"✅ {market} يدعم الشموع")
            valid.append(market)
        else:
            print(f"❌ {market} لا يدعم الشموع")
        time.sleep(0.1)  # لتجنب الحظر المؤقت
    with open("valid_markets.json", "w") as f:
        json.dump(valid, f)
    print(f"✅ تم حفظ {len(valid)} سوق صالح في valid_markets.json")

check_candle_support()