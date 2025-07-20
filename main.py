import os
import redis
import requests
from flask import Flask, request

# إعداد
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REDIS_URL = os.getenv("REDIS_URL")

# طباعة معلومات ربط Redis
print("🔧 Trying Redis URL:", REDIS_URL)

try:
    r = redis.from_url(REDIS_URL)
    r.ping()
    print("✅ Redis Connected Successfully")
except Exception as e:
    print("❌ Redis Connection Failed:", str(e))
    r = None  # مشان ما ينهار البوت لاحقاً