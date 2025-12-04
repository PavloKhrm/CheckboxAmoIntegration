import os
import requests
import logging

from config import NP_SENDER_NAME_1, NP_SENDER_NAME_2

logger = logging.getLogger("telegram")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PROFILE_SENDER_MAP = {
    "1": NP_SENDER_NAME_1,
    "2": NP_SENDER_NAME_2,
}

def resolve_sender_name(profile_id: str) -> str:
    return PROFILE_SENDER_MAP.get(profile_id, profile_id)

def send_telegram(text: str, profile_id: str | None = None):
    if not BOT_TOKEN or not CHAT_ID:
        return
    sender = resolve_sender_name(profile_id) if profile_id else ""
    final_text = f"<b>{sender}</b>\n{text}" if sender else text
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={
                "chat_id": CHAT_ID,
                "text": final_text,
                "parse_mode": "HTML"
            },
            timeout=5
        )
    except Exception as e:
        logger.error(f"telegram_send_error={e}")
