import requests
import websocket
import threading
import json
import time
import datetime
import traceback
from keep_alive import keep_alive

TELEGRAM_BOT_TOKEN = "8041985955:AAGNPL_dWWWI5AWlYFue5NxkNOXsYqBOmiw"
TELEGRAM_CHANNEL_ID = "@PumpGuardians"
SEEN_MINTS = set()

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
        print(f"[Telegram] Status: {response.status_code}")
        if response.status_code != 200:
            print(f"[Telegram Error] {response.text}")
    except Exception as e:
        print("[Telegram Exception]")
        traceback.print_exc()

def format_token_message(info):
    try:
        address = info.get("address", "")
        if not address or address in SEEN_MINTS:
            return None
        SEEN_MINTS.add(address)

        name = info.get("name", "?")
        symbol = info.get("symbol", "?")
        price_usd = float(info.get("usdMarketPrice") or 0)
        price_sol = float(info.get("solMarketPrice") or 0)
        volume = float(info.get("totalVolume") or 0)
        market_cap = float(info.get("marketCapUsd") or 0)
        holders = info.get("holders", "?")
        twitter = info.get("twitter") or "Not available"
        website = info.get("website") or "Not available"
        created_at = int(info.get("created_at") or 0)

        score = int(info.get("score") or 3)
        green_circles = "🟢" * score

        age_str = "Unknown"
        if created_at:
            age_seconds = int(datetime.datetime.now().timestamp()) - created_at
            age_minutes = age_seconds // 60
            age_str = f"{age_minutes} min ago"

        message = (
            f"<b>PUMP GUARDIANS AI</b>\n\n"
            f"<b>{name} / {symbol}</b>\n"
            f"{green_circles}\n\n"
            f"💵 <b>Price:</b> ${price_usd:.4f} ({price_sol:.4f} SOL)\n"
            f"💰 <b>Market Cap:</b> ${market_cap:,.0f}\n"
            f"📈 <b>Volume:</b> {volume:,.0f} SOL\n"
            f"👥 <b>Holders:</b> {holders}\n"
            f"⏱️ <b>Age:</b> {age_str}\n"
            f"🌐 <b>Website:</b> {website}\n"
            f"🐦 <b>Twitter:</b> {twitter}\n\n"
            f"<a href='https://pump.fun/{address}'>Buy</a> | "
            f"<a href='https://www.dexscreener.com/solana/{address}'>Chart</a> | "
            f"<a href='https://birdeye.so/token/{address}'>More Info</a>"
        )
        return message
    except Exception:
        traceback.print_exc()
        return None

def fetch_token_info(address):
    try:
        url = f"https://pumpportal.fun/api/mint/{address}"
        res = requests.get(url)
        if res.status_code != 200:
            print(f"[ERROR] Failed to get token info for {address}: {res.text}")
            return None
        return res.json()
    except Exception:
        print(f"[EXCEPTION] Fetch token info for {address}")
        traceback.print_exc()
        return None

def on_message(ws, message):
    try:
        data = json.loads(message)
        mint = data.get("mint")
        if not mint or mint in SEEN_MINTS:
            return
        print(f"[INFO] New token: {mint}")

        token_info = fetch_token_info(mint)
        if not token_info:
            return

        msg = format_token_message(token_info)
        if msg:
            send_telegram_message(msg)
        else:
            print("[SKIP] Invalid message format.")
    except Exception:
        print("[EXCEPTION] While handling WebSocket message:")
        traceback.print_exc()

def on_error(ws, error):
    print(f"[WebSocket Error] {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"[WebSocket Closed] Code: {close_status_code}, Msg: {close_msg}")
    print("[INFO] Reconnecting in 5 seconds...")
    time.sleep(5)
    start_websocket()

def on_open(ws):
    print("[WebSocket] Connection established.")

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
    print("[STARTING] PumpGuardians WebSocket bot running...")
    send_telegram_message("✅ PumpGuardians WebSocket bot started.")
    keep_alive()
    start_websocket()
