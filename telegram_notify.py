import os
import requests
import logging

logger = logging.getLogger("telegram")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        return  # телега выключена
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=5)
    except Exception as e:
        logger.error(f"telegram_send_error={e}")
