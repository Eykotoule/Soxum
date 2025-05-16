import requests
import websocket
import threading
import json
import time
import datetime
import traceback
import os
import logging
from keep_alive import keep_alive  # فرض می‌کنم این ماژول برای نگه‌داشتن بات فعاله

# تنظیمات لاگینگ برای ذخیره خطاها
logging.basicConfig(filename='bot.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# توکن بات تلگرام (بهتره از متغیر محیطی استفاده کنی)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8041985955:AAGNPL_dWWWI5AWlYFue5NxkNOXsYqBOmiw")
TELEGRAM_CHANNEL_ID = "@PumpGuardians"
SEEN_MINTS = set()  # برای جلوگیری از ارسال تکراری توکن‌ها

# تابع ارسال پیام به تلگرام
def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            logging.error(f"خطا در ارسال به تلگرام: {response.text}")
    except Exception as e:
        logging.exception("خطا در ارسال پیام به تلگرام")

# تابع فرمت کردن اطلاعات توکن
def format_token_message(info):
    try:
        address = info.get("address")
        if not address or address in SEEN_MINTS:
            return None
        SEEN_MINTS.add(address)

        name = info.get("name", "؟")
        symbol = info.get("symbol", "؟")
        price_usd = float(info.get("usdMarketPrice", 0))
        price_sol = float(info.get("solMarketPrice", 0))
        volume = float(info.get("totalVolume", 0))
        market_cap = float(info.get("marketCapUsd", 0))
        holders = info.get("holders", "؟")
        twitter = info.get("twitter", "موجود نیست")
        website = info.get("website", "موجود نیست")
        created_at = int(info.get("created_at", 0))
        score = int(info.get("score", 3))

        # فیلتر کردن توکن‌ها با حجم معاملات کمتر از 100 SOL
        if volume < 100:
            logging.info(f"توکن {address} به دلیل حجم کم ({volume} SOL) فیلتر شد")
            return None

        green_circles = "🟢" * score

        # محاسبه سن توکن با زمان UTC
        if created_at:
            now_utc = datetime.datetime.now(datetime.timezone.utc).timestamp()
            age_seconds = now_utc - created_at
            age_minutes = int(age_seconds // 60)
            age_str = f"{age_minutes} دقیقه پیش"
        else:
            age_str = "نامشخص"

        message = (
            f"<b>PUMP GUARDIANS AI</b>\n\n"
            f"<b>{name} / {symbol}</b>\n"
            f"{green_circles} (امتیاز: {score})\n\n"
            f"💵 <b>قیمت:</b> ${price_usd:.4f} ({price_sol:.4f} SOL)\n"
            f"💰 <b>ارزش بازار:</b> ${market_cap:,.0f}\n"
            f"📈 <b>حجم معاملات:</b> {volume:,.0f} SOL\n"
            f"👥 <b>تعداد هولدرها:</b> {holders}\n"
            f"⏱️ <b>سن توکن:</b> {age_str}\n"
            f"🌐 <b>وب‌سایت:</b> {website}\n"
            f"🐦 <b>توییتر:</b> {twitter}\n\n"
            f"<a href='https://pump.fun/{address}'>خرید</a> | "
            f"<a href='https://www.dexscreener.com/solana/{address}'>چارت</a> | "
            f"<a href='https://birdeye.so/token/{address}'>اطلاعات بیشتر</a>"
        )
        return message
    except Exception:
        logging.exception("خطا در فرمت کردن پیام توکن")
        return None

# تابع دریافت اطلاعات توکن از API
def fetch_token_info(address):
    try:
        url = f"https://pumpportal.fun/api/mint/{address}"
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            logging.error(f"خطا در دریافت اطلاعات توکن {address}: {res.text}")
            return None
        return res.json()
    except Exception:
        logging.exception(f"خطا در دریافت اطلاعات توکن {address}")
        return None

# تابع مدیریت پیام‌های WebSocket
def on_message(ws, message):
    try:
        data = json.loads(message)
        mint = data.get("mint")
        if not mint or mint in SEEN_MINTS:
            return
        logging.info(f"توکن جدید: {mint}")

        token_info = fetch_token_info(mint)
        if not token_info:
            return

        msg = format_token_message(token_info)
        if msg:
            send_telegram_message(msg)
            time.sleep(1)  # تأخیر برای جلوگیری از بلاک شدن توسط تلگرام
        else:
            logging.info("پیام نامعتبر یا فیلتر شده")
    except Exception:
        logging.exception("خطا در پردازش پیام WebSocket")

# تابع مدیریت خطاهای WebSocket
def on_error(ws, error):
    logging.error(f"خطای WebSocket: {error}")

# تابع مدیریت بسته شدن WebSocket
def on_close(ws, close_status_code, close_msg):
    logging.info(f"اتصال WebSocket بسته شد: کد {close_status_code}, پیام: {close_msg}")
    backoff = 5
    while True:
        logging.info(f"تلاش برای اتصال دوباره بعد از {backoff} ثانیه...")
        time.sleep(backoff)
        try:
            start_websocket()
            break
        except Exception:
            backoff = min(backoff * 2, 60)  # حداکثر تأخیر 60 ثانیه

# تابع مدیریت باز شدن WebSocket
def on_open(ws):
    logging.info("اتصال WebSocket برقرار شد")
    send_telegram_message("✅ بات WebSocket شروع به کار کرد")

# تابع شروع WebSocket
def start_websocket():
    ws = websocket.WebSocketApp(
        "wss://pumpportal.fun/api/data",
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
        on_open=on_open
    )
    ws.run_forever()

if __name__ == "__main__":
    logging.info("شروع بات WebSocket PumpGuardians...")
    keep_alive()  # فرض می‌کنم این تابع برای آنلاین نگه داشتن باته
    start_websocket()
