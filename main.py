import requests
import websocket
import json
import time
import datetime
import traceback
import logging
import os
from keep_alive import keep_alive

# تنظیمات لاگینگ
logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# اطلاعات بات تلگرام
TELEGRAM_BOT_TOKEN = "8041985955:AAGNPL_dWWWI5AWlYFue5NxkNOXsYqBOmiw"
TELEGRAM_CHANNEL_ID = "@PumpGuardians"
SEEN_MINTS = set()

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
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code != 200:
            logging.error(f"خطا در ارسال به تلگرام: {response.text}")
        else:
            logging.info("پیام با موفقیت به تلگرام ارسال شد")
    except Exception as e:
        logging.exception("خطای غیرمنتظره در ارسال پیام به تلگرام")

# تابع فرمت کردن اطلاعات معامله
def format_trade_message(data):
    try:
        mint = data.get("mint")
        if not mint or mint in SEEN_MINTS:
            return None
        SEEN_MINTS.add(mint)

        tx_type = data.get("txType", "؟")  # نوع معامله (buy یا sell)
        trader = data.get("traderPublicKey", "ناشناس")[:8] + "..."  # کوتاه کردن آدرس معامله‌گر
        token_amount = float(data.get("tokenAmount", 0))
        market_cap = float(data.get("marketCapSol", 0))
        sol_in_curve = float(data.get("vSolInBondingCurve", 0))
        tokens_in_curve = float(data.get("vTokensInBondingCurve", 0))

        message = (
            f"<b>PUMP GUARDIANS AI - معامله جدید</b>\n\n"
            f"📈 <b>توکن:</b> {mint[:8]}...\n"
            f"💱 <b>نوع معامله:</b> {tx_type}\n"
            f"👤 <b>معامله‌گر:</b> {trader}\n"
            f"💵 <b>مقدار توکن:</b> {token_amount:,.0f}\n"
            f"💰 <b>ارزش بازار (SOL):</b> {market_cap:,.2f}\n"
            f"🏦 <b>SOL در Bonding Curve:</b> {sol_in_curve:,.2f}\n"
            f"📊 <b>توکن‌ها در Bonding Curve:</b> {tokens_in_curve:,.0f}\n\n"
            f"<a href='https://pump.fun/{mint}'>خرید</a> | "
            f"<a href='https://www.dexscreener.com/solana/{mint}'>چارت</a>"
        )
        return message
    except Exception:
        logging.exception("خطا در فرمت کردن پیام معامله")
        return None

# تابع دریافت اطلاعات توکن از API (برای اطلاعات اضافی، اگه نیاز شد)
def fetch_token_info(address):
    try:
        url = f"https://pumpportal.fun/api/mint/{address}"
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            logging.error(f"خطا در دریافت اطلاعات توکن {address}: {res.status_code} - {res.text}")
            return None
        return res.json()
    except Exception:
        logging.exception(f"خطا در دریافت اطلاعات توکن {address}")
        return None

# تابع مدیریت پیام‌های WebSocket
def on_message(ws, message):
    try:
        logging.info(f"پیام خام WebSocket دریافت شد: {message}")
        data = json.loads(message)
        
        # فقط معاملات رو پردازش کن
        if "txType" in data and data.get("txType") in ["buy", "sell"]:
            logging.info(f"معامله جدید دریافت شد: {data.get('mint')}")
            msg = format_trade_message(data)
            if msg:
                send_telegram_message(msg)
                logging.info(f"پیام برای معامله {data.get('mint')} به تلگرام ارسال شد")
        else:
            logging.info("پیام دریافت‌شده معامله نیست، نادیده گرفته شد")
    except Exception:
        logging.exception("خطا در پردازش پیام WebSocket")

def on_error(ws, error):
    logging.error(f"خطای WebSocket: {error}")

def on_close(ws, close_status_code, close_msg):
    logging.info(f"اتصال WebSocket بسته شد: {close_status_code}, {close_msg}")
    backoff = 5
    while True:
        logging.info(f"تلاش برای اتصال دوباره بعد از {backoff} ثانیه...")
        time.sleep(backoff)
        try:
            start_websocket()
            break
        except Exception:
            backoff = min(backoff * 2, 60)

def on_open(ws):
    logging.info("اتصال به WebSocket برقرار شد")
    send_telegram_message("✅ بات WebSocket شروع به کار کرد - در انتظار معاملات...")
    
    # اشتراک به معاملات توکن‌ها
    payload = {
        "method": "subscribeTokenTrade",
        "keys": []  # اگه بخوای توکن خاصی رو مانیتور کنی، آدرسش رو اینجا بذار، وگرنه همه توکن‌ها رو می‌گیره
    }
    ws.send(json.dumps(payload))
    logging.info("اشتراک به معاملات توکن‌ها انجام شد")

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
    send_telegram_message("🚀 بات در حال راه‌اندازی است...")
    keep_alive()
    try:
        start_websocket()
    except Exception as e:
        logging.exception("خطا در شروع WebSocket")
        send_telegram_message(f"❌ خطا در اتصال WebSocket: {str(e)}")
